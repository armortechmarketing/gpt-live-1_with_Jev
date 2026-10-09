from typing import Literal

Verdict = Literal["allow", "human", "block"]

IRREVERSIBLE_BLOCK = 0.70
RISKY_BLOCK = 0.80
REVIEW = 0.45


def verdict_for(risky: float, irreversible: float) -> Verdict:
    """Decide from Jev probabilities. This function is the only policy."""
    if irreversible >= IRREVERSIBLE_BLOCK or risky >= RISKY_BLOCK:
        return "block"
    if irreversible >= REVIEW or risky >= REVIEW:
        return "human"
    return "allow"


def commentary_for(verdict: Verdict, resolution: Literal["approved", "rejected"] | None = None) -> str:
    if resolution == "approved":
        return (
            "A person approved this action. Tell the caller it is approved. "
            "Do not say a refund, email, or deletion was actually carried out."
        )
    if resolution == "rejected":
        return (
            "A person rejected this action. Tell the caller it will not proceed. "
            "Do not attempt the action."
        )
    if verdict == "allow":
        return (
            "Gate result: allowed. Tell the caller this step is approved to proceed. "
            "Do not say a refund, email, or deletion was actually carried out."
        )
    if verdict == "block":
        return (
            "Gate result: blocked. Tell the caller this action is blocked because it is "
            "risky or irreversible. Do not proceed."
        )
    return (
        "Gate result: a person must approve this first. Tell the caller you are waiting "
        "for a person. Do not proceed until that person answers."
    )
