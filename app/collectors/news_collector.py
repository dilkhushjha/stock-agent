from datetime import datetime, timezone

import feedparser

from app.data.news_sources import NEWS_SOURCES


class NewsCollector:

    def __init__(self):
        self.sources = NEWS_SOURCES

    @staticmethod
    def _parse_date(entry):

        if hasattr(entry, "published_parsed"):

            try:
                return datetime(
                    *entry.published_parsed[:6],
                    tzinfo=timezone.utc,
                )
            except Exception:
                pass

        return datetime.now(timezone.utc)

    def collect(self) -> list[dict]:

        articles = []

        for source in self.sources:

            try:

                feed = feedparser.parse(
                    source["url"]
                )

                for entry in feed.entries:

                    title = getattr(
                        entry,
                        "title",
                        "",
                    ).strip()

                    url = getattr(
                        entry,
                        "link",
                        "",
                    ).strip()

                    summary = getattr(
                        entry,
                        "summary",
                        "",
                    ).strip()

                    if not title or not url:
                        continue

                    articles.append(
                        {
                            "title": title,
                            "url": url,
                            "content": summary,
                            "source": source["name"],
                            "category": source["category"],
                            "published_at": (
                                self._parse_date(entry)
                            ),
                        }
                    )

            except Exception as exc:

                print(
                    f"[NEWS] Failed source "
                    f"{source['name']}: {exc}"
                )

        return articles