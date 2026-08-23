from collections import defaultdict
from statistics import mean


class BacktestMetrics:
    """Aggregates historical replay outcomes into auditable performance metrics."""

    @staticmethod
    def calculate(replay_results: list[dict]) -> dict:
        rows = []
        for result in replay_results:
            for outcome in result.get("outcomes", []):
                if outcome.get("actual_return_percent") is None:
                    continue
                rows.append({
                    "symbol": result.get("symbol"),
                    "event_id": result.get("event_id"),
                    **outcome,
                })

        if not rows:
            return {
                "status": "NO_DATA",
                "observations": 0,
                "horizons": {},
                "overall": {},
            }

        horizons = defaultdict(list)
        for row in rows:
            horizons[row["horizon_days"]].append(row)

        horizon_metrics = {}
        for horizon, items in sorted(horizons.items()):
            directional = [x for x in items if x.get("predicted_probability") is not None]
            correct = [x for x in directional if x["actual_direction_correct"]]
            returns = [x["actual_return_percent"] for x in items]
            errors = [
                abs(x["actual_return_percent"] - x["predicted_return_percent"])
                for x in items
                if x.get("predicted_return_percent") is not None
            ]
            horizon_metrics[str(horizon)] = {
                "observations": len(items),
                "directional_accuracy": round(len(correct) / len(directional), 4) if directional else None,
                "average_actual_return_percent": round(mean(returns), 3),
                "average_absolute_prediction_error_percent": round(mean(errors), 3) if errors else None,
                "positive_return_rate": round(sum(r > 0 for r in returns) / len(returns), 4),
            }

        returns = [x["actual_return_percent"] for x in rows]
        correct = [x for x in rows if x["actual_direction_correct"]]
        return {
            "status": "OK",
            "observations": len(rows),
            "horizons": horizon_metrics,
            "overall": {
                "directional_accuracy": round(len(correct) / len(rows), 4),
                "average_actual_return_percent": round(mean(returns), 3),
                "positive_return_rate": round(sum(r > 0 for r in returns) / len(returns), 4),
            },
        }
