import httpx

DECISIONS_URL = "https://openrouter.ai/api/alpha/decisions"
MODEL = "typesafe/jev-1.13"

QUESTIONS = {
    "risky": {
        "type": "noul",
        "instructions": "Is this proposed action risky for the business or the customer?",
        "criteria": {
            "true": "The action could cause financial loss, data loss, privacy harm, or a wide unwanted side effect.",
            "false": "The action is a routine read or a reversible draft with little downside.",
        },
    },
    "irreversible": {
        "type": "noul",
        "instructions": "Is this proposed action hard or impossible to undo?",
        "criteria": {
            "true": "Money leaves, a message is sent to many people, or a record is deleted.",
            "false": "The step is a lookup, a draft, or something that can be undone easily.",
        },
    },
}


class JevError(RuntimeError):
    pass


async def judge_action(api_key: str, action: str) -> tuple[float, float]:
    payload = {
        "model": MODEL,
        "state": {
            "proposed_action": action,
            "context": "A voice agent is asking permission before it acts. Judge only this proposed action.",
        },
        "questions": QUESTIONS,
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "http://localhost:5173",
        "X-Title": "Action Gate",
    }
    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.post(DECISIONS_URL, json=payload, headers=headers)
    except httpx.HTTPError as exc:
        raise JevError(f"Jev request failed: {exc}") from exc

    if response.status_code >= 400:
        detail = response.text.strip().replace("\n", " ")
        raise JevError(f"Jev returned {response.status_code}: {detail[:240]}")

    body = response.json()
    answers = body.get("answers") or {}
    try:
        risky = float(answers["risky"]["noul"])
        irreversible = float(answers["irreversible"]["noul"])
    except (KeyError, TypeError, ValueError) as exc:
        raise JevError("Jev response did not include risky and irreversible scores.") from exc
    return risky, irreversible
