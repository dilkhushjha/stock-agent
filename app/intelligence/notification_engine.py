from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.alert import OpportunityAlert


@dataclass(frozen=True)
class NotificationMessage:
    alert_id: int
    symbol: str
    action: str
    title: str
    body: str
    score: float
    risk: str


class NotificationEngine:
    """Builds high-signal notifications without deciding delivery provider."""

    DEFAULT_SCORE_THRESHOLD = 75.0

    @classmethod
    def candidates(cls, db: Session, score_threshold: float | None = None) -> list[NotificationMessage]:
        threshold = score_threshold if score_threshold is not None else cls.DEFAULT_SCORE_THRESHOLD
        alerts = db.scalars(
            select(OpportunityAlert)
            .where(
                OpportunityAlert.status == "NEW",
                OpportunityAlert.opportunity_score >= threshold,
            )
            .order_by(OpportunityAlert.opportunity_score.desc())
        ).all()

        messages = []
        for alert in alerts:
            messages.append(
                NotificationMessage(
                    alert_id=alert.id,
                    symbol=alert.symbol,
                    action=alert.action,
                    title=alert.title,
                    body=alert.reason or "New high-confidence opportunity detected.",
                    score=float(alert.opportunity_score or 0),
                    risk=alert.risk,
                )
            )
        return messages

    @staticmethod
    def format_text(message: NotificationMessage) -> str:
        return (
            f"🚨 {message.title}\n\n"
            f"Action: {message.action}\n"
            f"Score: {message.score:.1f}/100\n"
            f"Risk: {message.risk}\n\n"
            f"{message.body}"
        )
