from __future__ import annotations

from app.intelligence.backtest_report import BacktestReport
from app.intelligence.historical_replay import HistoricalReplayRunner
from app.models.event import MarketEvent


class BacktestRunner:
    """Runs the complete opportunity pipeline over historical events."""

    @classmethod
    def run(cls, db, limit: int = 100, event_type: str | None = None) -> dict:
        query = db.query(MarketEvent).order_by(MarketEvent.event_date.asc())
        if event_type:
            query = query.filter(MarketEvent.event_type == event_type)

        events = query.limit(limit).all()
        replay_results = []
        failures = []

        for event in events:
            try:
                replay_results.extend(HistoricalReplayRunner.replay_event(db, event.id))
            except Exception as exc:
                failures.append({"event_id": event.id, "error": str(exc)})

        report = BacktestReport.build(replay_results)
        return {
            "events_requested": len(events),
            "events_replayed": len(events) - len(failures),
            "failures": failures,
            "report": report,
        }
