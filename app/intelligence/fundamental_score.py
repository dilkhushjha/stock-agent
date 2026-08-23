class FundamentalScore:

    @staticmethod
    def calculate(
        fundamentals: dict,
    ) -> dict:

        score = 50.0
        reasons = []

        roe = fundamentals.get("roe")

        if roe is not None:

            if roe >= 0.20:

                score += 15
                reasons.append(
                    "Strong ROE"
                )

            elif roe >= 0.12:

                score += 8
                reasons.append(
                    "Healthy ROE"
                )

            elif roe < 0:

                score -= 15
                reasons.append(
                    "Negative ROE"
                )

        debt = fundamentals.get(
            "debt_to_equity"
        )

        if debt is not None:

            if debt < 0.5:

                score += 10
                reasons.append(
                    "Low debt"
                )

            elif debt > 2:

                score -= 15
                reasons.append(
                    "High debt"
                )

        earnings_growth = fundamentals.get(
            "earnings_growth"
        )

        if earnings_growth is not None:

            if earnings_growth >= 0.20:

                score += 15
                reasons.append(
                    "Strong earnings growth"
                )

            elif earnings_growth >= 0.10:

                score += 8
                reasons.append(
                    "Positive earnings growth"
                )

            elif earnings_growth < 0:

                score -= 10
                reasons.append(
                    "Declining earnings"
                )

        margin = fundamentals.get(
            "profit_margin"
        )

        if margin is not None:

            if margin >= 0.15:

                score += 10
                reasons.append(
                    "Strong profit margin"
                )

            elif margin < 0:

                score -= 15
                reasons.append(
                    "Negative profit margin"
                )

        score = max(
            0,
            min(100, score),
        )

        if score >= 75:
            rating = "STRONG"

        elif score >= 60:
            rating = "HEALTHY"

        elif score >= 40:
            rating = "NEUTRAL"

        else:
            rating = "WEAK"

        return {
            "score": round(score, 2),
            "rating": rating,
            "reasons": reasons,
        }