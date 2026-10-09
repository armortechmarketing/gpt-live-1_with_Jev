import type { ServerMessage } from "../types";

export type SessionSocket = {
  sendAudio: (audio: string) => void;
  decide: (id: string, decision: "approve" | "reject") => void;
  stop: () => void;
};

export function openSession(onMessage: (message: ServerMessage) => void, onClose: () => void): SessionSocket {
  const protocol = window.location.protocol === "https:" ? "wss" : "ws";
  const socket = new WebSocket(`${protocol}://${window.location.host}/ws/session`);

  socket.addEventListener("message", (event) => {
    onMessage(JSON.parse(String(event.data)) as ServerMessage);
  });
  socket.addEventListener("close", onClose);
  socket.addEventListener("error", onClose);

  const send = (payload: object) => {
    if (socket.readyState === WebSocket.OPEN) socket.send(JSON.stringify(payload));
  };

  return {
    sendAudio: (audio) => send({ type: "audio", audio }),
    decide: (id, decision) => send({ type: "human_decision", id, decision }),
    stop: () => {
      send({ type: "stop" });
      socket.close();
    },
  };
}
