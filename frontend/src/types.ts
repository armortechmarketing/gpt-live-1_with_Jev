export type SessionState = "idle" | "connecting" | "live" | "closed" | "error";

export type Verdict = "allow" | "human" | "block";

export type GateCard = {
  id: string;
  action: string;
  risky: number;
  irreversible: number;
  verdict: Verdict;
  resolution: "pending" | "approved" | "rejected" | null;
};

export type Caption = {
  id: string;
  role: "user" | "assistant";
  text: string;
  final: boolean;
};

export type ServerMessage =
  | { type: "status"; state: Exclude<SessionState, "idle">; detail: string }
  | { type: "caption"; role: "user"; text: string; final: boolean }
  | { type: "caption"; role: "assistant"; delta: string; final: boolean }
  | { type: "audio"; audio: string }
  | {
      type: "gate";
      id: string;
      action: string;
      risky: number;
      irreversible: number;
      verdict: Verdict;
      resolution: "pending" | null;
    }
  | { type: "gate_resolution"; id: string; resolution: "approved" | "rejected" };

export const DEMO_LINES = [
  "Draft a reply to the customer.",
  "Look up the order status.",
  "Issue a refund for two thousand four hundred dollars.",
  "Email the whole customer list.",
];
