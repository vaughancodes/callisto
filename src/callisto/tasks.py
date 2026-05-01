"""Celery tasks for the cold-path processing pipeline.

Pipeline flow (triggered when a Twilio Media Stream ends):
  1. process_call_end — entry point, dispatches the full chain
  2. assemble_full_transcript — collects hot-path chunks or runs Whisper fallback
  3. run_deep_analysis — full-transcript LLM insight pass, deduped against hot-path
  4. generate_summary — executive summary, sentiment, key topics, action items
  5. compute_cost_accounting — total tokens consumed across the call
"""

import json
import logging
import math
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

from celery import chain
from openai import OpenAI
from sqlalchemy.orm.attributes import flag_modified

from callisto.celery_app import celery
from callisto.config import Config
from callisto.extensions import db
from callisto.models import Call, CallSummary, Insight, InsightTemplate, Tenant, Transcript

logger = logging.getLogger(__name__)


def _get_llm_client() -> OpenAI:
    return OpenAI(api_key=Config.LLM_API_KEY, base_url=Config.LLM_BASE_URL)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

@celery.task(bind=True, name="callisto.process_call_end")
def process_call_end(self, call_id: str, tenant_id: str, audio_path: str):
    """Dispatch the full cold-path analysis chain."""
    pipeline = chain(
        assemble_full_transcript.s({
            "call_id": call_id,
            "tenant_id": tenant_id,
            "audio_path": audio_path,
            "total_input_tokens": 0,
            "total_output_tokens": 0,
        }),
        run_deep_analysis.s(),
        generate_summary.s(),
        compute_cost_accounting.s(),
        prune_expired_recordings.s(tenant_id=tenant_id),
    )
    pipeline.apply_async()
    logger.info("Dispatched cold-path pipeline for call %s", call_id)


# ---------------------------------------------------------------------------
# 1. Assemble transcript
# ---------------------------------------------------------------------------

@celery.task(bind=True, name="callisto.assemble_full_transcript", max_retries=2)
def assemble_full_transcript(self, pipeline_data: dict):
    """Collect the full transcript from hot-path chunks or Whisper fallback."""
    from callisto.transcription.whisper import transcribe_audio

    call_id = pipeline_data["call_id"]
    tenant_id = pipeline_data["tenant_id"]
    audio_path = pipeline_data["audio_path"]

    call = db.session.get(Call, call_id)
    if not call:
        raise ValueError(f"Call {call_id} not found")

    # Use hot-path chunks if they exist. Sort by time so two-speaker
    # conversations render chronologically regardless of which track each
    # chunk arrived on.
    existing_chunks = (
        Transcript.query
        .filter_by(call_id=call.id)
        .order_by(Transcript.start_ms, Transcript.chunk_index)
        .all()
    )

    if existing_chunks:
        # Voicemail calls: discard the internal track (ringback + our
        # <Play>ed greeting) and anything before the voicemail boundary.
        # What's left is just the caller's message — the right substrate
        # for summary / insight / action-item analysis.
        vm = (call.metadata_ or {}).get("voicemail") or {}
        is_voicemail = bool(vm.get("started_at"))
        if is_voicemail:
            boundary_ms = int(vm.get("started_at_ms") or 0)
            existing_chunks = [
                c for c in existing_chunks
                if c.speaker == "external" and (c.start_ms or 0) >= boundary_ms
            ]

        full_transcript = _render_transcript(existing_chunks)
        logger.info(
            "Assembled transcript from %d hot-path chunks for call %s"
            "%s",
            len(existing_chunks), call_id,
            " (voicemail)" if is_voicemail else "",
        )
        # Keep the WAV on disk — the API serves voicemail audio from it
        # (and can serve full-call audio later).

        return {
            **pipeline_data,
            "full_transcript": full_transcript,
            "segment_count": len(existing_chunks),
            "is_voicemail": is_voicemail,
        }

    # Fallback: Whisper re-transcription
    tenant = db.session.get(Tenant, tenant_id)
    whisper_model = tenant.settings.get("whisper_model", "base")

    try:
        segments = transcribe_audio(audio_path, model_name=whisper_model)
    except Exception as e:
        logger.error("Transcription failed for call %s: %s", call_id, e)
        call.status = "failed"
        call.metadata_["error"] = f"Transcription failed: {e}"
        db.session.commit()
        raise self.retry(exc=e, countdown=30)

    fallback_chunks = []
    for seg in segments:
        t = Transcript(
            call_id=call.id,
            tenant_id=call.tenant_id,
            speaker="external",  # Whisper fallback only processes the inbound track (external party)
            text=seg["text"],
            start_ms=seg["start_ms"],
            end_ms=seg["end_ms"],
            confidence=_normalize_logprob(seg["confidence"]),
            chunk_index=seg["chunk_index"],
        )
        db.session.add(t)
        fallback_chunks.append(t)
    db.session.commit()
    logger.info("Stored %d Whisper transcript chunks for call %s", len(segments), call_id)

    full_transcript = _render_transcript(fallback_chunks)
    # Keep the WAV on disk — the API serves voicemail audio from it.

    vm = (call.metadata_ or {}).get("voicemail") or {}
    is_voicemail = bool(vm.get("started_at"))

    return {
        **pipeline_data,
        "full_transcript": full_transcript,
        "segment_count": len(segments),
        "is_voicemail": is_voicemail,
    }


# ---------------------------------------------------------------------------
# 2. Deep analysis — full-context insight detection with deduplication
# ---------------------------------------------------------------------------

@celery.task(bind=True, name="callisto.run_deep_analysis", max_retries=2)
def run_deep_analysis(self, pipeline_data: dict):
    """Second-pass insight detection with full call context.

    The hot path evaluates 60-second windows — it can miss insights that only
    become apparent in full context (e.g. budget concerns in minute 2 +
    cancellation in minute 8 = churn risk).
    """
    call_id = pipeline_data["call_id"]
    tenant_id = pipeline_data["tenant_id"]
    full_transcript = pipeline_data["full_transcript"]
    is_voicemail = bool(pipeline_data.get("is_voicemail"))

    if not full_transcript.strip():
        logger.info("Empty transcript for call %s — skipping deep analysis", call_id)
        return pipeline_data

    call = db.session.get(Call, call_id)
    if not call:
        raise ValueError(f"Call {call_id} not found")

    tenant_obj = db.session.get(Tenant, tenant_id)
    tenant_context = tenant_obj.context if tenant_obj else None

    direction = (call.direction or "inbound")
    template_query = InsightTemplate.query.filter_by(
        tenant_id=tenant_id, active=True
    )
    if direction.startswith("outbound"):
        template_query = template_query.filter_by(outbound_enabled=True)
    else:
        template_query = template_query.filter_by(inbound_enabled=True)
    templates = template_query.all()

    if not templates:
        logger.info(
            "No active %s templates for tenant %s — skipping deep analysis",
            direction, tenant_id,
        )
        return pipeline_data

    def _applies_to_label(val: str) -> str:
        if val == "external":
            return "evaluate ONLY against [external] utterances"
        if val == "internal":
            return "evaluate ONLY against [internal] utterances"
        return "evaluate against BOTH [external] and [internal] utterances"

    template_descriptions = "\n".join(
        f"- Template ID: {t.id}\n"
        f"  Name: {t.name}\n"
        f"  Category: {t.category}\n"
        f"  Severity: {t.severity}\n"
        f"  Applies to: {_applies_to_label(t.applies_to or 'both')}\n"
        f"  Detection criteria: {t.prompt}"
        for t in templates
    )

    context_section = ""
    if tenant_context and tenant_context.strip():
        context_section = f"""## Context

Analyze the call through the lens of the following context about the Callisto user (which may be a business, a team, or an individual) and the kinds of calls they typically handle:

{tenant_context.strip()}

"""

    is_outbound = direction.startswith("outbound")
    direction_section = (
        "## Call Direction (context only; do not restate in outputs)\n\n"
        + (
            "This was an OUTBOUND call (internal party dialed external). "
            "Use this as background when judging whether templates are "
            "triggered. Do not restate who called whom in evidence or "
            "reasoning.\n\n"
            if is_outbound
            else "This was an INBOUND call (external party dialed internal). "
            "Use this as background when judging whether templates are "
            "triggered. Do not restate who called whom in evidence or "
            "reasoning.\n\n"
        )
    )

    voicemail_section = ""
    if is_voicemail:
        voicemail_section = """## Important: This Call Is a Voicemail

The Callisto user did NOT answer this call. The transcript below contains ONLY the caller's recorded voicemail message; there is no live two-party conversation to analyze. Any insight about how the internal party handled the call is not applicable: they weren't on the line. Evaluate templates solely against what the caller said in their message.

"""

    prompt = f"""You are an expert call analyst performing deep post-call analysis. You have access to the COMPLETE call transcript. Analyze it holistically for patterns that may only be visible in full context.

The transcript is from a two-party phone conversation. Each line is prefixed with the speaker:
- [external] = the other party on the call (the contact on the other end)
- [internal] = the Callisto user on this call. This may be someone acting on behalf of a business or team, OR a single individual using Callisto for their own personal calls. Do not assume the internal speaker represents a company, has colleagues, or has an employer unless the transcript or business context says so.

Pay close attention to who said what. A template about the external party's intent should key off [external] utterances; a template about how the internal party is conducting the call should key off [internal] utterances.

Each template has an "Applies to" constraint. If a template says to evaluate only against [external] utterances, you MUST NOT detect it based on anything the [internal] speaker said (and vice versa). Evidence quotes for such a template must come from the matching speaker's lines only.

{direction_section}{voicemail_section}{context_section}## Insight Templates to Evaluate

{template_descriptions}

## Full Call Transcript

{full_transcript}

## Instructions

Evaluate the full transcript against each template. Look for:
- Explicit signals (direct statements matching the template)
- Implicit signals (patterns across the conversation that together indicate the insight)
- Contextual signals (tone shifts, repeated concerns, escalation patterns)

Only report insights you are confident are present.

Respond with a JSON array. Each element:
- "template_id": the template ID string
- "detected": true or false
- "confidence": 0.0 to 1.0
- "evidence": exact quotes from the transcript (include the [external] or [internal] prefix)
- "reasoning": explanation including which speaker triggered it and any cross-conversation patterns

Respond ONLY with the JSON array."""

    client = _get_llm_client()
    try:
        response = client.chat.completions.create(
            model=Config.LLM_MODEL,
            temperature=0.2,
            max_tokens=2000,
            messages=[{"role": "user", "content": prompt}],
        )
    except Exception as e:
        logger.error("Deep analysis LLM call failed for call %s: %s", call_id, e)
        raise self.retry(exc=e, countdown=30)

    # Track token usage
    usage = response.usage
    in_tok = usage.prompt_tokens if usage else 0
    out_tok = usage.completion_tokens if usage else 0

    response_text = response.choices[0].message.content.strip()
    if response_text.startswith("```"):
        lines = response_text.split("\n")
        response_text = "\n".join(lines[1:-1])

    try:
        results = json.loads(response_text)
    except json.JSONDecodeError:
        logger.error("Failed to parse deep analysis response: %s", response_text[:300])
        return {
            **pipeline_data,
            "deep_insights_count": 0,
            "total_input_tokens": pipeline_data.get("total_input_tokens", 0) + in_tok,
            "total_output_tokens": pipeline_data.get("total_output_tokens", 0) + out_tok,
        }

    detected = [r for r in results if r.get("detected")]

    # Deduplicate against hot-path insights already in the database
    existing_insights = Insight.query.filter_by(call_id=call.id).all()
    # Group existing evidence strings by template_id
    existing_by_template: dict[str, list[str]] = {}
    for i in existing_insights:
        tid = str(i.template_id)
        if tid not in existing_by_template:
            existing_by_template[tid] = []
        existing_by_template[tid].append(i.evidence.strip())

    template_map = {str(t.id): t for t in templates}
    new_count = 0
    for det in detected:
        template_id = det.get("template_id", "")
        if template_id not in template_map:
            continue

        evidence = det.get("evidence", "").strip()
        # Skip if evidence overlaps with any existing evidence for this template
        existing_for_tmpl = existing_by_template.get(template_id, [])
        is_dup = any(
            evidence in prev or prev in evidence
            for prev in existing_for_tmpl
        ) if evidence and existing_for_tmpl else False
        if is_dup:
            logger.debug("Dedup: skipping %s — overlaps with hot path evidence", template_id)
            continue

        db.session.add(Insight(
            call_id=call.id,
            tenant_id=call.tenant_id,
            template_id=template_map[template_id].id,
            source="post_call",
            confidence=float(det.get("confidence", 0.0)),
            evidence=evidence,
            result={"reasoning": det.get("reasoning", ""), "raw": det},
        ))
        new_count += 1

    db.session.commit()
    logger.info(
        "Deep analysis for call %s: %d detected, %d new (after dedup), tokens=%d+%d",
        call_id, len(detected), new_count, in_tok, out_tok,
    )

    return {
        **pipeline_data,
        "deep_insights_count": new_count,
        "total_input_tokens": pipeline_data.get("total_input_tokens", 0) + in_tok,
        "total_output_tokens": pipeline_data.get("total_output_tokens", 0) + out_tok,
    }


# ---------------------------------------------------------------------------
# 3. Generate summary — sentiment, key topics, action items
# ---------------------------------------------------------------------------

@celery.task(bind=True, name="callisto.generate_summary", max_retries=2)
def generate_summary(self, pipeline_data: dict):
    """Generate an executive summary with sentiment, key topics, and action items."""
    call_id = pipeline_data["call_id"]
    tenant_id = pipeline_data["tenant_id"]
    full_transcript = pipeline_data["full_transcript"]
    is_voicemail = bool(pipeline_data.get("is_voicemail"))

    if not full_transcript.strip():
        logger.info("Empty transcript for call %s — skipping summary", call_id)
        return pipeline_data

    call = db.session.get(Call, call_id)
    if not call:
        raise ValueError(f"Call {call_id} not found")

    tenant_obj = db.session.get(Tenant, tenant_id)
    tenant_context = tenant_obj.context if tenant_obj else None

    context_section = ""
    if tenant_context and tenant_context.strip():
        context_section = f"""## Context

Analyze the call through the lens of the following context about the Callisto user (which may be a business, a team, or an individual):

{tenant_context.strip()}

"""

    direction = (call.direction or "inbound")
    is_outbound = direction.startswith("outbound")
    direction_section = (
        "## Call Direction (context only; do not restate in the summary)\n\n"
        + (
            "This was an OUTBOUND call (internal party dialed external). "
            "Use this as background to interpret what you're reading. "
            "do not restate who called whom or phrases like \"the "
            "internal party reached out\". Focus the summary on the "
            "substance of the conversation.\n\n"
            if is_outbound
            else "This was an INBOUND call (external party dialed internal). "
            "Use this as background to interpret what you're reading "
            "Do not restate who called whom or phrases like \"the "
            "external party reached out\". Focus the summary on the "
            "substance of the conversation.\n\n"
        )
    )

    voicemail_section = ""
    if is_voicemail:
        voicemail_section = """## Important: This Call Is a Voicemail

The Callisto user did NOT answer this call. The transcript below contains ONLY the caller's recorded voicemail message; there is no live two-party conversation. Frame the summary as "caller left a voicemail saying ..." rather than as a dialogue, and draw sentiment only from the caller's tone.

"""

    prompt = f"""Analyze this phone call transcript and produce a structured summary.

The transcript is from a two-party phone conversation. Each line is prefixed with the speaker:
- [external] = the other party on the call (the contact on the other end)
- [internal] = the Callisto user on this call. This may be someone acting on behalf of a business or team, OR a single individual using Callisto for their own personal calls. Do not assume the internal speaker represents a company, has colleagues, or has an employer unless the transcript or business context says so.

{direction_section}{voicemail_section}{context_section}## Transcript

{full_transcript}

## Instructions

Respond with a JSON object containing:
- "summary": a concise 2-4 sentence executive summary focused on what was discussed and what it means; new information gained from the call. Do not restate facts already obvious from context (who called whom, that it was inbound/outbound, etc.). Avoid em-dashes in the prose.
- "sentiment": one of "positive", "negative", "neutral", or "mixed" (reflecting the overall tone of the call)
- "key_topics": an array of 3-8 topic strings (e.g. "billing", "cancellation", "product feedback")
- "action_items": an array of objects, each with:
  - "text": description of the action item, phrased as something the Callisto user (the "internal" party) should do next. The action item must belong to the internal party. Do NOT include things the external party said they would do; those are not action items.
  - "assignee": always "internal". This field exists only for schema compatibility; omit the item entirely if the action is not for the internal party.
  - "priority": "high", "medium", or "low"
  Only include an action item when there is a concrete follow-up the internal party should take. If nothing is required of them, return an empty array.

If the transcript is too short or unclear for meaningful analysis, still provide your best assessment.

Respond ONLY with the JSON object."""

    client = _get_llm_client()
    try:
        response = client.chat.completions.create(
            model=Config.LLM_MODEL,
            temperature=0.3,
            max_tokens=1000,
            messages=[{"role": "user", "content": prompt}],
        )
    except Exception as e:
        logger.error("Summary generation failed for call %s: %s", call_id, e)
        raise self.retry(exc=e, countdown=30)

    usage = response.usage
    in_tok = usage.prompt_tokens if usage else 0
    out_tok = usage.completion_tokens if usage else 0

    response_text = response.choices[0].message.content.strip()
    if response_text.startswith("```"):
        lines = response_text.split("\n")
        response_text = "\n".join(lines[1:-1])

    try:
        result = json.loads(response_text)
    except json.JSONDecodeError:
        logger.error("Failed to parse summary response: %s", response_text[:300])
        return {
            **pipeline_data,
            "total_input_tokens": pipeline_data.get("total_input_tokens", 0) + in_tok,
            "total_output_tokens": pipeline_data.get("total_output_tokens", 0) + out_tok,
        }

    # Defensive filter: the prompt says action items are for the internal
    # party only, but models occasionally slip in external/shared items.
    # Drop any that aren't explicitly assigned to internal, and force the
    # assignee field to "internal" on the remainder.
    action_items = []
    for item in result.get("action_items", []):
        if not isinstance(item, dict):
            continue
        assignee = (item.get("assignee") or "internal").strip().lower()
        if assignee and assignee != "internal":
            continue
        item["assignee"] = "internal"
        action_items.append(item)

    # Store the summary
    existing = CallSummary.query.filter_by(call_id=call.id).first()
    if existing:
        existing.summary = result.get("summary", "")
        existing.sentiment = result.get("sentiment", "neutral")
        existing.key_topics = result.get("key_topics", [])
        existing.action_items = action_items
        existing.llm_model = Config.LLM_MODEL
    else:
        db.session.add(CallSummary(
            call_id=call.id,
            tenant_id=call.tenant_id,
            summary=result.get("summary", ""),
            sentiment=result.get("sentiment", "neutral"),
            key_topics=result.get("key_topics", []),
            action_items=action_items,
            llm_model=Config.LLM_MODEL,
            token_cost=0,
        ))

    db.session.commit()
    logger.info(
        "Summary for call %s: sentiment=%s, %d topics, %d action items",
        call_id,
        result.get("sentiment"),
        len(result.get("key_topics", [])),
        len(action_items),
    )

    return {
        **pipeline_data,
        "total_input_tokens": pipeline_data.get("total_input_tokens", 0) + in_tok,
        "total_output_tokens": pipeline_data.get("total_output_tokens", 0) + out_tok,
    }


# ---------------------------------------------------------------------------
# 4. Cost accounting
# ---------------------------------------------------------------------------

@celery.task(bind=True, name="callisto.compute_cost_accounting")
def compute_cost_accounting(self, pipeline_data: dict):
    """Record total token usage and mark the call as completed."""
    call_id = pipeline_data["call_id"]
    total_in = pipeline_data.get("total_input_tokens", 0)
    total_out = pipeline_data.get("total_output_tokens", 0)
    total_tokens = total_in + total_out

    call = db.session.get(Call, call_id)
    if not call:
        raise ValueError(f"Call {call_id} not found")

    # Update the summary with total token cost
    summary = CallSummary.query.filter_by(call_id=call.id).first()
    if summary:
        summary.token_cost = total_tokens

    call.status = "completed"
    call.metadata_ = {
        **(call.metadata_ or {}),
        "cold_path_tokens": {
            "input": total_in,
            "output": total_out,
            "total": total_tokens,
        },
    }
    db.session.commit()

    logger.info(
        "Call %s completed. Cold-path tokens: %d in + %d out = %d total",
        call_id, total_in, total_out, total_tokens,
    )

    return {
        **pipeline_data,
        "status": "completed",
        "total_tokens": total_tokens,
    }


# ---------------------------------------------------------------------------
# Re-analyze an existing call
# ---------------------------------------------------------------------------

@celery.task(bind=True, name="callisto.reanalyze_call")
def reanalyze_call(self, call_id: str):
    """Re-run deep analysis and summary for a call that has already been
    processed. Uses the transcript chunks already in the database — does not
    require the original audio file. Previous post-call insights and the
    existing summary are wiped first so the new run replaces them."""
    call = db.session.get(Call, call_id)
    if not call:
        raise ValueError(f"Call {call_id} not found")

    chunks = (
        Transcript.query
        .filter_by(call_id=call.id)
        .order_by(Transcript.start_ms, Transcript.chunk_index)
        .all()
    )
    if not chunks:
        logger.warning("Re-analyze skipped for %s: no transcript chunks", call_id)
        return

    vm = (call.metadata_ or {}).get("voicemail") or {}
    is_voicemail = bool(vm.get("started_at"))
    if is_voicemail:
        boundary_ms = int(vm.get("started_at_ms") or 0)
        chunks = [
            c for c in chunks
            if c.speaker == "external" and (c.start_ms or 0) >= boundary_ms
        ]

    full_transcript = _render_transcript(chunks)

    # Drop prior post-call insights so they don't accumulate. Real-time
    # insights (source='realtime') captured during the live call are kept.
    Insight.query.filter_by(call_id=call.id, source="post_call").delete()
    db.session.commit()

    pipeline_data = {
        "call_id": call_id,
        "tenant_id": str(call.tenant_id),
        "audio_path": "",
        "full_transcript": full_transcript,
        "segment_count": len(chunks),
        "total_input_tokens": 0,
        "total_output_tokens": 0,
        "is_voicemail": is_voicemail,
    }

    pipeline = chain(
        run_deep_analysis.s(pipeline_data),
        generate_summary.s(),
        compute_cost_accounting.s(),
    )
    pipeline.apply_async()
    logger.info("Dispatched re-analysis pipeline for call %s", call_id)


# ---------------------------------------------------------------------------
# Audio retention — auto-delete recordings past the tenant's window
# ---------------------------------------------------------------------------

@celery.task(bind=True, name="callisto.prune_expired_recordings")
def prune_expired_recordings(self, prev_result=None, tenant_id: str | None = None):
    """Delete the saved WAV for any call in ``tenant_id`` whose recording is
    older than the tenant's configured retention window. Transcripts and
    insights are left intact — only the on-disk audio and its
    ``metadata.recording_path`` key are removed.

    Retention lives in ``tenant.settings["audio_retention_days"]``; 0 / null
    means keep forever. Chained off the end of the cold-path pipeline so
    every newly-completed call enforces its tenant's policy.
    """
    if not tenant_id:
        return prev_result

    tenant = db.session.get(Tenant, tenant_id)
    if tenant is None:
        return prev_result

    settings = tenant.settings or {}
    retention_days = settings.get("audio_retention_days")
    try:
        retention_days = int(retention_days) if retention_days else 0
    except (TypeError, ValueError):
        retention_days = 0
    if retention_days <= 0:
        return prev_result

    cutoff = datetime.now(timezone.utc) - timedelta(days=retention_days)

    candidates = (
        Call.query
        .filter(Call.tenant_id == tenant_id)
        .filter(Call.ended_at.isnot(None))
        .filter(Call.ended_at < cutoff)
        .all()
    )

    deleted = 0
    for call in candidates:
        meta = call.metadata_ or {}
        path = meta.get("recording_path")
        if not path:
            continue
        try:
            Path(path).unlink(missing_ok=True)
        except OSError as exc:
            logger.warning(
                "Could not remove expired recording for call %s: %s",
                call.id, exc,
            )
            continue
        meta.pop("recording_path", None)
        call.metadata_ = meta
        flag_modified(call, "metadata_")
        deleted += 1

    if deleted:
        db.session.commit()
        logger.info(
            "Pruned %d expired recording(s) for tenant %s (retention=%dd)",
            deleted, tenant_id, retention_days,
        )

    return prev_result


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _normalize_logprob(logprob: float) -> float:
    """Convert Whisper's avg_logprob (negative, ~-1 to 0) to a 0-1 confidence score."""
    try:
        return max(0.0, min(1.0, math.exp(logprob)))
    except (ValueError, OverflowError):
        return 0.5


def _render_transcript(chunks) -> str:
    """Render a list of Transcript rows as a speaker-labeled conversation.

    Each line is prefixed with [external] or [internal] so the LLM can attribute
    statements to the right party. Chunks are assumed to be in chronological
    order (by start_ms).
    """
    lines = []
    for c in chunks:
        text = (c.text or "").strip()
        if not text:
            continue
        speaker = c.speaker if c.speaker and c.speaker != "unknown" else "speaker"
        lines.append(f"[{speaker}] {text}")
    return "\n".join(lines)
