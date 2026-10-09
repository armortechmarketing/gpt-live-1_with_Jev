import { DEMO_LINES, type Caption, type SessionState } from "../types";
import { MicButton } from "./MicButton";

type ConversationProps = {
  state: SessionState;
  detail: string;
  captions: Caption[];
  onStart: () => void;
  onStop: () => void;
};

export function Conversation({ state, detail, captions, onStart, onStop }: ConversationProps) {
  return (
    <section className="panel conversation">
      <header className="panel-head">
        <div>
          <p className="eyebrow">GPT-Live-1</p>
          <h2>Voice</h2>
        </div>
        <MicButton state={state} onStart={onStart} onStop={onStop} />
      </header>
      <p className={`status status-${state}`}>{detail}</p>
      <div className="captions" aria-live="polite">
        {captions.length === 0 ? (
          <p className="empty">Start the call, then say one of the lines below.</p>
        ) : (
          captions.map((line) => (
            <p key={line.id} className={`caption caption-${line.role}`}>
              <span>{line.role === "user" ? "You" : "Agent"}</span>
              {line.text}
            </p>
          ))
        )}
      </div>
      <div className="prompts">
        {/* <p className="eyebrow">Say one of these</p> */}
        <ol>
          {/* {DEMO_LINES.map((line) => (
            <li key={line}>{line}</li>
          ))} */}
        </ol>
      </div>
    </section>
  );
}
