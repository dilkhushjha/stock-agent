import hashlib
from datetime import datetime
from email.utils import parsedate_to_datetime

import feedparser


class RSSNewsCollector:

    @staticmethod
    def _parse_date(entry) -> datetime | None:
        """
        Convert RSS publication date into a Python datetime.
        """

        date_value = (
            entry.get("published")
            or entry.get("updated")
        )

        if not date_value:
            return None

        try:
            return parsedate_to_datetime(
                date_value
            ).replace(tzinfo=None)

        except Exception:
            return None

    @staticmethod
    def _generate_url(entry) -> str:
        """
        Extract article URL.
        """

        return entry.get(
            "link",
            ""
        ).strip()

    @staticmethod
    def collect(
        feed_url: str,
        source: str,
        limit: int = 20,
    ) -> list[dict]:

        feed = feedparser.parse(feed_url)

        articles = []

        for entry in feed.entries[:limit]:

            url = RSSNewsCollector._generate_url(
                entry
            )

            if not url:
                continue

            title = entry.get(
                "title",
                ""
            ).strip()

            summary = entry.get(
                "summary",
                ""
            ).strip()

            articles.append(
                {
                    "title": title,
                    "url": url,
                    "source": source,
                    "published_at": (
                        RSSNewsCollector._parse_date(
                            entry
                        )
                    ),
                    "summary": summary,
                    "content": summary,
                    "language": "en",
                }
            )

        return articles