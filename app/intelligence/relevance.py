KEYWORDS = {

    "rbi",
    "sebi",
    "inflation",
    "interest rate",
    "repo rate",
    "gdp",
    "fiscal",
    "government",
    "policy",
    "regulation",
    "earnings",
    "profit",
    "revenue",
    "guidance",
    "sugar",
    "steel",
    "crude",
    "oil",
    "coal",
    "gold",
    "copper",
    "exports",
    "imports",
    "tariff",
    "production",
    "demand",
    "supply",
    "merger",
    "acquisition",
    "order",
    "contract",
    "approval",
}


class NewsRelevance:

    @staticmethod
    def score(article: dict) -> int:

        text = (
            article.get("title", "")
            + " "
            + article.get("content", "")
        ).lower()

        score = 0

        for keyword in KEYWORDS:

            if keyword in text:
                score += 1

        return score

    @staticmethod
    def filter(
        articles: list[dict],
        minimum_score: int = 2,
    ) -> list[dict]:

        relevant = []

        for article in articles:

            score = NewsRelevance.score(
                article
            )

            if score >= minimum_score:

                article["relevance_score"] = score

                relevant.append(article)

        relevant.sort(
            key=lambda x: x["relevance_score"],
            reverse=True,
        )

        return relevant