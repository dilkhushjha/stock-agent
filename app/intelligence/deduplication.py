import hashlib


class NewsDeduplicator:

    @staticmethod
    def fingerprint(
        title: str,
        url: str,
    ) -> str:

        raw = (
            title.strip().lower()
            + "|"
            + url.strip().lower()
        )

        return hashlib.sha256(
            raw.encode("utf-8")
        ).hexdigest()

    @staticmethod
    def deduplicate(
        articles: list[dict],
    ) -> list[dict]:

        seen = set()
        unique = []

        for article in articles:

            fingerprint = (
                NewsDeduplicator.fingerprint(
                    article["title"],
                    article["url"],
                )
            )

            if fingerprint in seen:
                continue

            seen.add(fingerprint)

            article["fingerprint"] = fingerprint

            unique.append(article)

        return unique