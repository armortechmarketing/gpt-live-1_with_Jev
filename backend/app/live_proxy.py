import asyncio
import json
import logging
import uuid
from typing import Any

import websockets
from fastapi import WebSocket, WebSocketDisconnect
from websockets.asyncio.client import ClientConnection

from app.config import Settings
from app.gate import commentary_for, verdict_for
from app.jev_client import JevError, judge_action

logger = logging.getLogger(__name__)

LIVE_URL = "wss://api.openai.com/v1/live/sessions"
JUDGE_PAUSE_SECONDS = 0.6

INSTRUCTIONS = """You are a calm support agent on a live call.
You may discuss drafting a reply, looking up an order, issuing a refund, or emailing customers.

Backchannel policy: Use light backchannels. Do not talk over the caller.

Interruption policy: Stop speaking when the caller interrupts. Listen.

Delegation policy:
Backend tools:
- Action gate: decides whether a proposed action is allowed, needs a person, or is blocked.

Delegate to the backend when:
- The caller asks you to take an action, change a record, send a message, issue a refund, look something up, or delete anything.
- The caller states what they want done.

Do not delegate to the backend when:
- The caller is only greeting you or asking you to repeat yourself.

Delegate before saying an action is done.
Do not guess the gate result while waiting.
When the gate replies, speak its verdict in one or two short sentences.
Never say a refund, email, or deletion was actually sent. The gate only decides permission.
"""

GREETING = (
    "Speak first. Greet the caller in one short sentence and say you check every "
    "action before it proceeds. Then listen."
)


class LiveProxy:
    def __init__(self, browser: WebSocket, settings: Settings) -> None:
        self.browser = browser
        self.settings = settings
        self.openai: ClientConnection | None = None
        self.ready = False
        self.pending_speech = ""
        self.delegation_id: str | None = None
        self.judge_task: asyncio.Task[None] | None = None
        self.resolutions: dict[str, str] = {}
        self._closed = False

    async def run(self) -> None:
        missing = self.settings.missing_keys()
        if missing:
            await self._status("error", f"Add {', '.join(missing)} to backend/.env and reconnect.")
            return

        await self._status("connecting", "Opening GPT-Live-1")
        headers = {"Authorization": f"Bearer {self.settings.openai_api_key}"}
        try:
            async with websockets.connect(
                LIVE_URL,
                additional_headers=headers,
                max_size=8 * 1024 * 1024,
                open_timeout=20,
            ) as openai_ws:
                self.openai = openai_ws
                await self._send_openai(
                    {
                        "type": "session.start",
                        "event_id": _event_id(),
                        "session": {
                            "model": "gpt-live-1",
                            "instructions": INSTRUCTIONS,
                            "audio": {
                                "format": {"type": "audio/pcm", "rate": 24000},
                                "output": {"voice": "marin"},
                            },
                            "delegation": {"type": "client"},
                        },
                    }
                )
                browser_task = asyncio.create_task(self._from_browser())
                openai_task = asyncio.create_task(self._from_openai())
                done, pending = await asyncio.wait(
                    {browser_task, openai_task},
                    return_when=asyncio.FIRST_COMPLETED,
                )
                for task in pending:
                    task.cancel()
                await asyncio.gather(*pending, return_exceptions=True)
                for task in done:
                    exc = task.exception()
                    if exc and not isinstance(exc, (asyncio.CancelledError, WebSocketDisconnect)):
                        raise exc
        except WebSocketDisconnect:
            return
        except Exception as exc:
            logger.exception("Live session ended")
            await self._status("error", _public_error(exc))
        finally:
            self.ready = False
            if self.judge_task and not self.judge_task.done():
                self.judge_task.cancel()

    async def _from_browser(self) -> None:
        while True:
            raw = await self.browser.receive_text()
            message = json.loads(raw)
            kind = message.get("type")
            if kind == "audio" and self.ready:
                audio = message.get("audio")
                if isinstance(audio, str) and audio:
                    await self._send_openai(
                        {"type": "session.input_audio.append", "audio": audio}
                    )
            elif kind == "human_decision":
                await self._resolve_human(message)
            elif kind == "stop":
                await self._send_openai({"type": "session.close", "event_id": _event_id()})
                return

    async def _from_openai(self) -> None:
        assert self.openai is not None
        async for raw in self.openai:
            event = json.loads(raw)
            event_type = event.get("type", "")
            if event_type == "session.output_audio.delta":
                delta = event.get("delta")
                if isinstance(delta, str) and delta:
                    await self._send_browser({"type": "audio", "audio": delta})
                continue
            if event_type != "session.input_audio.append":
                logger.info("openai event %s", event_type)
            await self._handle_openai(event)

    async def _handle_openai(self, event: dict[str, Any]) -> None:
        event_type = event.get("type")
        if event_type == "session.started":
            self.ready = True
            session = event.get("session") or {}
            session_id = session.get("id", "")
            await self._status("live", "Listening")
            logger.info("session started %s", session_id)
            await self._send_openai(
                {
                    "type": "session.instructions.append",
                    "event_id": _event_id(),
                    "delegation_id": None,
                    "content": GREETING,
                }
            )
            return

        if event_type == "session.input_transcript.delta":
            delta = _delta_text(event)
            if delta:
                self.pending_speech += delta
                await self._send_browser(
                    {"type": "caption", "role": "user", "text": self.pending_speech, "final": False}
                )
            return

        if event_type == "session.output_transcript.delta":
            delta = _delta_text(event)
            if delta:
                await self._send_browser(
                    {"type": "caption", "role": "assistant", "delta": delta, "final": False}
                )
            return

        if event_type == "session.delegation.created":
            delegation = event.get("delegation") or {}
            if delegation.get("target") != "client":
                return
            delegation_id = delegation.get("id")
            if isinstance(delegation_id, str) and delegation_id:
                await self._schedule_judge(delegation_id)
            return

        if event_type == "session.closed":
            await self._status("closed", "Session closed")
            return

        if event_type == "error" or str(event_type).endswith(".error"):
            message = _error_message(event)
            if not self.ready:
                await self._status(
                    "error",
                    message or "GPT-Live-1 did not start. Check that this OpenAI project can use gpt-live-1.",
                )
            else:
                await self._status("error", message or "GPT-Live returned an error.")

    async def _schedule_judge(self, delegation_id: str) -> None:
        self.delegation_id = delegation_id
        if self.judge_task and not self.judge_task.done():
            self.judge_task.cancel()
        self.judge_task = asyncio.create_task(self._judge_after_pause())

    async def _judge_after_pause(self) -> None:
        try:
            await self._judge_once()
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.exception("gate failed")
            # Keep the call open; only session.start failures use state=error.
            await self._status("live", _public_error(exc))

    async def _judge_once(self) -> None:
        await asyncio.sleep(JUDGE_PAUSE_SECONDS)
        delegation_id = self.delegation_id
        action = self.pending_speech.strip()
        self.pending_speech = ""
        if not delegation_id:
            return
        if not action:
            await self._comment(
                delegation_id,
                "No clear action was heard. Ask the caller to repeat what they want done. Do not proceed.",
            )
            await self._status("live", "No speech captured for that check. Ask again.")
            return

        await self._status("live", "Jev is checking this action")
        try:
            risky, irreversible = await judge_action(self.settings.openrouter_api_key, action)
        except JevError as exc:
            logger.warning("jev failed: %s", exc)
            await self._comment(
                delegation_id,
                "The gate could not check this action. Tell the caller it is held. Do not proceed.",
            )
            await self._status("live", str(exc))
            return

        verdict = verdict_for(risky, irreversible)
        self.resolutions[delegation_id] = "pending" if verdict == "human" else "done"
        await self._send_browser(
            {
                "type": "gate",
                "id": delegation_id,
                "action": action,
                "risky": risky,
                "irreversible": irreversible,
                "verdict": verdict,
                "resolution": "pending" if verdict == "human" else None,
            }
        )
        await self._send_browser({"type": "caption", "role": "user", "text": action, "final": True})
        await self._comment(delegation_id, commentary_for(verdict))
        await self._status("live", "Listening")

    async def _resolve_human(self, message: dict[str, Any]) -> None:
        delegation_id = message.get("id")
        decision = message.get("decision")
        if not isinstance(delegation_id, str) or decision not in {"approve", "reject"}:
            return
        if self.resolutions.get(delegation_id) != "pending":
            return
        resolution = "approved" if decision == "approve" else "rejected"
        self.resolutions[delegation_id] = resolution
        await self._send_browser(
            {"type": "gate_resolution", "id": delegation_id, "resolution": resolution}
        )
        await self._comment(delegation_id, commentary_for("human", resolution))

    async def _comment(self, delegation_id: str, content: str) -> None:
        await self._send_openai(
            {
                "type": "session.commentary.append",
                "event_id": _event_id(),
                "delegation_id": delegation_id,
                "content": content,
            }
        )

    async def _send_openai(self, payload: dict[str, Any]) -> None:
        if self.openai is None:
            return
        await self.openai.send(json.dumps(payload))

    async def _send_browser(self, payload: dict[str, Any]) -> None:
        if self._closed:
            return
        try:
            await self.browser.send_json(payload)
        except Exception:
            self._closed = True

    async def _status(self, state: str, detail: str) -> None:
        await self._send_browser({"type": "status", "state": state, "detail": detail})


def _event_id() -> str:
    return f"evt_{uuid.uuid4().hex}"


def _delta_text(event: dict[str, Any]) -> str:
    delta = event.get("delta")
    if isinstance(delta, str):
        return delta
    if isinstance(delta, dict):
        text = delta.get("text") or delta.get("transcript")
        if isinstance(text, str):
            return text
    text = event.get("transcript")
    return text if isinstance(text, str) else ""


def _error_message(event: dict[str, Any]) -> str:
    error = event.get("error")
    if isinstance(error, dict):
        message = error.get("message") or error.get("code")
        if isinstance(message, str):
            return message
    if isinstance(error, str):
        return error
    message = event.get("message")
    return message if isinstance(message, str) else ""


def _public_error(exc: Exception) -> str:
    text = str(exc).strip() or exc.__class__.__name__
    if "401" in text or "invalid_api_key" in text.lower():
        return "OpenAI rejected the API key."
    if "403" in text or "model_not_found" in text or "gpt-live-1" in text.lower():
        return "This OpenAI project could not open gpt-live-1. " + text[:180]
    return text[:240]
