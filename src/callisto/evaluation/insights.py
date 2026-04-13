"""LLM-powered insight evaluation using any OpenAI-compatible API."""

import json
import logging

from openai import OpenAI

from callisto.config import Config

logger = logging.getLogger(__name__)


def evaluate_transcript(
    transcript_text: str,
    templates: list[dict],
    model: str | None = None,
) -> list[dict]:
    """Evaluate a full transcript against insight templates via an LLM.

    Uses the OpenAI SDK pointed at whatever base_url is configured —
    works with OpenAI, Anthropic (via compatible proxy), Ollama, vLLM,
    Together, OpenRouter, LiteLLM, etc.

    Args:
        transcript_text: The full call transcript as a single string.
        templates: List of template dicts, each with:
            id, name, description, prompt, category, severity
        model: Override the model to use.

    Returns:
        List of detected insight dicts:
            [{"template_id": "...", "confidence": 0.85, "evidence": "...",
              "reasoning": "..."}, ...]
    """
    if not templates:
        logger.info("No active templates — skipping evaluation")
        return []

    client = OpenAI(
        api_key=Config.LLM_API_KEY,
        base_url=Config.LLM_BASE_URL,
    )
    model = model or Config.LLM_MODEL

    template_descriptions = "\n".join(
        f"- Template ID: {t['id']}\n"
        f"  Name: {t['name']}\n"
        f"  Category: {t['category']}\n"
        f"  Severity: {t['severity']}\n"
        f"  Detection criteria: {t['prompt']}"
        for t in templates
    )

    prompt = f"""You are an expert call analyst. Analyze the following phone call transcript and evaluate it against each insight template below. For each template, determine whether the described insight is present in the call.

## Insight Templates to Evaluate

{template_descriptions}

## Call Transcript

{transcript_text}

## Instructions

For each template, evaluate whether the insight is detected in the transcript. Only report insights you are confident are present — do not fabricate or stretch interpretations.

Respond with a JSON array. Each element should have:
- "template_id": the template ID string
- "detected": true or false
- "confidence": a float from 0.0 to 1.0 (only meaningful if detected is true)
- "evidence": the exact quote or close paraphrase from the transcript that supports detection (empty string if not detected)
- "reasoning": brief explanation of why this was or was not detected

Example response format:
[
  {{"template_id": "abc-123", "detected": true, "confidence": 0.92, "evidence": "I'm thinking about switching to another provider", "reasoning": "Caller explicitly mentioned considering alternatives, strong churn signal"}},
  {{"template_id": "def-456", "detected": false, "confidence": 0.0, "evidence": "", "reasoning": "No compliance violations observed in this call"}}
]

Respond ONLY with the JSON array, no other text."""

    logger.info("Evaluating transcript against %d templates with %s", len(templates), model)

    response = client.chat.completions.create(
        model=model,
        temperature=0.1,
        max_tokens=2000,
        messages=[{"role": "user", "content": prompt}],
    )

    response_text = response.choices[0].message.content.strip()

    # Parse the JSON response — handle markdown code fences if present
    if response_text.startswith("```"):
        lines = response_text.split("\n")
        response_text = "\n".join(lines[1:-1])

    try:
        results = json.loads(response_text)
    except json.JSONDecodeError:
        logger.error("Failed to parse LLM response as JSON: %s", response_text[:500])
        return []

    detected = [r for r in results if r.get("detected")]

    usage = response.usage
    in_tok = usage.prompt_tokens if usage else 0
    out_tok = usage.completion_tokens if usage else 0
    logger.info(
        "Evaluation complete: %d/%d insights detected (model=%s, tokens=%d+%d)",
        len(detected),
        len(templates),
        model,
        in_tok,
        out_tok,
    )

    return detected
