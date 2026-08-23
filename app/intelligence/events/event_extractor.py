import json
import re

from app.services.llm import OllamaProvider


class EventExtractor:

    def __init__(self):
        self.llm = OllamaProvider()

    @staticmethod
    def _clean_json(raw_response: str) -> str:

        raw_response = raw_response.strip()

        # Remove markdown code fences if present.
        raw_response = re.sub(
            r"^```json\s*",
            "",
            raw_response,
            flags=re.IGNORECASE,
        )

        raw_response = re.sub(
            r"^```\s*",
            "",
            raw_response,
        )

        raw_response = re.sub(
            r"\s*```$",
            "",
            raw_response,
        )

        # Extract the JSON object if additional text exists.
        start = raw_response.find("{")
        end = raw_response.rfind("}")

        if start != -1 and end != -1:
            raw_response = raw_response[start:end + 1]

        return raw_response.strip()

    def extract(
        self,
        title: str,
        content: str,
    ) -> dict:

        prompt = f"""
You are a financial market intelligence engine
specializing in the Indian stock market.

Analyze the following news article.

TITLE:
{title}

CONTENT:
{content}

Your job is to identify the most important
market-relevant EVENT described by the article.

Return ONLY a JSON object.

Required structure:

{{
    "event_type": "",
    "title": "",
    "description": "",
    "entity": "",
    "sector": "",
    "direction": "",
    "impact": "",
    "confidence": 0.0,
    "time_horizon": ""
}}

Allowed event_type values:

EARNINGS
MANAGEMENT_CHANGE
REGULATION
GOVERNMENT_POLICY
COMMODITY
SUPPLY
DEMAND
MERGER_ACQUISITION
FUNDING
MACROECONOMIC
GEOPOLITICAL
LEGAL
OTHER

Allowed direction values:

POSITIVE
NEGATIVE
NEUTRAL

Allowed impact values:

LOW
MEDIUM
HIGH

Allowed time_horizon values:

INTRADAY
SHORT_TERM
MEDIUM_TERM
LONG_TERM

Rules:

1. Do not invent facts.
2. Use only information supported by the article.
3. "entity" should contain the main company,
   commodity, industry or economic entity involved.
4. "sector" should identify the affected Indian
   market sector when reasonably clear.
5. "direction" describes the likely economic/market
   direction of the event.
6. "impact" describes the potential magnitude.
7. "confidence" must be between 0 and 1.
8. If information is insufficient, use NEUTRAL,
   LOW impact and confidence <= 0.3.
"""

        raw_response = self.llm.generate(prompt)

        cleaned = self._clean_json(raw_response)

        try:
            result = json.loads(cleaned)

        except json.JSONDecodeError as exc:
            raise ValueError(
                f"LLM returned invalid JSON: {raw_response}"
            ) from exc

        return result