from statistics import mean, median


class OutcomeStatistics:

    @staticmethod
    def calculate(
        returns: list[float | None],
    ) -> dict:

        values = [
            value
            for value in returns
            if value is not None
        ]

        if not values:

            return {
                "sample_size": 0,
                "positive_probability": None,
                "average_return": None,
                "median_return": None,
                "best_return": None,
                "worst_return": None,
            }

        positive = [
            value
            for value in values
            if value > 0
        ]

        return {
            "sample_size": len(values),

            "positive_probability": round(
                len(positive) / len(values),
                4,
            ),

            "average_return": round(
                mean(values),
                2,
            ),

            "median_return": round(
                median(values),
                2,
            ),

            "best_return": round(
                max(values),
                2,
            ),

            "worst_return": round(
                min(values),
                2,
            ),
        }