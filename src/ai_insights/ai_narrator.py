"""
Portugal Data Intelligence - AI-Powered Narrative Generation
=============================================================
Standalone functions that delegate narrative generation to OpenAI GPT-4
for richer prose when an API key is available.

Extracted from InsightEngine to keep the facade class slim.
"""

import json
from typing import Any, Dict, Optional

import pandas as pd

try:
    from config.settings import OPENAI_MAX_TOKENS, OPENAI_MODEL, OPENAI_TEMPERATURE
except ImportError:
    OPENAI_MODEL = "gpt-4"
    OPENAI_MAX_TOKENS = 2000
    OPENAI_TEMPERATURE = 0.3

try:
    from src.utils.logger import get_logger
except ImportError:
    import logging

    def get_logger(name: str, level: Optional[int] = None) -> logging.Logger:  # type: ignore[misc]
        return logging.getLogger(name)


logger = get_logger(__name__)


def _sanitize_for_prompt(obj: Any) -> Any:
    """Strip control characters and limit string lengths for safe prompt injection."""
    if isinstance(obj, str):
        cleaned = obj.replace("\x00", "").replace("\r", "")
        return cleaned[:2000]
    if isinstance(obj, dict):
        return {str(k)[:100]: _sanitize_for_prompt(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_sanitize_for_prompt(i) for i in obj[:200]]
    return obj


# Re-use the PILLAR_QUERIES display names without importing the full dict
# to avoid circular dependencies.  The caller passes the display_name in.

_PILLAR_QUERIES_DISPLAY = {
    "gdp": "Gross Domestic Product",
    "unemployment": "Unemployment",
    "credit": "Credit to the Economy",
    "interest_rates": "Interest Rates",
    "inflation": "Inflation",
    "public_debt": "Public Debt",
}


def generate_ai_insight(
    openai_client: Any,
    pillar: str,
    data: dict,
    *,
    model: Optional[str] = None,
    max_tokens: Optional[int] = None,
    temperature: Optional[float] = None,
) -> dict:
    """Generate insight for a single pillar using OpenAI GPT-4.

    Parameters
    ----------
    openai_client : openai.OpenAI
        An initialised OpenAI client instance.
    pillar : str
        Pillar identifier (e.g. ``"gdp"``).
    data : dict
        Structured data summary produced by ``InsightEngine._summarise_pillar``.
    model : str, optional
        Override for the OpenAI model name.
    max_tokens : int, optional
        Override for max tokens.
    temperature : float, optional
        Override for sampling temperature.
    """
    model = model or OPENAI_MODEL
    max_tokens = max_tokens or OPENAI_MAX_TOKENS
    temperature = temperature if temperature is not None else OPENAI_TEMPERATURE

    display_name = _PILLAR_QUERIES_DISPLAY.get(pillar, pillar)

    # Prepare a concise data summary for the prompt (sanitized)
    data_summary = _sanitize_for_prompt(
        {
            k: v
            for k, v in data.items()
            if k not in ("annual_data",) and not isinstance(v, pd.DataFrame)
        }
    )

    prompt = f"""You are a senior macroeconomic analyst at a Big4 consulting firm writing an
executive briefing on Portugal's {display_name} data.

DATA SUMMARY:
{json.dumps(data_summary, indent=2, default=str)}

Generate a professional insight with these exact keys (JSON format):
- "pillar": "{pillar}"
- "headline": one-line headline finding (max 100 chars)
- "executive_summary": 2-3 paragraph executive narrative (professional, data-driven)
- "key_findings": array of 4-6 bullet point strings
- "risk_assessment": risk level (HIGH/ELEVATED/MODERATE/LOW) with explanation
- "recommendations": array of 3-4 strategic recommendations
- "outlook": forward-looking statement (1 paragraph)

Use specific numbers from the data. Write in a professional, analytical tone suitable
for a ministerial briefing or board presentation. Focus on Portugal-specific context.
Return ONLY valid JSON."""

    response = openai_client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=max_tokens,
        temperature=temperature,
    )

    content = response.choices[0].message.content.strip()
    # Try to parse JSON from the response
    if content.startswith("```"):
        content = content.split("```")[1]
        if content.startswith("json"):
            content = content[4:]
    result: dict = json.loads(content)
    result["pillar"] = pillar  # ensure correct pillar key
    logger.info(f"AI insight generated for {pillar}.")
    return result


def generate_ai_cross_pillar(
    openai_client: Any,
    summaries: Dict[str, dict],
    *,
    model: Optional[str] = None,
    max_tokens: Optional[int] = None,
    temperature: Optional[float] = None,
) -> dict:
    """Generate cross-pillar insights using OpenAI GPT-4.

    Parameters
    ----------
    openai_client : openai.OpenAI
        An initialised OpenAI client instance.
    summaries : dict
        Mapping of pillar name to its data summary dict.
    model : str, optional
        Override for the OpenAI model name.
    max_tokens : int, optional
        Override for max tokens.
    temperature : float, optional
        Override for sampling temperature.
    """
    model = model or OPENAI_MODEL
    max_tokens = max_tokens or OPENAI_MAX_TOKENS
    temperature = temperature if temperature is not None else OPENAI_TEMPERATURE

    compact = {}
    for k, v in summaries.items():
        if v.get("status") == "ok":
            compact[k] = _sanitize_for_prompt(
                {
                    key: val
                    for key, val in v.items()
                    if key not in ("annual_data",) and not isinstance(val, pd.DataFrame)
                }
            )

    prompt = f"""You are a senior macroeconomic strategist writing a cross-pillar analysis
for Portugal. Analyse the relationships between these macroeconomic pillars:

{json.dumps(compact, indent=2, default=str)}

Generate a JSON response with:
- "relationships": array of objects, each with "name", "pillars" (array), "narrative", "relationship_strength"
  Analyse these relationships:
  1. GDP-Unemployment (Okun's Law)
  2. Interest Rates-Credit Transmission
  3. Inflation-Monetary Policy Alignment
  4. Debt Sustainability vs Growth
- "macro_narrative": 3-4 paragraph synthesis of the overall macro picture

Use specific numbers. Professional tone. Return ONLY valid JSON."""

    response = openai_client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=max_tokens,
        temperature=temperature,
    )

    content = response.choices[0].message.content.strip()
    if content.startswith("```"):
        content = content.split("```")[1]
        if content.startswith("json"):
            content = content[4:]
    result: dict = json.loads(content)
    logger.info("AI cross-pillar insights generated.")
    return result
