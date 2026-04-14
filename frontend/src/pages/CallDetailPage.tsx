import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft } from "lucide-react";
import { useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { PhoneLink } from "../components/LinkedContact";
import { PageLoadingSpinner } from "../components/LoadingSpinner";
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
  contact_id: string | null;
  contact_name: string | null;
  contact_company: string | null;
  direction: string;
  status: string;
  started_at: string;
  ended_at: string | null;
  duration_sec: number | null;
  notes: string | null;
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
  });

  useDocumentTitle(
    call ? `${call.contact_name ?? call.caller_number} call` : "Call"
  );

  const notesFromServer = call?.notes ?? "";
  const [notesText, setNotesText] = useState(notesFromServer);
  // Sync when server data arrives or changes
  const [lastSynced, setLastSynced] = useState("");
  if (notesFromServer !== lastSynced && !editingNotes) {
    setNotesText(notesFromServer);
    setLastSynced(notesFromServer);
  }

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
    refetchInterval: call?.status === "active" ? 5000 : false,
  });

  const { data: summary } = useQuery({
    queryKey: ["summary", callId],
    queryFn: () =>
      apiFetch<SummaryData>(`/api/v1/calls/${callId}/summary`),
    enabled: call?.status === "completed",
    retry: false,
  });

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

  const direction = call?.direction
    ? call.direction.charAt(0).toUpperCase() + call.direction.slice(1)
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
        <div>
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
            ) : call?.caller_number ? (
              <PhoneLink number={call.caller_number} />
            ) : (
              "Loading..."
            )}
          </h2>
          <div className="flex items-center gap-2 mt-0.5">
            {call?.contact_name && (
              <span className="text-sm text-page-text-secondary">
                <PhoneLink number={call.caller_number} />
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
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-5 gap-6">
        {/* Transcript */}
        <div className="lg:col-span-3 space-y-6">
          <div className="bg-card-bg rounded-lg border border-card-border">
            <div className="p-4 border-b border-card-border">
              <h3 className="font-semibold text-page-text">Transcript</h3>
            </div>
            <div className="p-4 max-h-[600px] overflow-auto space-y-3">
              {transcript?.map((chunk, i) => (
                <div
                  key={`${chunk.chunk_index}-${i}`}
                  className="flex gap-3"
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
              ))}
              {(!transcript || transcript.length === 0) && (
                <p className="text-page-text-muted text-sm text-center py-4">
                  No transcript available
                </p>
              )}
            </div>
          </div>

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
