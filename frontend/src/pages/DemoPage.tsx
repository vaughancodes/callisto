import { useEffect, useState } from "react";
import {
  Activity,
  Boxes,
  Code2,
  Database,
  Headphones,
  Layers,
  Mail,
  Mic,
  Network,
  Phone,
  Radio,
  ShieldCheck,
  Sparkles,
  Workflow,
} from "lucide-react";
import { useDocumentTitle } from "../hooks/useDocumentTitle";
import { apiFetch } from "../lib/api";
import { enterDemo } from "../lib/demoMode";

interface DemoTenant {
  id: string;
  name: string;
  slug: string;
  description: string;
  tagline: string;
  color: string;
}

const STACK_BADGES = [
  "Python · Flask",
  "PostgreSQL · JSONB",
  "Redis Streams",
  "Celery (post-call)",
  "WebSockets · Twilio Media Streams",
  "SIP · BYO desk phone or softphone",
  "Deepgram · Whisper",
  "OpenAI-compatible LLMs",
  "React · TypeScript",
  "Docker Compose",
];

const ENGINEERING_CARDS = [
  {
    icon: Workflow,
    title: "Hot path / cold path split",
    body: "Real-time insights run over Redis Streams with a sliding 60-second context window. Heavy post-call analysis (full transcript, multi-pass LLM, sentiment, action items) runs as a Celery chain. The hot path can never block on heavy work.",
  },
  {
    icon: Mic,
    title: "Twilio Media Streams pipeline",
    body: "WSS endpoint accepts forked call audio (mulaw 8 kHz). Decoded, resampled to 16 kHz PCM, routed per-track to Deepgram, and accumulated into a stereo WAV (L=caller, R=internal) for playback.",
  },
  {
    icon: Phone,
    title: "Configurable voicemail",
    body: "Per-number app voicemail with a Dial timeout that beats the carrier. Dial action stamps the voicemail boundary; the existing media stream keeps capturing. Audio served as a sliced mono file aligned to the caller's first transcribed word.",
  },
  {
    icon: Network,
    title: "SIP-compatible (BYO device)",
    body: "Each tenant gets a Twilio SIP Domain provisioned on first credential mint, with a per-number SIP user. Plug a deskphone or softphone into the SIP URI and Callisto routes inbound calls to ring the device, or accepts SIP-originated outbound INVITEs and dials out via the tenant's number as caller ID.",
  },
  {
    icon: ShieldCheck,
    title: "Multi-tenant isolation",
    body: "Column-based tenancy with tenant_id on every table, enforced at the query layer. Hierarchical org → tenant → user permissions, JWT auth, per-tenant LLM context piped into both deep-analysis and summary prompts.",
  },
  {
    icon: Sparkles,
    title: "Bring-your-own insight templates",
    body: "Tenants define what to detect: churn risk, urgent symptoms, robocalls, anything. Templates carry an applies_to constraint (external / internal / both) honored by the LLM and post-filtered against the speaker track.",
  },
  {
    icon: Database,
    title: "Audio retention & cost control",
    body: "Per-tenant audio retention (auto-delete after N days, transcripts retained). LLM cost accounting tallied per call. Greeting upload + serve, sliced voicemail audio, all behind JWT-gated endpoints.",
  },
];


export function DemoPage() {
  useDocumentTitle("Demo");
  const [tenants, setTenants] = useState<DemoTenant[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    apiFetch<{ tenants: DemoTenant[] }>("/api/demo/manifest")
      .then((data) => setTenants(data.tenants))
      .catch((e: Error) => setError(e.message));
    // Fire-and-forget visit ping. The backend rate-limits per IP and
    // fires an ntfy.sh push to my phone if NTFY_DEMO_TOPIC is set.
    fetch("/api/demo/visit", { method: "POST" }).catch(() => {});
  }, []);

  const launch = (slug: string) => {
    enterDemo(slug);
    // Hard reload — AuthProvider runs /auth/me once at mount, so we need
    // a fresh app boot for it to see the new localStorage flag and fetch
    // the synth user from /api/demo/me. A soft navigate() leaves user=null
    // and ProtectedRoute bounces to /login.
    window.location.href = "/";
  };

  return (
    <div className="min-h-screen bg-page-bg text-page-text">
      {/* Logo + wordmark header */}
      <header className="border-b border-card-border">
        <div className="max-w-5xl mx-auto px-6 py-5 flex items-center gap-3">
          <img
            src="/callisto-icon-animated.svg"
            alt=""
            className="w-10 h-10 shrink-0"
          />
          <img
            src="/callisto-wordmark-light.svg"
            alt="Callisto"
            className="h-6 dark:hidden"
          />
          <img
            src="/callisto-wordmark-dark.svg"
            alt="Callisto"
            className="h-6 hidden dark:block"
          />
        </div>
      </header>

      {/* Hero */}
      <section className="px-6 py-16 max-w-5xl mx-auto">
        <div className="flex items-center gap-2 text-xs uppercase tracking-wider text-accent-light mb-4">
          <Headphones className="w-4 h-4" />
          Callisto · interactive demo
        </div>
        <h1 className="text-4xl sm:text-5xl font-bold text-page-text leading-tight">
          A multi-tenant telephony intelligence platform.
          <span className="text-accent-light"> Live audio in, structured insights out.</span>
        </h1>
        <p className="text-lg text-page-text-secondary mt-5 max-w-3xl">
          Real calls fork over Twilio Media Streams into a streaming
          transcription + LLM evaluation pipeline. Tenants bring their own
          insight criteria. Sales teams detect churn risk, clinics route
          urgent symptoms, individuals flag robocalls.
        </p>
        <p className="text-lg text-page-text mt-4 max-w-3xl font-medium">
          The demo is below: pick a tenant, click "Enter sandbox", and
          land in the real Callisto UI populated with seeded data. No
          login.
        </p>

        <div className="flex flex-wrap items-center gap-3 mt-6">
          <a
            href="#sandbox"
            className="inline-flex items-center gap-2 px-4 py-2 bg-brand-sky text-white rounded-lg font-medium hover:bg-brand-sky/90 transition-colors"
          >
            Jump to the sandbox
            <span aria-hidden>↓</span>
          </a>
          <a
            href="#deep-dives"
            className="inline-flex items-center gap-2 px-4 py-2 border border-card-border text-page-text-secondary rounded-lg hover:bg-page-hover transition-colors"
          >
            Or read about the build
          </a>
        </div>

        <div className="flex flex-wrap gap-2 mt-8">
          {STACK_BADGES.map((b) => (
            <span
              key={b}
              className="text-xs px-2.5 py-1 rounded-full bg-card-bg border border-card-border text-page-text-secondary"
            >
              {b}
            </span>
          ))}
        </div>
      </section>

      {/* Sandbox launcher */}
      <section
        id="sandbox"
        className="px-6 py-14 bg-page-bg-tertiary border-y-2 border-brand-sky/40 scroll-mt-4"
      >
        <div className="max-w-5xl mx-auto">
          <div className="inline-flex items-center gap-2 text-xs uppercase tracking-wider text-brand-sky mb-3 font-semibold">
            <span className="w-2 h-2 rounded-full bg-brand-sky animate-pulse" />
            The demo lives here
          </div>
          <h2 className="text-3xl font-bold text-page-text mb-3">
            Pick a sandbox tenant
          </h2>
          <p className="text-base text-page-text-secondary mb-6 max-w-2xl">
            Each tenant lands you in the real Callisto UI populated with
            seeded fake calls, transcripts, insights, summaries, and
            voicemails. Editing is disabled, but everything else (browsing,
            playback, analytics) works exactly as it would for a live
            tenant.
          </p>

          {error && (
            <div className="mb-4 p-3 rounded-lg bg-danger/10 border border-danger/30 text-danger text-sm">
              {error}
            </div>
          )}

          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {tenants.map((t) => (
              <button
                key={t.id}
                type="button"
                onClick={() => launch(t.slug)}
                className="group text-left bg-card-bg border border-card-border rounded-xl p-5 flex flex-col hover:border-brand-sky hover:shadow-lg transition-all"
              >
                <div className={`text-xs uppercase tracking-wide font-semibold text-${t.color} mb-2`}>
                  {t.tagline}
                </div>
                <div className="text-lg font-semibold text-page-text mb-1">
                  {t.name}
                </div>
                <p className="text-sm text-page-text-secondary mb-5">
                  {t.description}
                </p>
                <span className="mt-auto self-start inline-flex items-center gap-1.5 px-3 py-1.5 bg-brand-sky text-white rounded-md font-medium text-sm group-hover:bg-brand-sky/90 transition-colors">
                  Enter sandbox
                  <span className="transition-transform group-hover:translate-x-0.5">
                    →
                  </span>
                </span>
              </button>
            ))}
            {tenants.length === 0 && !error && (
              <div className="col-span-3 p-6 text-center text-page-text-muted text-sm">
                Loading sandbox tenants...
              </div>
            )}
          </div>
        </div>
      </section>

      {/* Engineering deep-dives */}
      <section id="deep-dives" className="px-6 py-14 max-w-5xl mx-auto scroll-mt-4">
        <h2 className="text-2xl font-bold text-page-text mb-2">
          Under the hood
        </h2>
        <p className="text-sm text-page-text-secondary mb-8 max-w-2xl">
          A few of the design decisions that shaped Callisto. The full
          architecture writeup lives in
          <code className="mx-1 px-1.5 py-0.5 text-xs bg-card-bg border border-card-border rounded">
            ARCHITECTURE.md
          </code>
          on GitHub.
        </p>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {ENGINEERING_CARDS.map((c) => (
            <div
              key={c.title}
              className="bg-card-bg border border-card-border rounded-xl p-5"
            >
              <div className="flex items-center gap-2 mb-2">
                <c.icon className="w-4 h-4 text-accent-light" />
                <h3 className="font-semibold text-page-text">{c.title}</h3>
              </div>
              <p className="text-sm text-page-text-secondary">{c.body}</p>
            </div>
          ))}
        </div>
      </section>

      {/* Pipeline strip */}
      <section className="px-6 py-12 bg-page-bg-tertiary border-y border-card-border">
        <div className="max-w-5xl mx-auto">
          <h2 className="text-2xl font-bold text-page-text mb-6">
            Request flow
          </h2>
          <div className="grid grid-cols-1 md:grid-cols-5 gap-3 text-sm">
            {[
              { icon: Phone, label: "Twilio call", sub: "TwiML routes audio" },
              { icon: Radio, label: "WSS ingestion", sub: "mulaw → 16 kHz PCM" },
              { icon: Activity, label: "Deepgram", sub: "per-track streaming STT" },
              { icon: Layers, label: "Hot path", sub: "Redis Streams + LLM" },
              { icon: Boxes, label: "Cold path", sub: "Celery: deep + summary" },
            ].map((s) => (
              <div
                key={s.label}
                className="bg-card-bg border border-card-border rounded-lg p-4 text-center"
              >
                <s.icon className="w-5 h-5 mx-auto text-brand-sky mb-2" />
                <div className="font-medium text-page-text">{s.label}</div>
                <div className="text-xs text-page-text-muted mt-1">
                  {s.sub}
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* About */}
      <section className="px-6 py-14 max-w-5xl mx-auto">
        <h2 className="text-2xl font-bold text-page-text mb-2">
          About this project
        </h2>
        <p className="text-sm text-page-text-secondary max-w-3xl">
          Callisto is a personal project built end-to-end by
          <span className="font-semibold text-page-text"> Daniel Vaughan</span>.
          The same codebase covers the Twilio webhook layer, the WebSocket
          ingestion gateway, the streaming and batched STT integrations,
          the multi-tenant Flask API, the Celery cold-path pipeline, the
          React + Tailwind frontend, and the Docker Compose dev
          environment.
        </p>
        <div className="flex flex-wrap gap-3 mt-6 text-sm">
          <a
            href="https://github.com/vaughancodes/callisto"
            target="_blank"
            rel="noreferrer"
            className="inline-flex items-center gap-1.5 px-3 py-2 border border-card-border rounded-lg hover:bg-page-hover"
          >
            <Code2 className="w-4 h-4" /> GitHub
          </a>
          <a
            href="https://www.linkedin.com/in/vaughancodes"
            target="_blank"
            rel="noreferrer"
            className="inline-flex items-center gap-1.5 px-3 py-2 border border-card-border rounded-lg hover:bg-page-hover"
          >
            LinkedIn
          </a>
          <a
            href="mailto:daniel@vaughan.codes"
            className="inline-flex items-center gap-1.5 px-3 py-2 border border-card-border rounded-lg hover:bg-page-hover"
          >
            <Mail className="w-4 h-4" /> Email
          </a>
          <a
            href="https://callisto.works"
            target="_blank"
            rel="noreferrer"
            className="inline-flex items-center gap-1.5 px-3 py-2 border border-card-border rounded-lg hover:bg-page-hover"
          >
            <Code2 className="w-4 h-4" /> Marketing site
          </a>
        </div>
      </section>

      <footer className="px-6 py-8 border-t border-card-border text-xs text-page-text-muted text-center">
        Callisto · /demo · seeded read-only data, no real Twilio or LLM
        calls are made from this page.
      </footer>
    </div>
  );
}
