import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, AudioLines, RefreshCw, Voicemail } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { PhoneLink } from "../components/LinkedContact";
import { PageLoadingSpinner } from "../components/LoadingSpinner";
import { useActiveTranscriptChunk } from "../hooks/useActiveTranscriptChunk";
import { useAuthedAudio } from "../hooks/useAuthedAudio";
import { useDocumentTitle } from "../hooks/useDocumentTitle";
import { useInsightStream } from "../hooks/useWebSocket";
import { apiFetch } from "../lib/api";
import { capitalize, formatDateTime, formatInsightSource, formatStatus } from "../lib/format";

interface TranscriptChunk {
  speaker: string;
  text: string;
  start_ms: number;
  end_ms: number;
  confidence: number;
  chunk_index: number;
}

interface InsightData {
  id: string;
  template_id: string;
  template_name: string | null;
  template_severity: string | null;
  source: string;
  detected_at: string;
  confidence: number;
  evidence: string;
  result: { reasoning?: string };
  transcript_range: { start_ms?: number; end_ms?: number } | null;
}

interface SummaryData {
  summary: string;
  sentiment: string;
  key_topics: string[];
  action_items: { text: string; assignee: string; priority: string }[];
  token_cost: number;
}

interface CallData {
  id: string;
  caller_number: string;
  callee_number?: string;
  other_party_number?: string | null;
  contact_id: string | null;
  contact_name: string | null;
  contact_company: string | null;
  direction: string;
  status: string;
  started_at: string;
  ended_at: string | null;
  duration_sec: number | null;
  notes: string | null;
  has_voicemail?: boolean;
  has_recording?: boolean;
}

interface VoicemailData {
  started_at: string;
  started_at_ms: number;
  dial_status: string | null;
  duration_sec: number | null;
  has_recording: boolean;
  transcript: TranscriptChunk[];
}

function formatTime(ms: number): string {
  const s = Math.floor(ms / 1000);
  const m = Math.floor(s / 60);
  const sec = s % 60;
  return `${m}:${sec.toString().padStart(2, "0")}`;
}

const sentimentColors: Record<string, string> = {
  positive: "bg-success/15 text-success",
  negative: "bg-danger/15 text-danger",
  neutral: "bg-page-divider text-page-text",
  mixed: "bg-warning/15 text-warning",
};

export function CallDetailPage() {
  const { callId } = useParams<{ callId: string }>();
  const navigate = useNavigate();
  const liveInsights = useInsightStream(callId);
  const queryClient = useQueryClient();
  const [editingNotes, setEditingNotes] = useState(false);

  const { data: call, isLoading: callLoading } = useQuery({
    queryKey: ["call", callId],
    queryFn: () => apiFetch<CallData>(`/api/v1/calls/${callId}`),
    refetchInterval: (query) => {
      const s = query.state.data?.status;
      return s === "active" || s === "processing" ? 3000 : false;
    },
  });

  const otherPartyNumber = call?.other_party_number ?? call?.caller_number ?? "";

  useDocumentTitle(
    call ? `${call.contact_name ?? otherPartyNumber} call` : "Call"
  );

  const notesFromServer = call?.notes ?? "";
  const [notesText, setNotesText] = useState(notesFromServer);
  // Sync when server data arrives or changes
  const [lastSynced, setLastSynced] = useState("");
  if (notesFromServer !== lastSynced && !editingNotes) {
    setNotesText(notesFromServer);
    setLastSynced(notesFromServer);
  }

  const isInFlight = call?.status === "active" || call?.status === "processing";

  // When the call leaves "processing" (i.e. the cold-path worker just
  // finished), force summary + insights to refetch. Their own polling stops
  // the moment status flips, and the last poll may have fired before the
  // worker committed the new rows — without this invalidation the page can
  // be left showing the pre-reanalysis summary.
  const prevStatusRef = useRef<string | undefined>(undefined);
  useEffect(() => {
    const prev = prevStatusRef.current;
    const current = call?.status;
    if (prev === "processing" && current && current !== "processing") {
      queryClient.invalidateQueries({ queryKey: ["summary", callId] });
      queryClient.invalidateQueries({ queryKey: ["insights", callId] });
    }
    prevStatusRef.current = current;
  }, [call?.status, callId, queryClient]);

  const { data: transcript, isLoading: transcriptLoading } = useQuery({
    queryKey: ["transcript", callId],
    queryFn: () =>
      apiFetch<TranscriptChunk[]>(`/api/v1/calls/${callId}/transcript`),
    refetchInterval: call?.status === "active" ? 5000 : false,
  });

  const { data: insights, isLoading: insightsLoading } = useQuery({
    queryKey: ["insights", callId],
    queryFn: () =>
      apiFetch<InsightData[]>(`/api/v1/calls/${callId}/insights`),
    refetchInterval: isInFlight ? 3000 : false,
  });

  const { data: summary } = useQuery({
    queryKey: ["summary", callId],
    queryFn: () =>
      apiFetch<SummaryData>(`/api/v1/calls/${callId}/summary`),
    enabled: call?.status === "completed" || call?.status === "processing",
    refetchInterval: call?.status === "processing" ? 3000 : false,
    retry: false,
  });

  const { data: voicemail } = useQuery({
    queryKey: ["voicemail", callId],
    queryFn: () =>
      apiFetch<VoicemailData>(`/api/v1/calls/${callId}/voicemail`),
    enabled: !!call?.has_voicemail,
    retry: false,
  });

  const callAudioUrl = useAuthedAudio(
    call?.has_recording ? `/api/v1/calls/${callId}/audio` : null
  );
  // useState (not useRef) so the hook re-subscribes when the conditionally-
  // rendered <audio> element mounts after the blob URL loads.
  const [callAudioEl, setCallAudioEl] = useState<HTMLAudioElement | null>(null);
  const activeFullIdx = useActiveTranscriptChunk(callAudioEl, transcript, 0);
  const activeVoicemailIdx = useActiveTranscriptChunk(
    callAudioEl,
    voicemail?.transcript,
    0
  );

  const saveNotes = useMutation({
    mutationFn: (notes: string) =>
      apiFetch(`/api/v1/calls/${callId}/notes`, {
        method: "PUT",
        body: JSON.stringify({ notes }),
      }),
    onSuccess: () => {
      setEditingNotes(false);
      queryClient.invalidateQueries({ queryKey: ["call", callId] });
    },
  });

  const [reanalyzeError, setReanalyzeError] = useState<string | null>(null);
  const reanalyze = useMutation({
    mutationFn: () =>
      apiFetch(`/api/v1/calls/${callId}/reanalyze`, { method: "POST" }),
    onSuccess: () => {
      setReanalyzeError(null);
      // Nudge the call query so polling picks up the new "processing" status
      // immediately rather than waiting for the next tick.
      queryClient.invalidateQueries({ queryKey: ["call", callId] });
    },
    onError: (err: Error) => {
      const match = err.message.match(/API error \d+: (.*)/);
      let msg = err.message;
      if (match) {
        try {
          const parsed = JSON.parse(match[1]);
          if (parsed?.error) msg = parsed.error;
        } catch {
          /* fall through */
        }
      }
      setReanalyzeError(msg);
      setTimeout(() => setReanalyzeError(null), 6000);
    },
  });

  const direction = call?.direction
    ? (call.direction.startsWith("outbound") ? "Outbound" : "Inbound")
    : "";

  if (callLoading || transcriptLoading || insightsLoading) {
    return <PageLoadingSpinner />;
  }

  return (
    <div className="p-6">
      {/* Header */}
      <div className="flex items-start gap-4 mb-6">
        <button
          onClick={() => navigate(-1)}
          className="p-2 hover:bg-page-hover rounded-lg transition-colors shrink-0 mt-0.5"
        >
          <ArrowLeft className="w-5 h-5 text-page-text" />
        </button>
        <div className="flex-1 min-w-0">
          <h2 className="text-2xl font-bold text-page-text">
            {call?.contact_name ? (
              call.contact_id ? (
                <Link
                  to={`/contacts/${call.contact_id}`}
                  className="text-brand-sky hover:underline"
                >
                  {call.contact_name}
                </Link>
              ) : (
                call.contact_name
              )
            ) : otherPartyNumber ? (
              <PhoneLink number={otherPartyNumber} />
            ) : (
              "Loading..."
            )}
          </h2>
          <div className="flex items-center gap-2 mt-0.5">
            {call?.contact_name && (
              <span className="text-sm text-page-text-secondary">
                <PhoneLink number={otherPartyNumber} />
              </span>
            )}
            {call?.contact_company && (
              <span className="text-sm text-page-text-muted">
                &middot; {call.contact_company}
              </span>
            )}
          </div>
          <p className="text-sm text-page-text-secondary mt-0.5">
            {direction} call &middot; {call ? formatStatus(call.status) : ""}
            {call?.duration_sec != null &&
              ` · ${Math.floor(call.duration_sec / 60)}m ${call.duration_sec % 60}s`}
            {call?.started_at && ` · ${formatDateTime(call.started_at)}`}
          </p>
        </div>
        {(call?.status === "completed" || call?.status === "processing") && (
          <div className="flex flex-col items-end gap-1 shrink-0">
            <button
              onClick={() => reanalyze.mutate()}
              disabled={reanalyze.isPending || call?.status === "processing"}
              title="Re-run deep analysis and summary with the current templates and context"
              className="flex items-center gap-2 px-3 py-2 bg-card-bg border border-card-border rounded-lg hover:bg-page-hover text-sm text-page-text disabled:opacity-50"
            >
              <RefreshCw
                className={`w-4 h-4 ${
                  reanalyze.isPending || call?.status === "processing"
                    ? "animate-spin"
                    : ""
                }`}
              />
              {call?.status === "processing"
                ? "Analyzing..."
                : reanalyze.isPending
                  ? "Queuing..."
                  : "Re-analyze"}
            </button>
            {reanalyzeError && (
              <span className="text-xs text-danger max-w-xs text-right">
                {reanalyzeError}
              </span>
            )}
          </div>
        )}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-5 gap-6">
        {/* Transcript */}
        <div className="lg:col-span-3 space-y-6">
          {call?.has_recording && (
            <div className="bg-card-bg rounded-lg border border-card-border">
              <div className="p-4 border-b border-card-border flex items-center gap-2">
                <AudioLines className="w-4 h-4 text-brand-sky" />
                <h3 className="font-semibold text-page-text">
                  Call Recording
                </h3>
                {call.duration_sec != null && (
                  <span className="text-xs text-page-text-muted">
                    {call.duration_sec}s
                  </span>
                )}
              </div>
              <div className="p-4">
                {callAudioUrl ? (
                  <audio
                    ref={setCallAudioEl}
                    controls
                    preload="metadata"
                    src={callAudioUrl}
                    className="w-full"
                  />
                ) : (
                  <p className="text-sm text-page-text-muted">
                    Loading recording...
                  </p>
                )}
                {voicemail?.started_at_ms != null && (
                  <p className="text-xs text-page-text-muted mt-2">
                    <Voicemail className="w-3 h-3 inline mr-1 text-accent-lavender" />
                    Voicemail starts at {formatTime(voicemail.started_at_ms)}.
                  </p>
                )}
              </div>
            </div>
          )}
          {voicemail && voicemail.transcript.length > 0 && (
            <div className="bg-card-bg rounded-lg border border-card-border">
              <div className="p-4 border-b border-card-border flex items-center gap-2">
                <Voicemail className="w-4 h-4 text-accent-lavender" />
                <h3 className="font-semibold text-page-text">
                  Voicemail Transcript
                </h3>
                {voicemail.duration_sec != null && (
                  <span className="text-xs text-page-text-muted">
                    {voicemail.duration_sec}s
                  </span>
                )}
              </div>
              <div className="p-4 max-h-[260px] overflow-auto space-y-2">
                {voicemail.transcript.map((chunk, i) => {
                  const active = i === activeVoicemailIdx;
                  const seek = () => {
                    if (callAudioEl) {
                      callAudioEl.currentTime = chunk.start_ms / 1000;
                      void callAudioEl.play().catch(() => {});
                    }
                  };
                  return (
                    <div
                      key={`vm-${chunk.chunk_index}-${i}`}
                      ref={(el) => {
                        if (active && el) {
                          el.scrollIntoView({ block: "nearest", behavior: "smooth" });
                        }
                      }}
                      role="button"
                      tabIndex={0}
                      onClick={seek}
                      onKeyDown={(e) => {
                        if (e.key === "Enter" || e.key === " ") {
                          e.preventDefault();
                          seek();
                        }
                      }}
                      className={`flex gap-3 px-2 py-1 -mx-2 rounded transition-colors cursor-pointer hover:bg-page-hover ${
                        active
                          ? "bg-brand-sky/10 border-l-2 border-brand-sky"
                          : "border-l-2 border-transparent"
                      }`}
                    >
                      <span className="text-xs text-page-text-muted w-12 shrink-0 pt-0.5 text-right">
                        {formatTime(chunk.start_ms - voicemail.started_at_ms)}
                      </span>
                      <span className="text-sm text-page-text flex-1 min-w-0">
                        {chunk.text}
                      </span>
                    </div>
                  );
                })}
              </div>
            </div>
          )}
          {!call?.has_voicemail && (
          <div className="bg-card-bg rounded-lg border border-card-border">
            <div className="p-4 border-b border-card-border">
              <h3 className="font-semibold text-page-text">Transcript</h3>
            </div>
            <div className="p-4 max-h-[600px] overflow-auto space-y-3">
              {transcript?.map((chunk, i) => {
                const active = i === activeFullIdx;
                const seek = () => {
                  if (callAudioEl) {
                    callAudioEl.currentTime = chunk.start_ms / 1000;
                    void callAudioEl.play().catch(() => {});
                  }
                };
                return (
                  <div
                    key={`${chunk.chunk_index}-${i}`}
                    ref={(el) => {
                      if (active && el) {
                        el.scrollIntoView({ block: "nearest", behavior: "smooth" });
                      }
                    }}
                    role="button"
                    tabIndex={0}
                    onClick={seek}
                    onKeyDown={(e) => {
                      if (e.key === "Enter" || e.key === " ") {
                        e.preventDefault();
                        seek();
                      }
                    }}
                    className={`flex gap-3 px-2 py-1 -mx-2 rounded transition-colors cursor-pointer hover:bg-page-hover ${
                      active
                        ? "bg-brand-sky/10 border-l-2 border-brand-sky"
                        : "border-l-2 border-transparent"
                    }`}
                  >
                    <span className="text-xs text-page-text-muted w-12 shrink-0 pt-0.5 text-right">
                      {formatTime(chunk.start_ms)}
                    </span>
                    <div className="flex-1 min-w-0">
                      {chunk.speaker && chunk.speaker !== "unknown" && (
                        <span
                          className={`text-[10px] uppercase font-semibold tracking-wide mr-2 ${
                            chunk.speaker === "external"
                              ? "text-accent-light"
                              : chunk.speaker === "internal"
                                ? "text-accent-periwinkle"
                                : "text-page-text-muted"
                          }`}
                        >
                          {chunk.speaker}
                        </span>
                      )}
                      <span className="text-sm text-page-text">
                        {chunk.text}
                      </span>
                    </div>
                  </div>
                );
              })}
              {(!transcript || transcript.length === 0) && (
                <p className="text-page-text-muted text-sm text-center py-4">
                  No transcript available
                </p>
              )}
            </div>
          </div>
          )}

          {/* Notes */}
          <div className="bg-card-bg rounded-lg border border-card-border">
            <div className="p-4 border-b border-card-border">
              <h3 className="font-semibold text-page-text">Notes</h3>
            </div>
            <div className="p-4">
              {editingNotes ? (
                <div className="space-y-2">
                  <textarea
                    value={notesText}
                    onChange={(e) => setNotesText(e.target.value)}
                    rows={4}
                    className="w-full px-3 py-2 text-sm border border-card-border rounded-lg bg-page-bg-tertiary text-page-text placeholder:text-page-text-muted"
                    autoFocus
                  />
                  <div className="flex gap-2">
                    <button
                      onClick={() => saveNotes.mutate(notesText)}
                      className="px-3 py-1.5 text-sm bg-brand-sky text-white rounded-lg hover:bg-brand-sky/80"
                    >
                      Save
                    </button>
                    <button
                      onClick={() => {
                        setEditingNotes(false);
                        setNotesText(call?.notes ?? "");
                      }}
                      className="px-3 py-1.5 text-sm text-page-text-secondary hover:bg-page-hover rounded-lg"
                    >
                      Cancel
                    </button>
                  </div>
                </div>
              ) : (
                <div
                  onClick={() => setEditingNotes(true)}
                  className="text-sm text-page-text-secondary cursor-pointer hover:bg-page-hover rounded p-2 -m-2 min-h-[3rem] whitespace-pre-wrap"
                >
                  {call?.notes || (
                    <span className="text-page-text-muted italic">
                      Click to add notes...
                    </span>
                  )}
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Insights + Summary */}
        <div className="lg:col-span-2 space-y-6">
          <div className="bg-card-bg rounded-lg border border-card-border">
            <div className="p-4 border-b border-card-border">
              <h3 className="font-semibold text-page-text">
                Insights ({(insights?.length ?? 0) + liveInsights.length})
              </h3>
            </div>
            <div className="divide-y divide-page-divider max-h-80 overflow-auto">
              {liveInsights.map((ins) => (
                <div
                  key={ins.insight_id}
                  className="p-3 bg-brand-sky/5 border-l-2 border-brand-sky"
                >
                  <div className="flex items-center gap-2">
                    <span className="text-xs font-medium text-brand-sky uppercase">
                      Live
                    </span>
                    <span className="text-sm font-medium text-page-text">
                      {ins.template_name}
                    </span>
                    <span className="text-xs text-page-text-muted ml-auto">
                      {Math.round(ins.confidence * 100)}%
                    </span>
                  </div>
                  <p className="text-xs text-page-text-secondary mt-1">{ins.evidence}</p>
                </div>
              ))}
              {insights?.map((ins) => (
                <div key={ins.id} className="p-3">
                  <div className="flex items-center gap-2">
                    <span
                      className={`text-xs px-1.5 py-0.5 rounded shrink-0 ${
                        ins.source === "realtime"
                          ? "bg-brand-sky/10 text-brand-sky"
                          : "bg-page-divider text-page-text-secondary"
                      }`}
                    >
                      {formatInsightSource(ins.source)}
                    </span>
                    <span className="text-sm font-medium text-page-text flex-1 truncate">
                      {ins.template_name ?? "Unknown template"}
                    </span>
                    {ins.confidence > 0 && (
                      <span className="text-xs text-page-text-muted shrink-0">
                        {Math.round(ins.confidence * 100)}%
                      </span>
                    )}
                  </div>
                  <p className="text-xs text-page-text-secondary mt-1 italic">
                    &ldquo;{ins.evidence}&rdquo;
                  </p>
                  {ins.result?.reasoning && (
                    <p className="text-xs text-page-text-muted mt-1">
                      {ins.result.reasoning}
                    </p>
                  )}
                </div>
              ))}
              {(insights?.length ?? 0) + liveInsights.length === 0 && (
                <p className="p-4 text-page-text-muted text-sm text-center">
                  No insights detected
                </p>
              )}
            </div>
          </div>

          {/* Summary */}
          {summary && (
            <div className="bg-card-bg rounded-lg border border-card-border">
              <div className="p-4 border-b border-card-border">
                <div className="flex items-center justify-between">
                  <h3 className="font-semibold text-page-text">Summary</h3>
                  <span
                    className={`text-xs px-2 py-0.5 rounded-full ${sentimentColors[summary.sentiment] ?? sentimentColors.neutral}`}
                  >
                    {capitalize(summary.sentiment)}
                  </span>
                </div>
              </div>
              <div className="p-4 space-y-4">
                <p className="text-sm text-page-text">{summary.summary}</p>

                {summary.key_topics.length > 0 && (
                  <div>
                    <h4 className="text-xs font-semibold text-page-text-secondary uppercase mb-2">
                      Topics
                    </h4>
                    <div className="flex flex-wrap gap-1">
                      {summary.key_topics.map((t) => (
                        <span
                          key={t}
                          className="text-xs px-2 py-0.5 bg-page-divider text-page-text-secondary rounded"
                        >
                          {t}
                        </span>
                      ))}
                    </div>
                  </div>
                )}

                {summary.action_items.length > 0 && (
                  <div>
                    <h4 className="text-xs font-semibold text-page-text-secondary uppercase mb-2">
                      Action Items
                    </h4>
                    <ul className="space-y-1">
                      {summary.action_items.map((item, i) => (
                        <li
                          key={i}
                          className="text-sm text-page-text flex gap-2"
                        >
                          <span
                            className={`text-xs px-1.5 py-0.5 rounded self-start ${
                              item.priority === "high"
                                ? "bg-danger/15 text-danger"
                                : item.priority === "medium"
                                  ? "bg-warning/15 text-yellow-600"
                                  : "bg-page-divider text-page-text-secondary"
                            }`}
                          >
                            {capitalize(item.priority)}
                          </span>
                          <span>{item.text}</span>
                        </li>
                      ))}
                    </ul>
                  </div>
                )}

                <p className="text-xs text-page-text-muted">
                  {summary.token_cost} tokens
                </p>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
