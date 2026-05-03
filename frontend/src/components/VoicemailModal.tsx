import { useQuery } from "@tanstack/react-query";
import { ExternalLink, Voicemail, X } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router-dom";
import { PhoneLink } from "./LinkedContact";
import { useActiveTranscriptChunk } from "../hooks/useActiveTranscriptChunk";
import { useAuthedAudio } from "../hooks/useAuthedAudio";
import { ScrollLock } from "../hooks/useBodyScrollLock";
import { apiFetch } from "../lib/api";
import { formatDateTime, formatDialStatus } from "../lib/format";

interface VoicemailTranscriptChunk {
  speaker: string;
  text: string;
  start_ms: number;
  end_ms: number;
  confidence: number;
  chunk_index: number;
}

interface VoicemailData {
  started_at: string;
  started_at_ms: number;
  dial_status: string | null;
  duration_sec: number | null;
  has_recording: boolean;
  transcript: VoicemailTranscriptChunk[];
}

interface CallMeta {
  id: string;
  direction: string;
  other_party_number?: string | null;
  caller_number: string;
  contact_id: string | null;
  contact_name: string | null;
  contact_company: string | null;
  our_number_friendly_name?: string | null;
  started_at: string;
}

function formatOffset(ms: number): string {
  const s = Math.floor(ms / 1000);
  const m = Math.floor(s / 60);
  return `${m}:${(s % 60).toString().padStart(2, "0")}`;
}

interface Props {
  callId: string;
  onClose: () => void;
}

export function VoicemailModal({ callId, onClose }: Props) {
  const { data: voicemail, isLoading: vmLoading } = useQuery({
    queryKey: ["voicemail", callId],
    queryFn: () =>
      apiFetch<VoicemailData>(`/api/v1/calls/${callId}/voicemail`),
    retry: false,
  });

  const { data: call } = useQuery({
    queryKey: ["call", callId],
    queryFn: () => apiFetch<CallMeta>(`/api/v1/calls/${callId}`),
  });

  const audioUrl = useAuthedAudio(
    voicemail?.has_recording ? `/api/v1/calls/${callId}/voicemail/audio` : null
  );
  // useState ref-callback so the effect re-runs when the audio element
  // mounts (it's conditionally rendered after the blob URL loads).
  const [audioEl, setAudioEl] = useState<HTMLAudioElement | null>(null);
  // Sliced voicemail audio starts at 0s, but the chunks' start_ms values
  // are still in call-time. Offset by the voicemail boundary so audio
  // 0s lines up with chunks at start_ms == voicemail.started_at_ms.
  const activeIdx = useActiveTranscriptChunk(
    audioEl,
    voicemail?.transcript,
    voicemail?.started_at_ms ?? 0
  );

  const otherParty = call?.other_party_number ?? call?.caller_number ?? "";

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <ScrollLock />
      <div className="bg-card-bg rounded-xl shadow-lg w-full max-w-2xl max-h-[90vh] overflow-hidden flex flex-col">
        <div className="p-4 border-b border-card-border flex items-center gap-3">
          <Voicemail className="w-5 h-5 text-accent-lavender shrink-0" />
          <div className="flex-1 min-w-0">
            <h3 className="text-lg font-semibold text-page-text">
              Voicemail
            </h3>
            {call && (
              <p className="text-xs text-page-text-muted truncate">
                {call.contact_name ?? <PhoneLink number={otherParty} />}
                {call.contact_company ? ` · ${call.contact_company}` : ""}
              </p>
            )}
          </div>
          <button
            onClick={onClose}
            className="p-1 hover:bg-page-hover rounded"
            aria-label="Close"
          >
            <X className="w-5 h-5 text-page-text" />
          </button>
        </div>

        <div className="p-5 space-y-4 overflow-auto">
          {vmLoading && (
            <p className="text-sm text-page-text-muted">Loading voicemail...</p>
          )}

          {voicemail && (
            <>
              <div className="flex flex-wrap gap-x-6 gap-y-1 text-xs text-page-text-secondary">
                <span>
                  <span className="text-page-text-muted">Received:</span>{" "}
                  {formatDateTime(voicemail.started_at)}
                </span>
                {voicemail.duration_sec != null && (
                  <span>
                    <span className="text-page-text-muted">Duration:</span>{" "}
                    {voicemail.duration_sec}s
                  </span>
                )}
                {voicemail.dial_status && (
                  <span>
                    <span className="text-page-text-muted">Reason:</span>{" "}
                    {formatDialStatus(voicemail.dial_status)}
                  </span>
                )}
              </div>

              {voicemail.has_recording ? (
                audioUrl ? (
                  <audio
                    ref={setAudioEl}
                    controls
                    preload="metadata"
                    src={audioUrl}
                    className="w-full"
                  />
                ) : (
                  <p className="text-sm text-page-text-muted">
                    Loading recording...
                  </p>
                )
              ) : (
                <p className="text-sm text-page-text-muted">
                  No recording available (audio may have been deleted by
                  retention policy, or the call is still processing).
                </p>
              )}

              <div>
                <h4 className="text-sm font-medium text-page-text mb-2">
                  Transcript
                </h4>
                {voicemail.transcript.length > 0 ? (
                  <div className="max-h-[260px] overflow-auto space-y-2 border border-card-border rounded-lg p-3 bg-page-bg-tertiary">
                    {voicemail.transcript.map((chunk, i) => {
                      const active = i === activeIdx;
                      const seek = () => {
                        if (audioEl) {
                          audioEl.currentTime = Math.max(
                            0,
                            (chunk.start_ms - voicemail.started_at_ms) / 1000
                          );
                          void audioEl.play().catch(() => {});
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
                          {formatOffset(
                            chunk.start_ms - voicemail.started_at_ms
                          )}
                        </span>
                        <span className="text-sm text-page-text flex-1 min-w-0">
                          {chunk.text}
                        </span>
                      </div>
                      );
                    })}
                  </div>
                ) : (
                  <p className="text-sm text-page-text-muted">
                    No transcript captured for this voicemail.
                  </p>
                )}
              </div>
            </>
          )}
        </div>

        <div className="p-4 border-t border-card-border flex justify-end">
          <Link
            to={`/calls/${callId}`}
            onClick={onClose}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 text-sm bg-brand-sky text-white rounded-lg hover:bg-brand-sky/80"
          >
            Open call <ExternalLink className="w-3.5 h-3.5" />
          </Link>
        </div>
      </div>
    </div>
  );
}
