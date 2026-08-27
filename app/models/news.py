from datetime import datetime

from sqlalchemy import (
    Column,
    Integer,
    String,
    Text,
    DateTime,
    Boolean,
)

from app.data.database import Base


class NewsArticle(Base):
    __tablename__ = "news_articles"

    id = Column(Integer, primary_key=True, index=True)

    title = Column(String(500), nullable=False)

    url = Column(
        String(1000),
        unique=True,
        nullable=False,
        index=True,
    )

    source = Column(String(200), nullable=True)

    published_at = Column(DateTime, nullable=True)

    summary = Column(Text, nullable=True)

    content = Column(Text, nullable=True)

    language = Column(String(20), default="en")

    is_processed = Column(
        Boolean,
        default=False,
        nullable=False,
    )

    # Which NEWS_SOURCES category/scope this came from. Previously collected by
    # NewsCollector but never persisted, so once an article was stored there was
    # no way to tell domestic from international coverage.
    category = Column(String(50), nullable=True)
    is_international = Column(Boolean, default=False, nullable=False)

    created_at = Column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )
    fingerprint = Column(
        String(64),
        nullable=True,
        unique=True,
        index=True,
    )