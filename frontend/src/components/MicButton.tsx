type MicButtonProps = {
  state: "idle" | "connecting" | "live" | "closed" | "error";
  onStart: () => void;
  onStop: () => void;
};

export function MicButton({ state, onStart, onStop }: MicButtonProps) {
  const live = state === "live";
  const connecting = state === "connecting";
  return (
    <button
      type="button"
      className={live ? "mic mic-live" : "mic"}
      disabled={connecting}
      onClick={live ? onStop : onStart}
    >
      <span className="mic-dot" aria-hidden="true" />
      {connecting ? "Connecting" : live ? "End call" : "Start call"}
    </button>
  );
}
