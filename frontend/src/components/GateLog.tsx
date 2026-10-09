import type { GateCard } from "../types";

type GateLogProps = {
  cards: GateCard[];
  onDecide: (id: string, decision: "approve" | "reject") => void;
};

const LABELS = {
  allow: "Allow",
  human: "Needs a person",
  block: "Block",
} as const;

export function GateLog({ cards, onDecide }: GateLogProps) {
  return (
    <section className="panel gate">
      <header className="panel-head">
        <div>
          <p className="eyebrow">Jev on OpenRouter</p>
          <h2>Approval gate</h2>
        </div>
      </header>
      <p className="rule">
        Block at 70% irreversible or 80% risky. A person reviews either score from 45%.
      </p>
      <div className="cards">
        {cards.length === 0 ? (
          <p className="empty">Checked actions appear here before the agent proceeds.</p>
        ) : (
          cards.map((card) => (
            <article key={card.id} className={`card verdict-${card.verdict}`}>
              <div className="card-top">
                <strong>{labelFor(card)}</strong>
                <span>{LABELS[card.verdict]}</span>
              </div>
              <p className="action">{card.action}</p>
              <dl>
                <div>
                  <dt>Risky</dt>
                  <dd>{percent(card.risky)}</dd>
                </div>
                <div>
                  <dt>Irreversible</dt>
                  <dd>{percent(card.irreversible)}</dd>
                </div>
              </dl>
              {card.verdict === "human" && card.resolution === "pending" ? (
                <div className="decisions">
                  <button type="button" onClick={() => onDecide(card.id, "approve")}>
                    Approve
                  </button>
                  <button type="button" className="reject" onClick={() => onDecide(card.id, "reject")}>
                    Reject
                  </button>
                </div>
              ) : null}
            </article>
          ))
        )}
      </div>
    </section>
  );
}

function labelFor(card: GateCard): string {
  if (card.resolution === "approved") return "Approved by a person";
  if (card.resolution === "rejected") return "Rejected by a person";
  if (card.resolution === "pending") return "Waiting";
  return "Decided";
}

function percent(value: number): string {
  return `${Math.round(value * 100)}%`;
}
