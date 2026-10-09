import { useRef, useState } from "react";
import { Conversation } from "./components/Conversation";
import { GateLog } from "./components/GateLog";
import { PcmPlayer, base64ToBytes, startMicrophone } from "./lib/audio";
import { openSession, type SessionSocket } from "./lib/socket";
import type { Caption, GateCard, ServerMessage, SessionState } from "./types";

export function App() {
  const [state, setState] = useState<SessionState>("idle");
  const [detail, setDetail] = useState("Ready when you are.");
  const [captions, setCaptions] = useState<Caption[]>([]);
  const [cards, setCards] = useState<GateCard[]>([]);
  const sessionRef = useRef<SessionSocket | null>(null);
  const stopMicRef = useRef<(() => void) | null>(null);
  const playerRef = useRef<PcmPlayer | null>(null);
  const audioRef = useRef<AudioContext | null>(null);
  const captionId = useRef(0);
  const generation = useRef(0);
  const stateRef = useRef<SessionState>("idle");

  function applyMessage(message: ServerMessage) {
    if (message.type === "status") {
      stateRef.current = message.state;
      setState(message.state);
      setDetail(message.detail);
      if (message.state === "live") void beginMicrophone(generation.current);
      if (message.state === "error" || message.state === "closed") stopMicrophone();
      return;
    }
    if (message.type === "caption") {
      setCaptions((current) => updateCaptions(current, message, () => `c${(captionId.current += 1)}`));
      return;
    }
    if (message.type === "audio") {
      playerRef.current?.play(base64ToBytes(message.audio));
      return;
    }
    if (message.type === "gate") {
      const card: GateCard = {
        id: message.id,
        action: message.action,
        risky: message.risky,
        irreversible: message.irreversible,
        verdict: message.verdict,
        resolution: message.resolution,
      };
      setCards((current) => [card, ...current.filter((item) => item.id !== card.id)]);
      return;
    }
    if (message.type === "gate_resolution") {
      setCards((current) =>
        current.map((card) => (card.id === message.id ? { ...card, resolution: message.resolution } : card)),
      );
    }
  }

  async function beginMicrophone(id: number) {
    if (stopMicRef.current || generation.current !== id) return;
    const context = audioRef.current ?? new AudioContext();
    audioRef.current = context;
    if (context.state === "suspended") await context.resume();
    playerRef.current = new PcmPlayer(context);
    const stop = await startMicrophone((audio) => sessionRef.current?.sendAudio(audio));
    if (generation.current !== id) {
      stop();
      return;
    }
    stopMicRef.current = stop;
  }

  function stopMicrophone() {
    stopMicRef.current?.();
    stopMicRef.current = null;
  }

  function startCall() {
    const id = generation.current + 1;
    generation.current = id;
    sessionRef.current?.stop();
    sessionRef.current = null;
    stopMicrophone();
    setCaptions([]);
    setCards([]);
    stateRef.current = "connecting";
    setState("connecting");
    setDetail("Opening GPT-Live-1");
    const context = new AudioContext();
    audioRef.current = context;
    playerRef.current = new PcmPlayer(context);
    sessionRef.current = openSession(applyMessage, () => {
      if (generation.current !== id) return;
      stopMicrophone();
      if (stateRef.current === "error") return;
      stateRef.current = "closed";
      setState("closed");
      setDetail("Call ended.");
    });
  }

  function stopCall() {
    generation.current += 1;
    sessionRef.current?.stop();
    sessionRef.current = null;
    stopMicrophone();
    playerRef.current?.reset();
    stateRef.current = "closed";
    setState("closed");
    setDetail("Call ended.");
  }

  return (
    <main className="app">
      <header className="top">
        <div>
          <p className="eyebrow">Approval gate</p>
          <h1>Action Gate</h1>
        </div>
        <p className="lede">GPT-Live-1 speaks. Jev checks each action before it proceeds.</p>
      </header>
      <div className="columns">
        <Conversation state={state} detail={detail} captions={captions} onStart={startCall} onStop={stopCall} />
        <GateLog cards={cards} onDecide={(id, decision) => sessionRef.current?.decide(id, decision)} />
      </div>
    </main>
  );
}

function updateCaptions(
  lines: Caption[],
  message: Extract<ServerMessage, { type: "caption" }>,
  nextId: () => string,
): Caption[] {
  const closed = lines.map((line) =>
    line.role !== message.role && !line.final ? { ...line, final: true } : line,
  );
  const last = closed[closed.length - 1];
  if (message.role === "user") {
    if (last && last.role === "user" && !last.final) {
      return [...closed.slice(0, -1), { ...last, text: message.text, final: message.final }];
    }
    return [...closed, { id: nextId(), role: "user", text: message.text, final: message.final }];
  }
  if (last && last.role === "assistant" && !last.final) {
    return [...closed.slice(0, -1), { ...last, text: last.text + message.delta }];
  }
  return [...closed, { id: nextId(), role: "assistant", text: message.delta, final: false }];
}
