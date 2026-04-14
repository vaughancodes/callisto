import {
  ArrowRight,
  Brain,
  Building2,
  Cpu,
  LineChart,
  Radio,
  ShieldCheck,
  Waves,
} from "lucide-react";

function GithubIcon({ className }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="currentColor"
      className={className}
      aria-hidden="true"
    >
      <path d="M12 .5C5.65.5.5 5.65.5 12c0 5.08 3.29 9.39 7.86 10.91.58.11.79-.25.79-.56 0-.27-.01-1-.02-1.96-3.2.69-3.87-1.54-3.87-1.54-.52-1.33-1.28-1.69-1.28-1.69-1.05-.72.08-.71.08-.71 1.16.08 1.77 1.19 1.77 1.19 1.03 1.76 2.7 1.25 3.36.96.1-.75.4-1.25.73-1.54-2.55-.29-5.24-1.28-5.24-5.69 0-1.26.45-2.29 1.18-3.09-.12-.29-.51-1.46.11-3.05 0 0 .97-.31 3.18 1.18a11.04 11.04 0 0 1 5.79 0c2.21-1.49 3.18-1.18 3.18-1.18.62 1.59.23 2.76.11 3.05.74.8 1.18 1.83 1.18 3.09 0 4.42-2.69 5.39-5.26 5.68.41.36.78 1.06.78 2.14 0 1.55-.01 2.8-.01 3.18 0 .31.21.68.8.56C20.21 21.39 23.5 17.07 23.5 12 23.5 5.65 18.35.5 12 .5z" />
    </svg>
  );
}

const APP_URL = "https://app.callisto.works";

const features = [
  {
    icon: Radio,
    title: "Real-time transcription",
    body: "Two-track streaming pulls speaker-diarized text off live Twilio calls with sub-second latency, inbound or outbound.",
  },
  {
    icon: Brain,
    title: "Configurable LLM insights",
    body: "Write detection rules in plain English. Any OpenAI-compatible model evaluates them against a sliding window of the conversation as it unfolds.",
  },
  {
    icon: Waves,
    title: "Live dashboards",
    body: "Detected insights stream to the app the moment they fire, so your team sees what matters before the call ends.",
  },
  {
    icon: LineChart,
    title: "Deep post-call analysis",
    body: "Every completed call gets a full-transcript LLM pass: summary, sentiment, key topics, action items, and cost accounting.",
  },
  {
    icon: Building2,
    title: "Multi-tenant by design",
    body: "Tenant isolation, per-tenant context, member management, and Google OAuth login built in from day one.",
  },
  {
    icon: Cpu,
    title: "Plug in any LLM",
    body: "Run a model on your own hardware or through a provider you already have an account with. Callisto doesn't lock you into either.",
  },
];

const flow = [
  {
    step: "1",
    title: "A call connects",
    body: "Whether your team is taking the call or making it, Callisto starts listening the moment the line opens. No extra software for your agents to install or remember to turn on.",
  },
  {
    step: "2",
    title: "It watches for what matters to you",
    body: "You decide what's worth flagging: a missed follow-up, a pricing question, a compliance phrase, a frustrated customer. Callisto checks for it as the conversation unfolds and pings the dashboard the moment it sees one.",
  },
  {
    step: "3",
    title: "The call ends, the write-up is already done",
    body: "By the time your agent hangs up, there's a summary, a sentiment read, the key topics, and a list of action items waiting in their queue. No more ten minutes of post-call notes per call.",
  },
];

export default function App() {
  return (
    <div className="min-h-screen bg-surface-dark text-text-primary overflow-x-hidden">
      {/* Glow backdrop */}
      <div className="pointer-events-none fixed inset-0 -z-10">
        <div className="absolute top-[-10%] left-1/2 -translate-x-1/2 w-[1100px] h-[1100px] rounded-full bg-brand-sky/10 blur-[160px]" />
        <div className="absolute top-[40%] right-[-10%] w-[800px] h-[800px] rounded-full bg-accent-periwinkle/10 blur-[160px]" />
        <div className="absolute bottom-[-15%] left-[-10%] w-[700px] h-[700px] rounded-full bg-accent-lavender/10 blur-[160px]" />
      </div>

      {/* Nav */}
      <header className="max-w-6xl mx-auto px-6 py-6 flex items-center justify-between">
        <a href="/" className="flex items-center gap-3">
          <img
            src="/callisto-icon-animated.svg"
            alt=""
            className="w-9 h-9"
          />
          <img
            src="/callisto-wordmark-dark.svg"
            alt="Callisto"
            className="h-7"
          />
        </a>
        <nav className="flex items-center gap-6">
          <a
            href="#features"
            className="hidden sm:inline text-sm text-text-secondary hover:text-text-primary transition-colors"
          >
            Features
          </a>
          <a
            href="#how"
            className="hidden sm:inline text-sm text-text-secondary hover:text-text-primary transition-colors"
          >
            How it works
          </a>
          <a
            href={APP_URL}
            className="text-sm font-medium text-white bg-brand-sky/90 hover:bg-brand-sky px-4 py-2 rounded-lg transition-colors"
          >
            Open the app
          </a>
        </nav>
      </header>

      {/* Hero */}
      <section className="max-w-6xl mx-auto px-6 pt-20 pb-32 text-center">
        <div className="flex justify-center mb-10">
          <img
            src="/callisto-icon-animated.svg"
            alt=""
            className="w-44 h-44 drop-shadow-[0_0_60px_rgba(14,165,233,0.35)]"
          />
        </div>
        <h1 className="text-5xl sm:text-6xl font-bold tracking-tight leading-[1.05]">
          Telephony intelligence,
          <br />
          <span className="bg-gradient-to-r from-brand-sky via-accent-periwinkle to-accent-lavender bg-clip-text text-transparent">
            in real time.
          </span>
        </h1>
        <p className="mt-7 text-lg text-text-secondary max-w-2xl mx-auto leading-relaxed">
          Callisto listens to live phone calls, transcribes them as they happen,
          and runs your own natural-language detection rules through the LLM of
          your choice, so the insights show up while the conversation is still
          on the line.
        </p>
        <div className="mt-10 flex flex-wrap justify-center gap-4">
          <a
            href={APP_URL}
            className="group inline-flex items-center gap-2 px-6 py-3 bg-brand-sky text-white rounded-lg font-medium hover:bg-brand-sky/90 transition-colors"
          >
            Launch the dashboard
            <ArrowRight className="w-4 h-4 group-hover:translate-x-0.5 transition-transform" />
          </a>
          <a
            href="#features"
            className="inline-flex items-center gap-2 px-6 py-3 border border-surface-border text-text-primary rounded-lg font-medium hover:bg-surface-elevated transition-colors"
          >
            See what it does
          </a>
        </div>
      </section>

      {/* Features */}
      <section id="features" className="max-w-6xl mx-auto px-6 pb-28">
        <div className="text-center mb-16">
          <h2 className="text-3xl sm:text-4xl font-bold tracking-tight">
            Everything that happens on the call,
            <br />
            <span className="text-text-secondary font-semibold">
              while it's still happening.
            </span>
          </h2>
        </div>
        <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-5">
          {features.map((f) => (
            <div
              key={f.title}
              className="rounded-xl border border-surface-border bg-surface-elevated/60 backdrop-blur-sm p-6 hover:border-brand-sky/40 transition-colors"
            >
              <div className="w-10 h-10 rounded-lg bg-brand-sky/15 text-brand-sky flex items-center justify-center mb-4">
                <f.icon className="w-5 h-5" />
              </div>
              <h3 className="text-lg font-semibold text-text-primary mb-2">
                {f.title}
              </h3>
              <p className="text-sm text-text-secondary leading-relaxed">
                {f.body}
              </p>
            </div>
          ))}
        </div>
      </section>

      {/* How it works */}
      <section
        id="how"
        className="max-w-6xl mx-auto px-6 pb-28"
      >
        <div className="rounded-2xl border border-surface-border bg-surface-elevated/40 backdrop-blur-sm p-8 sm:p-12">
          <div className="text-center mb-12">
            <h2 className="text-3xl sm:text-4xl font-bold tracking-tight mb-4">
              From the first hello to the post-call write-up.
            </h2>
            <p className="text-text-secondary max-w-2xl mx-auto leading-relaxed">
              Callisto sits quietly between your phone system and your team,
              turning every conversation into something you can actually act on
              without changing how anyone works.
            </p>
          </div>
          <div className="grid md:grid-cols-3 gap-5">
            {flow.map((f) => (
              <div
                key={f.step}
                className="rounded-xl border border-surface-border bg-surface-dark/60 p-6"
              >
                <div className="w-9 h-9 rounded-full bg-brand-sky/15 text-brand-sky flex items-center justify-center text-sm font-semibold mb-4">
                  {f.step}
                </div>
                <h3 className="text-lg font-semibold text-text-primary mb-2">
                  {f.title}
                </h3>
                <p className="text-sm text-text-secondary leading-relaxed">
                  {f.body}
                </p>
              </div>
            ))}
          </div>
          <div className="mt-10 flex items-center justify-center gap-2 text-sm text-text-muted">
            <ShieldCheck className="w-4 h-4 text-accent-periwinkle" />
            Your servers or ours. Your call(s).
          </div>
        </div>
      </section>

      {/* CTA */}
      <section className="max-w-4xl mx-auto px-6 pb-28 text-center">
        <h2 className="text-3xl sm:text-4xl font-bold tracking-tight mb-5">
          Ready to listen in on what your calls are actually saying?
        </h2>
        <p className="text-text-secondary max-w-xl mx-auto mb-8">
          Sign in with Google and start defining insights against your own
          calls in minutes.
        </p>
        <a
          href={APP_URL}
          className="group inline-flex items-center gap-2 px-7 py-3.5 bg-brand-sky text-white rounded-lg font-medium hover:bg-brand-sky/90 transition-colors"
        >
          Open the app
          <ArrowRight className="w-4 h-4 group-hover:translate-x-0.5 transition-transform" />
        </a>
      </section>

      {/* Footer */}
      <footer className="border-t border-surface-border">
        <div className="max-w-6xl mx-auto px-6 py-8 flex flex-col sm:flex-row items-center justify-between gap-4">
          <div className="flex items-center gap-2 text-sm text-text-muted">
            <img
              src="/callisto-icon-static.svg"
              alt=""
              className="w-5 h-5 opacity-80"
            />
            © {new Date().getFullYear()} Vaughan.Codes. All rights reserved.
          </div>
          <div className="flex items-center gap-5 text-sm text-text-muted">
            <a
              href={APP_URL}
              className="hover:text-text-primary transition-colors"
            >
              app.callisto.works
            </a>
            <a
              href="https://github.com/vaughancodes/callisto"
              className="flex items-center gap-1.5 hover:text-text-primary transition-colors"
            >
              <GithubIcon className="w-4 h-4" />
              GitHub
            </a>
          </div>
        </div>
      </footer>
    </div>
  );
}
