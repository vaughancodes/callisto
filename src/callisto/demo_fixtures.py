"""Seeded fake data for the /demo sandbox.

Three tenants (a B2B sales team, a small medical practice, and a personal
line), each with a handful of calls covering inbound, outbound, and
voicemail flows. Transcripts, post-call insights, summaries, contacts,
and templates are all included. The data is realistic enough to evaluate
the product but obviously synthetic.

Everything is in-memory: the demo API ships fixed UUIDs so deep links into
the sandbox are reproducible across deploys.
"""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone
from typing import Any


def _iso(days_ago: float, hour: int = 10, minute: int = 0) -> str:
    base = datetime.now(timezone.utc).replace(
        hour=hour, minute=minute, second=0, microsecond=0
    )
    return (base - timedelta(days=days_ago)).isoformat()


# ---------------------------------------------------------------------------
# Tenants
# ---------------------------------------------------------------------------

TENANTS: list[dict[str, Any]] = [
    {
        "id": "11111111-1111-1111-1111-111111111111",
        "organization_id": "00000000-0000-0000-0000-000000000001",
        "organization_name": "Demo Org",
        "name": "Northwind Sales",
        "slug": "northwind-sales",
        "description": "B2B SaaS sales team. Outbound and inbound revenue calls.",
        "context": (
            "Northwind sells inventory management software to mid-market "
            "warehouses and 3PLs. Most calls are outbound prospecting, "
            "inbound demo requests, or follow-ups with existing customers "
            "discussing renewals, expansions, or churn risk."
        ),
        "settings": {},
        "tagline": "B2B SaaS sales. Calls with prospects and customers.",
        "color": "brand-sky",
    },
    {
        "id": "22222222-2222-2222-2222-222222222222",
        "organization_id": "00000000-0000-0000-0000-000000000001",
        "organization_name": "Demo Org",
        "name": "Crescent Family Medicine",
        "slug": "crescent-clinic",
        "description": "Small primary-care clinic. Appointment and triage calls.",
        "context": (
            "Crescent is a 4-physician family medicine practice. Calls are "
            "patients booking appointments, asking about prescriptions, "
            "reporting symptoms for triage, or requesting records. HIPAA "
            "compliance and accurate triage routing are top priority."
        ),
        "settings": {},
        "tagline": "Primary-care clinic. Triage and patient intake.",
        "color": "accent-lavender",
    },
    {
        "id": "33333333-3333-3333-3333-333333333333",
        "organization_id": "00000000-0000-0000-0000-000000000001",
        "organization_name": "Demo Org",
        "name": "Personal Line",
        "slug": "personal",
        "description": "An individual using Callisto on their own number.",
        "context": (
            "Personal line. Most calls are with contractors about home "
            "repairs, scheduling appointments with my doctor or dentist, "
            "or family checking in. Not a business; there's no team, "
            "just one person."
        ),
        "settings": {},
        "tagline": "Personal line. Callisto isn't just for businesses.",
        "color": "accent-periwinkle",
    },
]


# ---------------------------------------------------------------------------
# Templates (per tenant)
# ---------------------------------------------------------------------------

TEMPLATES: dict[str, list[dict[str, Any]]] = {
    "11111111-1111-1111-1111-111111111111": [
        {
            "id": "tpl-nw-churn",
            "tenant_id": "11111111-1111-1111-1111-111111111111",
            "name": "Churn Risk",
            "description": "Customer is signaling they may leave.",
            "prompt": "Detect language indicating dissatisfaction, evaluating alternatives, or budget cuts.",
            "category": "Retention",
            "severity": "critical",
            "is_realtime": True,
            "active": True,
            "applies_to": "external",
        },
        {
            "id": "tpl-nw-upsell",
            "tenant_id": "11111111-1111-1111-1111-111111111111",
            "name": "Upsell Opportunity",
            "description": "Customer mentions hitting plan limits or new use cases.",
            "prompt": "Detect mentions of needing more seats, hitting feature limits, or new departments adopting.",
            "category": "Revenue",
            "severity": "info",
            "is_realtime": True,
            "active": True,
            "applies_to": "external",
        },
        {
            "id": "tpl-nw-discovery",
            "tenant_id": "11111111-1111-1111-1111-111111111111",
            "name": "Pain Point Mentioned",
            "description": "Prospect describes a specific operational pain.",
            "prompt": "Identify any specific operational frustration, manual workaround, or time-cost the prospect mentions.",
            "category": "Discovery",
            "severity": "info",
            "is_realtime": True,
            "active": True,
            "applies_to": "external",
        },
        {
            "id": "tpl-nw-pricing",
            "tenant_id": "11111111-1111-1111-1111-111111111111",
            "name": "Pricing Objection",
            "description": "Prospect raises concerns about cost.",
            "prompt": "Detect direct or indirect pushback on pricing.",
            "category": "Discovery",
            "severity": "warning",
            "is_realtime": True,
            "active": True,
            "applies_to": "external",
        },
    ],
    "22222222-2222-2222-2222-222222222222": [
        {
            "id": "tpl-cl-urgent",
            "tenant_id": "22222222-2222-2222-2222-222222222222",
            "name": "Urgent Symptom",
            "description": "Patient describes symptoms requiring immediate triage.",
            "prompt": "Detect chest pain, shortness of breath, severe bleeding, suicidal ideation, or other red-flag symptoms.",
            "category": "Triage",
            "severity": "critical",
            "is_realtime": True,
            "active": True,
            "applies_to": "external",
        },
        {
            "id": "tpl-cl-rx",
            "tenant_id": "22222222-2222-2222-2222-222222222222",
            "name": "Prescription Request",
            "description": "Patient is calling about a refill or new Rx.",
            "prompt": "Detect mentions of medications, refills, or pharmacy issues.",
            "category": "Routing",
            "severity": "info",
            "is_realtime": True,
            "active": True,
            "applies_to": "external",
        },
        {
            "id": "tpl-cl-appointment",
            "tenant_id": "22222222-2222-2222-2222-222222222222",
            "name": "Appointment Booking",
            "description": "Patient wants to schedule, reschedule, or cancel.",
            "prompt": "Detect any scheduling intent.",
            "category": "Routing",
            "severity": "info",
            "is_realtime": True,
            "active": True,
            "applies_to": "external",
        },
    ],
    "33333333-3333-3333-3333-333333333333": [
        {
            "id": "tpl-pl-spam",
            "tenant_id": "33333333-3333-3333-3333-333333333333",
            "name": "Likely Spam / Robocall",
            "description": "Call appears to be a spam pitch or robocall.",
            "prompt": "Detect generic sales scripts, warranty pitches, or pre-recorded audio.",
            "category": "Personal",
            "severity": "warning",
            "is_realtime": True,
            "active": True,
            "applies_to": "external",
        },
        {
            "id": "tpl-pl-appt",
            "tenant_id": "33333333-3333-3333-3333-333333333333",
            "name": "Appointment Reminder",
            "description": "Healthcare or service provider confirming a visit.",
            "prompt": "Detect any appointment confirmation or reminder.",
            "category": "Personal",
            "severity": "info",
            "is_realtime": True,
            "active": True,
            "applies_to": "external",
        },
    ],
}


CATEGORIES_BY_TENANT: dict[str, list[str]] = {
    "11111111-1111-1111-1111-111111111111": [
        "Retention",
        "Revenue",
        "Discovery",
    ],
    "22222222-2222-2222-2222-222222222222": ["Triage", "Routing"],
    "33333333-3333-3333-3333-333333333333": ["Personal"],
}


# ---------------------------------------------------------------------------
# Contacts
# ---------------------------------------------------------------------------

CONTACTS: dict[str, list[dict[str, Any]]] = {
    "11111111-1111-1111-1111-111111111111": [
        {
            "id": "c-nw-1",
            "tenant_id": "11111111-1111-1111-1111-111111111111",
            "name": "Priya Mehta",
            "company": "Halberd Logistics",
            "email": "priya.mehta@halberd.example",
            "phone_numbers": ["+15551110001"],
            "notes": (
                "VP Ops at Halberd. Decision maker on the rollout.\n"
                "Wary of multi-quarter deployments after a bad ERP project in 2023.\n"
                "Prefers calls Tue/Thu evenings; hates surprise emails."
            ),
            "created_at": _iso(180),
            "updated_at": _iso(2),
        },
        {
            "id": "c-nw-2",
            "tenant_id": "11111111-1111-1111-1111-111111111111",
            "name": "Marcus Chen",
            "company": "Sundial Distributors",
            "email": "marcus@sundial.example",
            "phone_numbers": ["+15551110002"],
            "notes": "Existing customer. Pro plan, 18 seats. Renewal Q2.",
            "created_at": _iso(220),
            "updated_at": _iso(7),
        },
        {
            "id": "c-nw-3",
            "tenant_id": "11111111-1111-1111-1111-111111111111",
            "name": "Lena Okafor",
            "company": "Brightline 3PL",
            "email": "lena@brightline.example",
            "phone_numbers": ["+15551110003"],
            "notes": (
                "Inbound demo from website. 40k SKUs, 2 facilities (Atlanta + Dallas).\n"
                "Adding a 3rd location in Q3.\n"
                "Cited cycle counting as the biggest pain on their 2014 system."
            ),
            "created_at": _iso(45),
            "updated_at": _iso(1),
        },
    ],
    "22222222-2222-2222-2222-222222222222": [
        {
            "id": "c-cl-1",
            "tenant_id": "22222222-2222-2222-2222-222222222222",
            "name": "Eleanor Park",
            "company": None,
            "email": None,
            "phone_numbers": ["+15552220001"],
            "notes": "DOB 1962-04-12. Long-term patient of Dr. Reese.",
            "created_at": _iso(900),
            "updated_at": _iso(20),
        },
        {
            "id": "c-cl-2",
            "tenant_id": "22222222-2222-2222-2222-222222222222",
            "name": "James Whitfield",
            "company": None,
            "email": "jwhitfield@example.com",
            "phone_numbers": ["+15552220002"],
            "notes": (
                "DOB 1978-03-04. Established patient on Dr. Singh's panel.\n"
                "Hypertension; lisinopril 20mg daily. Last A1c 5.6.\n"
                "Prefers video visits to in-person."
            ),
            "created_at": _iso(120),
            "updated_at": _iso(5),
        },
    ],
    "33333333-3333-3333-3333-333333333333": [
        {
            "id": "c-pl-1",
            "tenant_id": "33333333-3333-3333-3333-333333333333",
            "name": "Mike (Roofer)",
            "company": "Cascade Roofing",
            "email": None,
            "phone_numbers": ["+15553330001"],
            "notes": "Quoted for the back-porch repair, $1800.",
            "created_at": _iso(60),
            "updated_at": _iso(3),
        },
        {
            "id": "c-pl-2",
            "tenant_id": "33333333-3333-3333-3333-333333333333",
            "name": "Dr. Patel's Office",
            "company": None,
            "email": None,
            "phone_numbers": ["+15553330002"],
            "notes": (
                "Primary care office. Reception line.\n"
                "Annual physical scheduled for late March.\n"
                "Send records release form to fax at +1 555 333 0099 if needed."
            ),
            "created_at": _iso(400),
            "updated_at": _iso(10),
        },
    ],
}


# ---------------------------------------------------------------------------
# Calls + everything attached to them
# ---------------------------------------------------------------------------

# Helper: build a call dict + parallel transcript / insights / summary / vm
# entries. Each "scenario" produces one Call's worth of data.

CALLS: list[dict[str, Any]] = []
TRANSCRIPTS: dict[str, list[dict[str, Any]]] = {}
INSIGHTS: dict[str, list[dict[str, Any]]] = {}
SUMMARIES: dict[str, dict[str, Any]] = {}
VOICEMAILS: dict[str, dict[str, Any]] = {}
VOICEMAIL_TRANSCRIPTS: dict[str, list[dict[str, Any]]] = {}


def _add_call(
    *,
    call_id: str,
    tenant_id: str,
    direction: str,
    contact: dict[str, Any] | None,
    other_party_number: str,
    started_days_ago: float,
    duration_sec: int,
    status: str = "completed",
    has_voicemail: bool = False,
    voicemail_started_ms: int | None = None,
    transcript: list[tuple[str, str, int]] | None = None,
    insights: list[dict[str, Any]] | None = None,
    summary: dict[str, Any] | None = None,
    voicemail_transcript: list[tuple[int, str]] | None = None,
    notes: str | None = None,
) -> None:
    started_at = _iso(started_days_ago)
    ended_at = (
        datetime.fromisoformat(started_at) + timedelta(seconds=duration_sec)
    ).isoformat()
    CALLS.append({
        "id": call_id,
        "tenant_id": tenant_id,
        "external_id": f"DEMO_{call_id}",
        "source": "twilio",
        "direction": direction,
        "caller_number": other_party_number if direction == "inbound" else "+15550000000",
        "callee_number": "+15550000000" if direction == "inbound" else other_party_number,
        "other_party_number": other_party_number,
        "our_number_friendly_name": "Main line",
        "contact_id": contact["id"] if contact else None,
        "contact_name": contact["name"] if contact else None,
        "contact_company": contact["company"] if contact else None,
        "agent_id": None,
        "status": status,
        "started_at": started_at,
        "ended_at": ended_at,
        "duration_sec": duration_sec,
        "consent_given": True,
        "notes": notes,
        "topics": (summary or {}).get("key_topics", [])[:3] if summary else [],
        "sentiment": (summary or {}).get("sentiment") if summary else None,
        "summary_text": (summary or {}).get("summary") if summary else None,
        "has_voicemail": has_voicemail,
        # has_recording is computed at request time from the on-disk
        # demo audio file. See _has_call_audio() / _has_voicemail_audio().
        "has_recording": False,
    })
    if transcript:
        TRANSCRIPTS[call_id] = [
            {
                "speaker": speaker,
                "text": text,
                "start_ms": start_ms,
                "end_ms": start_ms + max(2000, len(text) * 60),
                "confidence": 0.92,
                "chunk_index": i,
            }
            for i, (speaker, text, start_ms) in enumerate(transcript)
        ]
    if insights:
        INSIGHTS[call_id] = [
            {
                "id": f"ins-{call_id}-{i}",
                "template_id": ins["template_id"],
                "template_name": ins["template_name"],
                "template_severity": ins.get("template_severity", "info"),
                "source": ins.get("source", "post_call"),
                "detected_at": started_at,
                "confidence": ins.get("confidence", 0.85),
                "evidence": ins["evidence"],
                "result": ins.get("result", {}),
                "transcript_range": ins.get("transcript_range"),
            }
            for i, ins in enumerate(insights)
        ]
    if summary:
        SUMMARIES[call_id] = {
            "call_id": call_id,
            "summary": summary["summary"],
            "sentiment": summary.get("sentiment", "neutral"),
            "key_topics": summary.get("key_topics", []),
            "action_items": summary.get("action_items", []),
            "llm_model": "gpt-4o-mini",
            "token_cost": 1842,
            "created_at": ended_at,
        }
    if has_voicemail and voicemail_started_ms is not None:
        VOICEMAILS[call_id] = {
            "started_at": ended_at,
            "started_at_ms": voicemail_started_ms,
            "dial_status": "no-answer",
            "duration_sec": duration_sec - voicemail_started_ms // 1000,
            "has_recording": False,
        }
        VOICEMAIL_TRANSCRIPTS[call_id] = [
            {
                "speaker": "external",
                "text": text,
                "start_ms": voicemail_started_ms + offset_ms,
                "end_ms": voicemail_started_ms + offset_ms + max(2000, len(text) * 60),
                "confidence": 0.9,
                "chunk_index": i,
            }
            for i, (offset_ms, text) in enumerate(voicemail_transcript or [])
        ]


# --- Northwind Sales calls ---

_add_call(
    call_id="call-nw-001",
    tenant_id="11111111-1111-1111-1111-111111111111",
    direction="outbound",
    contact=CONTACTS["11111111-1111-1111-1111-111111111111"][0],
    other_party_number="+15551110001",
    started_days_ago=0.5,
    duration_sec=128,
    transcript=[
        ("internal", "Hey Priya it's Daniel. You got a sec?", 1000),
        ("external", "Yeah hey Daniel. Sure what's up.", 4000),
        ("internal", "Just wanted to check in on how the rollout's been going.", 7000),
        ("external", "It's been okay. We've gotten three of the warehouses on. But the Phoenix one is dragging.", 11000),
        ("internal", "What's the holdup over there?", 19000),
        ("external", "Honestly the team there is pretty checked out. They're still emailing inventory counts in spreadsheets and our ops manager hasn't pushed them to switch.", 22000),
        ("internal", "That makes sense. We have a few customers who hit that exact pattern. The rollout stalls when there isn't a champion at the site. Would it help if I joined a 30-minute call with the Phoenix lead?", 36000),
        ("external", "That could actually help. Although honestly I'm starting to wonder if the price is right for what we're getting out of it. Three sites in nine months isn't great.", 52000),
        ("internal", "I hear you. Let me put together a usage report so we can see exactly where the value is landing. Then we can decide whether the plan tier still makes sense.", 68000),
        ("external", "Sure. And between you and me Brightline is starting to look at us. So I'd like to get this turned around before our renewal in March.", 84000),
        ("internal", "Got it. I'll have that report to you by Thursday and we'll set up the Phoenix call next week.", 99000),
        ("external", "Sounds good. Thanks Daniel.", 110000),
        ("internal", "Talk to you Friday. Have a good one.", 114000),
        ("external", "You too. Bye.", 120000),
    ],
    insights=[
        {
            "template_id": "tpl-nw-churn",
            "template_name": "Churn Risk",
            "template_severity": "critical",
            "confidence": 0.91,
            "evidence": "I'm starting to wonder if the price is right for what we're getting out of it. Three sites in nine months isn't great.",
            "result": {"reason": "Customer questions ROI plus mentions evaluating alternative (Brightline)."},
        },
        {
            "template_id": "tpl-nw-pricing",
            "template_name": "Pricing Objection",
            "template_severity": "warning",
            "confidence": 0.84,
            "evidence": "I'm starting to wonder if the price is right for what we're getting out of it.",
        },
    ],
    summary={
        "summary": "Check-in on the customer's rollout, which is progressing slowly. The customer raised concerns about value relative to cost and disclosed they're evaluating a competitor ahead of an upcoming renewal. Conversation closed on next steps to help unblock the slowest site.",
        "sentiment": "negative",
        "key_topics": ["rollout pace", "ROI concerns", "competitive evaluation", "renewal"],
        "action_items": [
            {"text": "Send Priya a usage report by Thursday showing where value has landed across the three live warehouses.", "assignee": "internal", "priority": "high"},
            {"text": "Schedule a 30-minute working session with the Phoenix site lead next week.", "assignee": "internal", "priority": "high"},
        ],
    },
    notes=(
        "Renewal in March, at risk. Brightline is the competitor in the mix.\n"
        "Phoenix site has no champion; ops manager hasn't pushed the switch.\n"
        "Promised: usage report by Thu, plus a 30-min call w/ Phoenix lead next wk."
    ),
)

_add_call(
    call_id="call-nw-002",
    tenant_id="11111111-1111-1111-1111-111111111111",
    direction="inbound",
    contact=CONTACTS["11111111-1111-1111-1111-111111111111"][2],
    other_party_number="+15551110003",
    started_days_ago=1.2,
    duration_sec=110,
    transcript=[
        ("internal", "Northwind this is Daniel.", 1000),
        ("external", "Hi Daniel this is Lena from Brightline 3PL. We filled out a demo request on your site.", 3000),
        ("internal", "Hey Lena thanks for calling. What pulled you toward us?", 9000),
        ("external", "Our current system is from 2014 and the cycle-count workflow is brutal. We have eight people doing what should be a one-person job.", 14000),
        ("internal", "Yeah that's a really common starting point. How many SKUs are you tracking?", 26000),
        ("external", "About forty thousand active across two facilities. We're growing fast though. We just signed a contract that's going to take us to a third location in Q3.", 32000),
        ("internal", "Got it. I'd love to set up a proper demo with our solutions team. We have customers in your size range who've been able to consolidate that down to one or two cycle counters.", 47000),
        ("external", "Yeah let's do that. What's the price range we're looking at ballpark?", 64000),
        ("internal", "For your scale we're typically looking at around four thousand a month on the Pro tier. We can dig into the exact bundle on the demo.", 70000),
        ("external", "Sounds good. Let's get something on the calendar for next week.", 84000),
        ("internal", "Perfect. I'll send some times over today.", 92000),
        ("external", "Thanks Daniel appreciate it.", 96000),
        ("internal", "Talk soon.", 100000),
        ("external", "Bye.", 102000),
    ],
    insights=[
        {
            "template_id": "tpl-nw-discovery",
            "template_name": "Pain Point Mentioned",
            "template_severity": "info",
            "confidence": 0.94,
            "evidence": "Our current system is from 2014 and the cycle-count workflow is brutal. We have eight people doing what should be a one-person job.",
        },
        {
            "template_id": "tpl-nw-upsell",
            "template_name": "Upsell Opportunity",
            "template_severity": "info",
            "confidence": 0.79,
            "evidence": "We just signed a contract that's going to take us to a third location in Q3.",
        },
    ],
    summary={
        "summary": "A prospect described their current inventory system as legacy and labor-heavy, particularly around cycle counting. They're growing and expect to add a new facility soon. They asked about pricing and agreed to a follow-up demo.",
        "sentiment": "positive",
        "key_topics": ["legacy replacement", "cycle counting", "expansion", "demo scheduled"],
        "action_items": [
            {"text": "Book a solutions-team demo with Lena for next week and prepare a Pro-tier price model accounting for the Q3 third location.", "assignee": "internal", "priority": "high"},
        ],
    },
    notes=(
        "40k SKUs, 2 facilities, 3rd opening Q3. 8 ppl on cycle counts today.\n"
        "Quoted Pro tier ~$4k/mo ballpark. Confirm exact bundle on demo.\n"
        "Demo to be scheduled next week; loop in solutions team."
    ),
)

_add_call(
    call_id="call-nw-003",
    tenant_id="11111111-1111-1111-1111-111111111111",
    direction="inbound",
    contact=CONTACTS["11111111-1111-1111-1111-111111111111"][1],
    other_party_number="+15551110002",
    started_days_ago=2.1,
    duration_sec=42,
    has_voicemail=True,
    voicemail_started_ms=10000,
    voicemail_transcript=[
        (5000, "Hey this is Marcus over at Sundial. Wanted to give you a heads up. We've got two new sites going live next month and we're going to need to bump our seat count."),
        (18000, "Probably another ten or twelve users. Give me a call back when you get a chance."),
        (28000, "Thanks bye."),
    ],
    insights=[
        {
            "template_id": "tpl-nw-upsell",
            "template_name": "Upsell Opportunity",
            "template_severity": "info",
            "confidence": 0.93,
            "evidence": "We've got two new sites going live next month and we're going to need to bump our seat count. Probably another ten or twelve users.",
        },
    ],
    summary={
        "summary": "The contact left a voicemail flagging upcoming expansion to additional sites and a need to increase their seat count. They asked for a callback to coordinate the change.",
        "sentiment": "positive",
        "key_topics": ["seat expansion", "new sites"],
        "action_items": [
            {"text": "Call Marcus back to confirm the new seat count and prep an order form for the additional 10–12 users.", "assignee": "internal", "priority": "high"},
        ],
    },
    notes=(
        "Sundial: currently 18 seats, Pro plan, renewal Q2.\n"
        "Adding 2 new sites next month → +10-12 users. Prep order form."
    ),
)

# --- Crescent Clinic calls ---

_add_call(
    call_id="call-cl-001",
    tenant_id="22222222-2222-2222-2222-222222222222",
    direction="inbound",
    contact=CONTACTS["22222222-2222-2222-2222-222222222222"][0],
    other_party_number="+15552220001",
    started_days_ago=0.2,
    duration_sec=78,
    transcript=[
        ("internal", "Crescent Family Medicine this is Diana.", 1000),
        ("external", "Hi Diana this is Eleanor Park. I'm a patient of Dr. Reese. I'm having some chest tightness and I'm not sure what to do.", 4000),
        ("internal", "Eleanor can you tell me how long this has been going on?", 13000),
        ("external", "Maybe an hour. It's not severe but it doesn't feel right. I took an aspirin already.", 18000),
        ("internal", "Okay. Are you having any shortness of breath dizziness or pain radiating to your arm or jaw?", 26000),
        ("external", "A little bit of shortness of breath. No arm pain.", 36000),
        ("internal", "I want you to hang up and call 911 right now. We can pull your chart on our end but you should be evaluated immediately. Don't drive yourself.", 41000),
        ("external", "Okay. Okay I'll call them now.", 53000),
        ("internal", "I'm going to call back in thirty minutes to check on you and I'll let Dr. Reese know.", 57000),
        ("external", "Okay. Thank you.", 65000),
        ("internal", "Hang in there. Goodbye.", 68000),
        ("external", "Bye.", 71000),
    ],
    insights=[
        {
            "template_id": "tpl-cl-urgent",
            "template_name": "Urgent Symptom",
            "template_severity": "critical",
            "source": "realtime",
            "confidence": 0.97,
            "evidence": "I'm having some chest tightness... A little bit of shortness of breath.",
        },
    ],
    summary={
        "summary": "A patient called reporting chest tightness with mild shortness of breath that had been ongoing for about an hour. The call ended with the patient agreeing to seek emergency evaluation.",
        "sentiment": "neutral",
        "key_topics": ["chest pain", "triage", "emergency referral"],
        "action_items": [
            {"text": "Call Eleanor back in 30 minutes to confirm she reached EMS, and notify Dr. Reese of the triage.", "assignee": "internal", "priority": "high"},
        ],
    },
    notes=(
        "Eleanor Park, DOB 1962-04-12, Dr. Reese's panel.\n"
        "~1 hr chest tightness + mild SOB, took aspirin, no arm pain.\n"
        "Triaged to 911. Callback at 30 min mark; flag to Dr. Reese."
    ),
)

_add_call(
    call_id="call-cl-002",
    tenant_id="22222222-2222-2222-2222-222222222222",
    direction="inbound",
    contact=CONTACTS["22222222-2222-2222-2222-222222222222"][1],
    other_party_number="+15552220002",
    started_days_ago=0.6,
    duration_sec=66,
    transcript=[
        ("internal", "Crescent Family Medicine this is Diana.", 1000),
        ("external", "Hi I'm trying to get a refill on my lisinopril. I'm down to my last two pills.", 4000),
        ("internal", "Sure can I have your name and date of birth?", 12000),
        ("external", "James Whitfield March 4th 1978.", 16000),
        ("internal", "Got it. I see you're due for a follow-up before we can authorize another 90-day refill. Do you want to come in this week or do a video visit?", 21000),
        ("external", "Video visit works. Whatever's fastest.", 35000),
        ("internal", "I have Wednesday at 4:15 with Dr. Singh. Does that work?", 40000),
        ("external", "Yeah that's perfect. Thank you.", 47000),
        ("internal", "I'll send the join link to your email this afternoon. Have a great day.", 52000),
        ("external", "Thanks you too.", 60000),
        ("internal", "Bye.", 63000),
    ],
    insights=[
        {
            "template_id": "tpl-cl-rx",
            "template_name": "Prescription Request",
            "template_severity": "info",
            "source": "realtime",
            "confidence": 0.96,
            "evidence": "I'm trying to get a refill on my lisinopril.",
        },
        {
            "template_id": "tpl-cl-appointment",
            "template_name": "Appointment Booking",
            "template_severity": "info",
            "confidence": 0.91,
            "evidence": "I have Wednesday at 4:15 with Dr. Singh. Does that work? Yeah that's perfect.",
        },
    ],
    summary={
        "summary": "A patient called to request a medication refill. The call covered scheduling requirements for the refill and ended with a video visit booked.",
        "sentiment": "positive",
        "key_topics": ["medication refill", "video visit", "follow-up scheduled"],
        "action_items": [
            {"text": "Confirm the Wednesday 4:15 video visit slot is held with Dr. Singh and send the patient the join link.", "assignee": "internal", "priority": "medium"},
        ],
    },
    notes=(
        "James Whitfield: lisinopril refill, down to last 2 pills.\n"
        "Booked Wed 4:15 video w/ Dr. Singh. Send join link."
    ),
)

# --- Personal line calls ---

_add_call(
    call_id="call-pl-001",
    tenant_id="33333333-3333-3333-3333-333333333333",
    direction="inbound",
    contact=CONTACTS["33333333-3333-3333-3333-333333333333"][0],
    other_party_number="+15553330001",
    started_days_ago=0.3,
    duration_sec=42,
    has_voicemail=True,
    voicemail_started_ms=10000,
    voicemail_transcript=[
        (4000, "Hey it's Mike from Cascade Roofing. Just wanted to circle back about the back-porch repair we quoted last week."),
        (16000, "We've got an opening Thursday morning if you want to lock that in. Give me a buzz back."),
        (26000, "Talk soon."),
    ],
    insights=[
        {
            "template_id": "tpl-pl-appt",
            "template_name": "Appointment Reminder",
            "template_severity": "info",
            "confidence": 0.89,
            "evidence": "We've got an opening Thursday morning if you want to lock that in.",
        },
    ],
    summary={
        "summary": "The caller left a voicemail offering an availability window for previously-quoted work and asked for a callback to confirm.",
        "sentiment": "neutral",
        "key_topics": ["repair scheduling", "callback requested"],
        "action_items": [
            {"text": "Call Mike back to confirm or decline the Thursday morning roofing repair slot.", "assignee": "internal", "priority": "medium"},
        ],
    },
    notes=(
        "Mike at Cascade Roofing. Back-porch repair quoted at $1800.\n"
        "Offered slot: Thursday AM. Decide + call back."
    ),
)

_add_call(
    call_id="call-pl-002",
    tenant_id="33333333-3333-3333-3333-333333333333",
    direction="inbound",
    contact=None,
    other_party_number="+18005550199",
    started_days_ago=1.0,
    duration_sec=18,
    transcript=[
        ("external", "Hi this is an important call regarding your vehicle's extended warranty. Our records indicate your coverage is about to expire.", 1000),
        ("external", "Press one now to speak with a representative or press two to be removed from our list.", 9000),
    ],
    insights=[
        {
            "template_id": "tpl-pl-spam",
            "template_name": "Likely Spam / Robocall",
            "template_severity": "warning",
            "source": "realtime",
            "confidence": 0.99,
            "evidence": "This is an important call regarding your vehicle's extended warranty.",
        },
    ],
    summary={
        "summary": "A short call consisting only of an automated sales script. No real conversation took place.",
        "sentiment": "neutral",
        "key_topics": ["robocall", "automated sales script"],
        "action_items": [],
    },
    notes="Robocall. Block this number.",
)


# ---------------------------------------------------------------------------
# Lookup helpers used by the demo blueprint
# ---------------------------------------------------------------------------

def list_tenants() -> list[dict[str, Any]]:
    return [
        {
            "id": t["id"],
            "name": t["name"],
            "slug": t["slug"],
            "description": t["description"],
            "tagline": t["tagline"],
            "color": t["color"],
        }
        for t in TENANTS
    ]


def get_tenant(slug: str) -> dict[str, Any] | None:
    for t in TENANTS:
        if t["slug"] == slug:
            return {
                "id": t["id"],
                "name": t["name"],
                "slug": t["slug"],
                "description": t["description"],
                "context": t["context"],
                "organization_id": t["organization_id"],
                "organization_name": t["organization_name"],
                "settings": deepcopy(t["settings"]),
            }
    return None


def get_tenant_by_id(tenant_id: str) -> dict[str, Any] | None:
    for t in TENANTS:
        if t["id"] == tenant_id:
            return t
    return None


def get_org(org_id: str) -> dict[str, Any] | None:
    # All demo tenants live under one fake org. Return a minimal org record.
    for t in TENANTS:
        if t["organization_id"] == org_id:
            return {
                "id": org_id,
                "name": t["organization_name"] or "Demo Org",
                "slug": "demo-org",
                "description": "Synthetic organization grouping the demo tenants.",
            }
    return None


def list_org_tenants(org_id: str) -> list[dict[str, Any]]:
    return [
        {
            "id": t["id"],
            "name": t["name"],
            "slug": t["slug"],
            "description": t["description"],
        }
        for t in TENANTS
        if t["organization_id"] == org_id
    ]


def list_org_numbers(org_id: str) -> list[dict[str, Any]]:
    out = []
    for t in TENANTS:
        if t["organization_id"] != org_id:
            continue
        # One sample number per tenant. Each number is "owned" by the org and
        # assigned to the tenant.
        last = t["id"].split("-")[0][:4]
        out.append({
            "id": f"num-{t['id']}",
            "organization_id": org_id,
            "tenant_id": t["id"],
            "e164": f"+1555{last[:3]}0000"[:12],
            "twilio_sid": f"PN{last}deadbeef",
            "inbound_enabled": True,
            "outbound_enabled": True,
        })
    return out


def list_org_admins(org_id: str) -> list[dict[str, Any]]:
    return [
        {
            "user_id": "demo-user",
            "email": "demo@callisto.example",
            "name": "Demo Visitor",
            "is_admin": True,
        },
    ]


def list_numbers(tenant_id: str) -> list[dict[str, Any]]:
    """Per-tenant phone number list shape for TenantSettingsPage."""
    t = get_tenant_by_id(tenant_id)
    if t is None:
        return []
    last = t["id"].split("-")[0][:4]
    return [
        {
            "id": f"num-{t['id']}",
            "e164": f"+1555{last[:3]}0000"[:12],
            "friendly_name": "Main line",
            "inbound_enabled": True,
            "outbound_enabled": True,
            "sip_username": None,
            "has_sip_user": False,
            "inbound_mode": "forward",
            "inbound_forward_to": "+15555550100",
            "voicemail_mode": "app",
        }
    ]


def list_members(tenant_id: str) -> list[dict[str, Any]]:
    return [
        {
            "user_id": "demo-user",
            "tenant_id": tenant_id,
            "email": "demo@callisto.example",
            "name": "Demo Visitor",
            "is_admin": True,
            "created_at": _iso(120),
        },
    ]


def list_calls(tenant_id: str) -> list[dict[str, Any]]:
    return [c for c in CALLS if c["tenant_id"] == tenant_id]


def get_call(call_id: str) -> dict[str, Any] | None:
    for c in CALLS:
        if c["id"] == call_id:
            # Reflect actual audio availability at request time so the
            # frontend's Call Recording card shows up only when the TTS
            # WAV has been rendered for this call.
            return {**c, "has_recording": _has_call_audio(call_id)}
    return None


def list_transcript(call_id: str) -> list[dict[str, Any]]:
    return TRANSCRIPTS.get(call_id, [])


def list_insights(call_id: str) -> list[dict[str, Any]]:
    return INSIGHTS.get(call_id, [])


def list_summary(call_id: str) -> dict[str, Any] | None:
    return SUMMARIES.get(call_id)


def list_voicemail(call_id: str) -> dict[str, Any] | None:
    vm = VOICEMAILS.get(call_id)
    if vm is None:
        return None
    return {**vm, "has_recording": _has_voicemail_audio(call_id)}


def list_voicemail_transcript(call_id: str) -> list[dict[str, Any]]:
    return VOICEMAIL_TRANSCRIPTS.get(call_id, [])


def list_voicemails(tenant_id: str) -> list[dict[str, Any]]:
    out = []
    for c in CALLS:
        if c["tenant_id"] != tenant_id or not c.get("has_voicemail"):
            continue
        vm = VOICEMAILS.get(c["id"]) or {}
        out.append({
            "call_id": c["id"],
            "external_id": c["external_id"],
            "direction": c["direction"],
            "other_party_number": c["other_party_number"],
            "our_number_friendly_name": c["our_number_friendly_name"],
            "contact_id": c["contact_id"],
            "contact_name": c["contact_name"],
            "contact_company": c["contact_company"],
            "call_started_at": c["started_at"],
            "voicemail_started_at": vm.get("started_at"),
            "voicemail_duration_sec": vm.get("duration_sec"),
            "has_recording": _has_voicemail_audio(c["id"]),
        })
    return out


def list_templates(tenant_id: str) -> list[dict[str, Any]]:
    return TEMPLATES.get(tenant_id, [])


def list_template_categories(tenant_id: str) -> list[dict[str, Any]]:
    return [
        {"id": f"cat-{tenant_id}-{i}", "tenant_id": tenant_id, "name": name}
        for i, name in enumerate(CATEGORIES_BY_TENANT.get(tenant_id, []))
    ]


def _has_call_audio(call_id: str) -> bool:
    try:
        from callisto.demo_audio import call_audio_path
        return call_audio_path(call_id).is_file()
    except Exception:
        return False


def _has_voicemail_audio(call_id: str) -> bool:
    try:
        from callisto.demo_audio import voicemail_audio_path
        return voicemail_audio_path(call_id).is_file()
    except Exception:
        return False


def list_contacts(tenant_id: str) -> list[dict[str, Any]]:
    return CONTACTS.get(tenant_id, [])


def _find_contact(contact_id: str) -> dict[str, Any] | None:
    for items in CONTACTS.values():
        for c in items:
            if c["id"] == contact_id:
                return c
    return None


def get_contact_detail(contact_id: str) -> dict[str, Any] | None:
    """Shape ContactDetailPage expects: contact fields + a calls list +
    sentiment counts + top topics. We derive sentiment + topics from the
    seeded summaries on the contact's own calls."""
    contact = _find_contact(contact_id)
    if contact is None:
        return None

    contact_calls = [c for c in CALLS if c.get("contact_id") == contact_id]
    contact_calls.sort(key=lambda c: c["started_at"], reverse=True)

    sentiment_counts: dict[str, int] = {}
    topic_counts: dict[str, int] = {}
    analyzed = 0
    latest_sentiment: str | None = None
    latest_started: str | None = None
    # contact_calls is already sorted newest first, but be explicit: pick
    # the sentiment from whichever analyzed call has the most recent
    # started_at (not the summary's created_at, which is just when the
    # cold-path finished).
    for c in contact_calls:
        s = SUMMARIES.get(c["id"])
        if s is None:
            continue
        analyzed += 1
        sentiment = s.get("sentiment") or "neutral"
        sentiment_counts[sentiment] = sentiment_counts.get(sentiment, 0) + 1
        for topic in s.get("key_topics", []) or []:
            topic_counts[topic] = topic_counts.get(topic, 0) + 1
        if latest_started is None or c["started_at"] > latest_started:
            latest_started = c["started_at"]
            latest_sentiment = sentiment

    top_topics = sorted(
        topic_counts.items(), key=lambda kv: kv[1], reverse=True
    )[:8]

    return {
        "id": contact["id"],
        "tenant_id": contact["tenant_id"],
        "name": contact["name"],
        "company": contact.get("company"),
        "phone_numbers": contact.get("phone_numbers", []),
        "email": contact.get("email"),
        "google_contact_id": contact.get("google_contact_id"),
        "notes": contact.get("notes"),
        "calls": contact_calls,
        "sentiment_summary": {
            "counts": sentiment_counts,
            "latest": latest_sentiment,
            "total_calls": len(contact_calls),
            "analyzed_calls": analyzed,
        },
        "top_topics": top_topics,
    }


def get_analytics_points(tenant_id: str, days: int = 30) -> list[dict[str, Any]]:
    """Synthetic insight-trend data, flat list shape the AnalyticsPage chart
    expects: [{date, template_id, template_name, count}, ...].

    Each template's signal is built over a 90-day window from two sine
    waves with non-harmonic periods (so they don't realign within the
    window) plus a small linear trend and a deterministic jitter. The
    requested ``days`` is then sliced off the tail of that 90-day
    signal, so a visitor can switch between 7 / 14 / 30 / 90 day views
    and never see the data visibly repeat or look templated.
    """
    import math

    WINDOW = 90
    days = max(1, min(days, WINDOW))
    points: list[dict[str, Any]] = []
    for i, tpl in enumerate(TEMPLATES.get(tenant_id, [])):
        seed = sum(ord(c) for c in tpl["id"])
        baseline = 3 + (seed % 4)                       # 3 to 6
        amp_a = 1.5 + (seed % 3) * 0.5                  # 1.5 to 2.5
        amp_b = 0.7 + ((seed >> 1) % 3) * 0.3           # 0.7 to 1.3
        period_a = 23 + (seed % 11)                     # 23 to 33
        period_b = 7 + ((seed >> 2) % 5)                # 7 to 11 (coprime-ish vs period_a)
        phase_a = (i * 1.7) + (seed % 5) * 0.4
        phase_b = (i * 0.9) + (seed % 7) * 0.3
        # Slow linear drift so the 90-day view shows mild secular trend.
        slope = (((seed >> 3) % 5) - 2) * 0.015         # -0.030 to +0.030 per day

        # Build full 90-day signal first, slice the tail.
        full = []
        for d in range(WINDOW):
            jitter = (((seed * (d + 1)) % 7) - 3) * 0.18  # -0.54 to +0.54
            value = (
                baseline
                + amp_a * math.sin((d * 2 * math.pi / period_a) + phase_a)
                + amp_b * math.sin((d * 2 * math.pi / period_b) + phase_b)
                + slope * d
                + jitter
            )
            full.append(max(0, round(value)))

        tail = full[-days:]
        for offset, count in enumerate(tail):
            date = (
                datetime.now(timezone.utc) - timedelta(days=days - 1 - offset)
            ).date().isoformat()
            points.append({
                "date": date,
                "template_id": tpl["id"],
                "template_name": tpl["name"],
                "count": count,
            })
    return points
