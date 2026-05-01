import { useQuery } from "@tanstack/react-query";
import { ChevronRight, Voicemail } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router-dom";
import { useAuth } from "../contexts/AuthContext";
import { apiFetch } from "../lib/api";
import { formatDateTime } from "../lib/format";
import { VoicemailModal } from "./VoicemailModal";

export interface VoicemailSummary {
  call_id: string;
  external_id: string;
  direction: string;
  other_party_number: string | null;
  our_number_friendly_name: string | null;
  contact_id: string | null;
  contact_name: string | null;
  contact_company: string | null;
  call_started_at: string;
  voicemail_started_at: string | null;
  voicemail_duration_sec: number | null;
  has_recording: boolean;
}

interface Props {
  /** How many voicemails to show. Omit for "show all" (pagination-ready pages). */
  limit?: number;
  /** "card": dashboard widget. "page": full-page list. */
  variant?: "card" | "page";
}

export function VoicemailsList({ limit, variant = "card" }: Props) {
  const { tenant } = useAuth();
  const [openId, setOpenId] = useState<string | null>(null);

  const perPage = limit ?? 50;
  const { data, isLoading } = useQuery({
    queryKey: ["voicemails", tenant?.id, perPage],
    queryFn: () =>
      apiFetch<{
        voicemails: VoicemailSummary[];
        total: number;
        page: number;
        pages: number;
      }>(
        `/api/v1/tenants/${tenant!.id}/voicemails?per_page=${perPage}`
      ),
    enabled: !!tenant,
  });

  const items = data?.voicemails ?? [];

  return (
    <>
      <div className="bg-card-bg rounded-lg border border-card-border">
        <div className="p-4 border-b border-card-border flex items-center justify-between">
          <h3 className="font-semibold text-page-text flex items-center gap-2">
            <Voicemail className="w-4 h-4 text-accent-lavender" />
            Voicemails
            {data && (
              <span className="text-xs font-normal text-page-text-muted">
                ({data.total})
              </span>
            )}
          </h3>
          {variant === "card" && (
            <Link
              to="/voicemails"
              className="text-xs text-brand-sky hover:underline inline-flex items-center"
            >
              See all <ChevronRight className="w-3 h-3" />
            </Link>
          )}
        </div>

        <div
          className={`divide-y divide-page-divider ${
            variant === "card" ? "max-h-96 overflow-auto" : ""
          }`}
        >
          {isLoading ? (
            <div className="p-6 text-center text-page-text-muted text-sm">
              Loading...
            </div>
          ) : items.length === 0 ? (
            <div className="p-6 text-center text-page-text-muted text-sm">
              No voicemails yet.
            </div>
          ) : (
            items.map((v) => (
              <button
                key={v.call_id}
                type="button"
                onClick={() => setOpenId(v.call_id)}
                className="w-full text-left p-3 hover:bg-page-hover transition-colors"
              >
                <div className="flex items-center justify-between gap-3">
                  <div className="min-w-0 flex-1">
                    <p className="text-sm font-medium text-page-text truncate">
                      {v.contact_name ?? v.other_party_number ?? "Unknown"}
                    </p>
                    <p className="text-xs text-page-text-muted truncate">
                      {v.contact_company ? `${v.contact_company} · ` : ""}
                      {v.voicemail_started_at
                        ? formatDateTime(v.voicemail_started_at)
                        : formatDateTime(v.call_started_at)}
                    </p>
                  </div>
                  <div className="flex items-center gap-2 shrink-0">
                    {v.voicemail_duration_sec != null && (
                      <span className="text-xs text-page-text-muted">
                        {v.voicemail_duration_sec}s
                      </span>
                    )}
                    {!v.has_recording && (
                      <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-page-divider text-page-text-muted">
                        no audio
                      </span>
                    )}
                    <ChevronRight className="w-4 h-4 text-page-text-muted" />
                  </div>
                </div>
              </button>
            ))
          )}
        </div>
      </div>

      {openId && (
        <VoicemailModal callId={openId} onClose={() => setOpenId(null)} />
      )}
    </>
  );
}
