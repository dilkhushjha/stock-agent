from __future__ import annotations

from collections import defaultdict
from statistics import mean


class BacktestReport:
    """Turns replay outcomes into decision-oriented diagnostic breakdowns."""

    @staticmethod
    def _bucket(score: float | None) -> str:
        if score is None:
            return "UNKNOWN"
        if score >= 80:
            return "80-100"
        if score >= 60:
            return "60-79"
        if score >= 40:
            return "40-59"
        return "0-39"

    @classmethod
    def build(cls, replay_results: list[dict]) -> dict:
        rows = []
        for result in replay_results:
            for outcome in result.get("outcomes", []):
                if outcome.get("actual_return_percent") is None:
                    continue
                rows.append({
                    "symbol": result.get("symbol"),
                    "event_id": result.get("event_id"),
                    "sector": result.get("sector", "UNKNOWN"),
                    "event_type": result.get("event_type", "UNKNOWN"),
                    "score": result.get("opportunity_score"),
                    **outcome,
                })

        def summarize(items: list[dict]) -> dict:
            if not items:
                return {"observations": 0}
            returns = [x["actual_return_percent"] for x in items]
            excess = [x["excess_return_percent"] for x in items if x.get("excess_return_percent") is not None]
            correct = [x for x in items if x.get("actual_direction_correct") is not None]
            return {
                "observations": len(items),
                "average_return_percent": round(mean(returns), 3),
                "positive_return_rate": round(sum(x > 0 for x in returns) / len(returns), 4),
                "directional_accuracy": round(sum(x["actual_direction_correct"] for x in correct) / len(correct), 4) if correct else None,
                "average_excess_return_percent": round(mean(excess), 3) if excess else None,
                "outperformance_rate": round(sum(x > 0 for x in excess) / len(excess), 4) if excess else None,
            }

        def grouped(key):
            groups = defaultdict(list)
            for row in rows:
                groups[row[key]].append(row)
            return {str(name): summarize(items) for name, items in groups.items()}

        score_groups = defaultdict(list)
        for row in rows:
            score_groups[cls._bucket(row.get("score"))].append(row)

        return {
            "observations": len(rows),
            "by_score_bucket": {name: summarize(items) for name, items in score_groups.items()},
            "by_sector": grouped("sector"),
            "by_event_type": grouped("event_type"),
        }
