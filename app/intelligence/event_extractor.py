import json
import re

import requests


OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL = "qwen2.5:3b"


class EventExtractor:

    @staticmethod
    def extract(
        title: str,
        content: str = "",
    ) -> dict:

        prompt = f"""
You are an Indian stock market intelligence engine.

Analyze the following news article.

TITLE:
{title}

CONTENT:
{content[:5000]}

Extract ONLY information that can materially affect
Indian financial markets.

Return ONLY valid JSON.

Required format:

{{
    "is_market_relevant": true,
    "event_type": "commodity|company|macro|regulation|geopolitical|earnings|other",
    "factor": "SUGAR|CRUDE_OIL|INTEREST_RATES|INFLATION|GDP_GROWTH|OTHER",
    "direction": "UP|DOWN|NEUTRAL",
    "severity": 0.0,
    "time_horizon": "INTRADAY|SHORT_TERM|MEDIUM_TERM|LONG_TERM",
    "summary": "one sentence",
    "reason": "why this matters to markets"
}}

Rules:

1. severity must be between 0 and 1.
2. Use the most relevant factor.
3. If no meaningful market factor exists, use:
   "factor": "OTHER"
   and "is_market_relevant": false.
4. Do not invent facts.
5. Return JSON only.
"""

        try:

            response = requests.post(
                OLLAMA_URL,
                json={
                    "model": MODEL,
                    "prompt": prompt,
                    "stream": False,
                    "format": "json",
                },
                timeout=120,
            )

            response.raise_for_status()

            raw = response.json()["response"]

            return EventExtractor._parse(
                raw
            )

        except Exception as exc:

            return {
                "error": str(exc),
                "is_market_relevant": False,
            }

    @staticmethod
    def _parse(
        raw: str,
    ) -> dict:

        raw = raw.strip()

        try:
            return json.loads(raw)

        except json.JSONDecodeError:
            pass

        match = re.search(
            r"\{.*\}",
            raw,
            re.DOTALL,
        )

        if match:

            try:

                return json.loads(
                    match.group()
                )

            except json.JSONDecodeError:
                pass

        return {
            "error": "Invalid JSON returned by LLM",
            "raw": raw,
            "is_market_relevant": False,
        }