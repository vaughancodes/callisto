import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, Building2, Mail, Phone } from "lucide-react";
import { useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { CallListItem, type CallListData } from "../components/CallListItem";
import { EmailLink, PhoneLink } from "../components/LinkedContact";
import { PageLoadingSpinner } from "../components/LoadingSpinner";
import { useDocumentTitle } from "../hooks/useDocumentTitle";
import { apiFetch } from "../lib/api";
import { capitalize } from "../lib/format";

interface ContactDetailData {
  id: string;
  name: string;
  company: string | null;
  phone_numbers: string[];
  email: string | null;
  google_contact_id: string | null;
  notes: string | null;
  calls: CallListData[];
  sentiment_summary: {
    counts: Record<string, number>;
    latest: string | null;
    total_calls: number;
    analyzed_calls: number;
  };
  top_topics: [string, number][];
}

const sentimentColors: Record<string, string> = {
  positive: "bg-success/15 text-success",
  negative: "bg-danger/15 text-danger",
  neutral: "bg-page-divider text-page-text",
  mixed: "bg-warning/15 text-warning",
};

const sentimentBarColors: Record<string, string> = {
  positive: "bg-success",
  negative: "bg-danger",
  neutral: "bg-page-text-muted",
  mixed: "bg-warning",
};

export function ContactDetailPage() {
  const { contactId } = useParams<{ contactId: string }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [editingNotes, setEditingNotes] = useState(false);

  const { data: contact, isLoading } = useQuery({
    queryKey: ["contact", contactId],
    queryFn: () => apiFetch<ContactDetailData>(`/api/v1/contacts/${contactId}`),
    refetchInterval: (query) => {
      const calls = query.state.data?.calls ?? [];
      const inFlight = calls.some(
        (c: { status: string }) =>
          c.status === "active" || c.status === "processing"
      );
      return inFlight ? 3000 : false;
    },
  });

  useDocumentTitle(contact ? contact.name : "Contact");

  const contactNotes = contact?.notes ?? "";
  const [notesText, setNotesText] = useState(contactNotes);
  const [lastSynced, setLastSynced] = useState("");
  if (contactNotes !== lastSynced && !editingNotes) {
    setNotesText(contactNotes);
    setLastSynced(contactNotes);
  }

  const saveNotes = useMutation({
    mutationFn: (notes: string) =>
      apiFetch(`/api/v1/contacts/${contactId}/notes`, {
        method: "PUT",
        body: JSON.stringify({ notes }),
      }),
    onSuccess: () => {
      setEditingNotes(false);
      queryClient.invalidateQueries({ queryKey: ["contact", contactId] });
    },
  });

  if (isLoading || !contact) {
    return <PageLoadingSpinner />;
  }

  const { sentiment_summary: sentiment, top_topics } = contact;
  const totalSentiment = Object.values(sentiment.counts).reduce(
    (a, b) => a + b,
    0
  );

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
        <div className="flex-1">
          <h2 className="text-2xl font-bold text-page-text">{contact.name}</h2>
          <div className="flex flex-wrap items-center gap-4 mt-2 text-sm text-page-text-secondary">
            {contact.company && (
              <span className="flex items-center gap-1.5">
                <Building2 className="w-4 h-4" />
                {contact.company}
              </span>
            )}
            {contact.phone_numbers.map((p) => (
              <span key={p} className="flex items-center gap-1.5">
                <Phone className="w-4 h-4" />
                <PhoneLink number={p} />
              </span>
            ))}
            {contact.email && (
              <span className="flex items-center gap-1.5">
                <Mail className="w-4 h-4" />
                <EmailLink email={contact.email} />
              </span>
            )}
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left: calls list */}
        <div className="lg:col-span-2">
          <div className="bg-card-bg rounded-lg border border-card-border">
            <div className="p-4 border-b border-card-border">
              <h3 className="font-semibold text-page-text">
                Calls ({contact.calls.length})
              </h3>
            </div>
            {contact.calls.length === 0 ? (
              <div className="p-8 text-center text-page-text-muted">
                No calls recorded for this contact
              </div>
            ) : (
              contact.calls.map((call) => (
                <CallListItem key={call.id} call={call} showDateAsTitle />
              ))
            )}
          </div>
        </div>

        {/* Right: sentiment + topics */}
        <div className="space-y-6">
          {/* Sentiment overview */}
          <div className="bg-card-bg rounded-lg border border-card-border">
            <div className="p-4 border-b border-card-border">
              <h3 className="font-semibold text-page-text">Sentiment</h3>
            </div>
            <div className="p-4 space-y-4">
              {sentiment.latest && (
                <div>
                  <p className="text-xs text-page-text-secondary uppercase font-medium mb-1">
                    Latest
                  </p>
                  <span
                    className={`inline-block px-3 py-1 text-sm rounded-full font-medium ${sentimentColors[sentiment.latest] ?? sentimentColors.neutral}`}
                  >
                    {capitalize(sentiment.latest!)}
                  </span>
                </div>
              )}

              {totalSentiment > 0 && (
                <div>
                  <p className="text-xs text-page-text-secondary uppercase font-medium mb-2">
                    All calls ({sentiment.analyzed_calls} analyzed)
                  </p>
                  <div className="flex h-3 rounded-full overflow-hidden">
                    {Object.entries(sentiment.counts).map(([key, count]) => (
                      <div
                        key={key}
                        className={
                          sentimentBarColors[key] ?? "bg-page-text-muted"
                        }
                        style={{
                          width: `${(count / totalSentiment) * 100}%`,
                        }}
                        title={`${key}: ${count}`}
                      />
                    ))}
                  </div>
                  <div className="flex flex-wrap gap-3 mt-2">
                    {Object.entries(sentiment.counts).map(([key, count]) => (
                      <span
                        key={key}
                        className="flex items-center gap-1.5 text-xs text-page-text-secondary"
                      >
                        <span
                          className={`w-2 h-2 rounded-full ${sentimentBarColors[key] ?? "bg-page-text-muted"}`}
                        />
                        {capitalize(key)} ({count})
                      </span>
                    ))}
                  </div>
                </div>
              )}

              {totalSentiment === 0 && (
                <p className="text-sm text-page-text-muted">No sentiment data yet</p>
              )}
            </div>
          </div>

          {/* Top topics */}
          <div className="bg-card-bg rounded-lg border border-card-border">
            <div className="p-4 border-b border-card-border">
              <h3 className="font-semibold text-page-text">Common Topics</h3>
            </div>
            <div className="p-4">
              {top_topics.length > 0 ? (
                <div className="flex flex-wrap gap-2">
                  {top_topics.map(([topic, count]) => (
                    <span
                      key={topic}
                      className="inline-flex items-center gap-1 px-2.5 py-1 bg-page-divider text-page-text rounded-full text-xs"
                    >
                      {topic}
                      <span className="text-page-text-muted font-medium">
                        {count}
                      </span>
                    </span>
                  ))}
                </div>
              ) : (
                <p className="text-sm text-page-text-muted">No topics yet</p>
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
                        setNotesText(contact.notes ?? "");
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
                  {contact.notes || (
                    <span className="text-page-text-muted italic">
                      Click to add notes...
                    </span>
                  )}
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
