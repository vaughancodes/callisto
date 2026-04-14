import { useMutation, useQueryClient } from "@tanstack/react-query";
import {
  AlertTriangle,
  CheckCircle,
  ChevronDown,
  ChevronRight,
  Clock,
  Phone,
  PhoneIncoming,
  PhoneOutgoing,
  StickyNote,
} from "lucide-react";
import { useState } from "react";
import { Link } from "react-router-dom";
import { PhoneLink } from "./LinkedContact";
import { Tooltip } from "./Tooltip";
import { formatDateTime, formatStatus } from "../lib/format";
import { apiFetch } from "../lib/api";

function DirectionIcon({ direction }: { direction: string }) {
  const isOutbound = direction.startsWith("outbound");
  const Icon = isOutbound ? PhoneOutgoing : PhoneIncoming;
  const label = isOutbound ? "Outbound call" : "Inbound call";
  return (
    <Tooltip content={label}>
      <Icon
        className={`w-3.5 h-3.5 ${
          isOutbound ? "text-accent-periwinkle" : "text-brand-sky"
        }`}
        aria-label={label}
      />
    </Tooltip>
  );
}

export interface CallListData {
  id: string;
  external_id?: string;
  source?: string;
  direction: string;
  caller_number: string;
  callee_number?: string | null;
  other_party_number?: string | null;
  our_number_friendly_name?: string | null;
  contact_id?: string | null;
  contact_name?: string | null;
  contact_company?: string | null;
  status: string;
  started_at: string;
  ended_at?: string | null;
  duration_sec?: number | null;
  notes?: string | null;
  topics?: string[];
  sentiment?: string | null;
  summary_text?: string | null;
}

const statusIcon: Record<string, React.ReactNode> = {
  active: <Phone className="w-4 h-4 text-accent-light animate-pulse" />,
  processing: <Clock className="w-4 h-4 text-warning" />,
  completed: <CheckCircle className="w-4 h-4 text-brand-sky" />,
  failed: <AlertTriangle className="w-4 h-4 text-danger" />,
};

const sentimentDot: Record<string, string> = {
  positive: "bg-success",
  negative: "bg-danger",
  neutral: "bg-page-text-muted",
  mixed: "bg-warning",
};

export function CallListItem({
  call,
  showDateAsTitle = false,
}: {
  call: CallListData;
  showDateAsTitle?: boolean;
}) {
  const [expanded, setExpanded] = useState(false);
  const [editingNotes, setEditingNotes] = useState(false);
  const [notesText, setNotesText] = useState(call.notes ?? "");
  const queryClient = useQueryClient();

  const saveNotes = useMutation({
    mutationFn: (notes: string) =>
      apiFetch(`/api/v1/calls/${call.id}/notes`, {
        method: "PUT",
        body: JSON.stringify({ notes }),
      }),
    onSuccess: () => {
      setEditingNotes(false);
      queryClient.invalidateQueries({ queryKey: ["calls"] });
      queryClient.invalidateQueries({ queryKey: ["contact"] });
    },
  });

  return (
    <div className="border-b border-page-divider last:border-b-0">
      {/* Main row */}
      <div className="flex items-center gap-3 p-4 hover:bg-page-hover transition-colors">
        {/* Expand arrow */}
        <button
          onClick={() => setExpanded(!expanded)}
          className="p-0.5 text-page-text-muted hover:text-page-text-secondary"
        >
          {expanded ? (
            <ChevronDown className="w-4 h-4" />
          ) : (
            <ChevronRight className="w-4 h-4" />
          )}
        </button>

        {/* Status icon */}
        {statusIcon[call.status] ?? statusIcon.completed}

        {/* Sentiment dot (invisible placeholder when missing, to keep alignment) */}
        <span
          className={`w-2 h-2 rounded-full shrink-0 ${
            call.sentiment
              ? sentimentDot[call.sentiment] ?? "bg-page-text-muted"
              : "invisible"
          }`}
          title={call.sentiment ?? ""}
        />


        {/* Main info */}
        <Link to={`/calls/${call.id}`} className="flex-1 min-w-0">
          {showDateAsTitle ? (
            <>
              <p className="text-sm font-medium text-page-text">
                {formatDateTime(call.started_at)}
              </p>
              <div className="flex items-center gap-1.5 mt-0.5 text-xs text-page-text-secondary">
                <DirectionIcon direction={call.direction} />
                {call.our_number_friendly_name && (
                  <span>{call.our_number_friendly_name} &middot;</span>
                )}
                <PhoneLink number={call.other_party_number ?? call.caller_number} />
              </div>
            </>
          ) : (
            <>
              <p className="text-sm font-medium text-page-text">
                {call.contact_name ? (
                  <>
                    {call.contact_id ? (
                      <Link
                        to={`/contacts/${call.contact_id}`}
                        className="text-brand-sky hover:underline"
                        onClick={(e) => e.stopPropagation()}
                      >
                        {call.contact_name}
                      </Link>
                    ) : (
                      call.contact_name
                    )}
                    <span className="text-page-text-muted font-normal ml-2">
                      <PhoneLink number={call.other_party_number ?? call.caller_number} />
                    </span>
                  </>
                ) : (
                  <PhoneLink number={call.other_party_number ?? call.caller_number} />
                )}
              </p>
              <div className="flex items-center gap-1.5 mt-0.5 text-xs text-page-text-secondary">
                {call.contact_company && (
                  <span>{call.contact_company} &middot;</span>
                )}
                <DirectionIcon direction={call.direction} />
                {call.our_number_friendly_name && (
                  <span>{call.our_number_friendly_name} &middot;</span>
                )}
                <span>{formatDateTime(call.started_at)}</span>
              </div>
            </>
          )}
        </Link>

        {/* Topics preview */}
        {(call.topics?.length ?? 0) > 0 && (
          <div className="hidden md:flex gap-1 shrink-0">
            {call.topics!.slice(0, 3).map((t) => (
              <span
                key={t}
                className="text-xs px-2 py-0.5 bg-page-divider text-page-text-secondary rounded"
              >
                {t}
              </span>
            ))}
          </div>
        )}

        {/* Notes indicator */}
        {call.notes && (
          <StickyNote className="w-3.5 h-3.5 text-warning shrink-0" title="Has notes" />
        )}

        {/* Status + duration */}
        <div className="text-right shrink-0">
          <span
            className={`inline-block px-2 py-0.5 text-xs rounded-full ${
              call.status === "active"
                ? "bg-brand-sky/10 text-brand-sky"
                : call.status === "completed"
                  ? "bg-brand-indigo/10 text-brand-indigo"
                  : call.status === "processing"
                    ? "bg-warning/15 text-warning"
                    : "bg-danger/15 text-danger"
            }`}
          >
            {formatStatus(call.status)}
          </span>
          {call.duration_sec != null && (
            <p className="text-xs text-page-text-muted mt-1">
              {Math.floor(call.duration_sec / 60)}m {call.duration_sec % 60}s
            </p>
          )}
        </div>
      </div>

      {/* Expanded section */}
      {expanded && (
        <div className="px-4 pb-4 pl-12 space-y-3">
          {/* Summary */}
          {call.summary_text && (
            <div>
              <p className="text-xs font-medium text-page-text-secondary uppercase mb-1">
                Summary
              </p>
              <p className="text-sm text-page-text-secondary">{call.summary_text}</p>
              {(call.topics?.length ?? 0) > 0 && (
                <div className="flex flex-wrap gap-1 mt-2">
                  {call.topics!.map((t) => (
                    <span
                      key={t}
                      className="text-xs px-2 py-0.5 bg-page-divider text-page-text-secondary rounded"
                    >
                      {t}
                    </span>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* Notes */}
          <div>
            <p className="text-xs font-medium text-page-text-secondary uppercase mb-1">
              Notes
            </p>
            {editingNotes ? (
              <div className="space-y-2">
                <textarea
                  value={notesText}
                  onChange={(e) => setNotesText(e.target.value)}
                  rows={3}
                  className="w-full px-3 py-2 text-sm border border-card-border rounded-lg bg-page-bg-tertiary text-page-text placeholder:text-page-text-muted"
                  autoFocus
                />
                <div className="flex gap-2">
                  <button
                    onClick={() => saveNotes.mutate(notesText)}
                    className="px-3 py-1 text-xs bg-brand-sky text-white rounded-lg hover:bg-brand-sky/80"
                  >
                    Save
                  </button>
                  <button
                    onClick={() => {
                      setEditingNotes(false);
                      setNotesText(call.notes ?? "");
                    }}
                    className="px-3 py-1 text-xs text-page-text-secondary hover:bg-page-hover rounded-lg"
                  >
                    Cancel
                  </button>
                </div>
              </div>
            ) : (
              <div
                onClick={() => setEditingNotes(true)}
                className="text-sm text-page-text-secondary cursor-pointer hover:bg-page-hover rounded p-2 -m-2 min-h-[2rem]"
              >
                {call.notes || (
                  <span className="text-page-text-muted italic">
                    Click to add notes...
                  </span>
                )}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
