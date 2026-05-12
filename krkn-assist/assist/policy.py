from __future__ import annotations

from dataclasses import dataclass

from .settings import (
    CE_TOP2_GAP_THRESHOLD,
    FAISS_TOP2_GAP_THRESHOLD,
    MIN_CE_SCORE,
    MIN_FAISS_SCORE,
    MIN_MATCH_SCORE,
    MIN_QUERY_WORDS,
)


@dataclass(frozen=True)
class PolicyDecision:
    accepted: bool
    reason: str
    scenarios: list[dict]
    timing_ms: int | None = None


def decide_scenarios(
    *,
    query: str,
    evidence: list[dict],
    threshold: float | None = None,
    allow_multi: bool = True,
) -> PolicyDecision:
    """
    Convert raw ranked evidence into a final decision.

    evidence: list of dicts containing:
      - id
      - final_score
      - score (cross-encoder raw)
      - retrieval_score
      - timing_ms (optional)
    """
    threshold = float(MIN_MATCH_SCORE if threshold is None else threshold)
    query = (query or "").strip()

    if len(query.split()) < MIN_QUERY_WORDS:
        return PolicyDecision(
            accepted=False,
            reason="query_too_short",
            scenarios=[],
            timing_ms=None,
        )

    if not evidence:
        return PolicyDecision(
            accepted=False,
            reason="no_candidates",
            scenarios=[],
            timing_ms=None,
        )

    top = evidence[0]
    top_timing = top.get("timing_ms") or {}
    timing_ms = int(top_timing.get("total")) if "total" in top_timing else None

    top_faiss = float(top.get("retrieval_score", 0.0))
    if top_faiss < MIN_FAISS_SCORE:
        return PolicyDecision(
            accepted=False,
            reason="min_faiss_score",
            scenarios=[],
            timing_ms=timing_ms,
        )

    max_ce = max((float(row.get("score", float("-inf"))) for row in evidence), default=float("-inf"))
    if max_ce < MIN_CE_SCORE:
        return PolicyDecision(
            accepted=False,
            reason="min_ce_score",
            scenarios=[],
            timing_ms=timing_ms,
        )

    top_final = float(top.get("final_score", 0.0))
    if top_final < threshold:
        return PolicyDecision(
            accepted=False,
            reason="final_score_below_threshold",
            scenarios=[],
            timing_ms=timing_ms,
        )

    ambiguous = False
    if allow_multi and len(evidence) >= 2:
        second = evidence[1]
        faiss_gap = abs(float(top.get("retrieval_score", 0.0)) - float(second.get("retrieval_score", 0.0)))
        ce_gap = abs(float(top.get("score", 0.0)) - float(second.get("score", 0.0)))
        ambiguous = faiss_gap < FAISS_TOP2_GAP_THRESHOLD or ce_gap < CE_TOP2_GAP_THRESHOLD

    accepted_rows: list[dict] = []
    if ambiguous and allow_multi:
        for row in evidence[:2]:
            if float(row.get("final_score", 0.0)) >= threshold:
                accepted_rows.append(row)
    else:
        accepted_rows.append(top)

    scenarios = [
        {"name": str(row.get("id") or ""), "score": round(float(row.get("final_score", 0.0)), 4)}
        for row in accepted_rows
        if str(row.get("id") or "").strip()
    ]

    return PolicyDecision(
        accepted=bool(scenarios),
        reason="accepted" if scenarios else "filtered",
        scenarios=scenarios,
        timing_ms=timing_ms,
    )

