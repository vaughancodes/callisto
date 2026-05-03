import {
  keepPreviousData,
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";
import { AlertCircle, Plus, Upload, X } from "lucide-react";
import { useRef, useState } from "react";
import { Link } from "react-router-dom";
import { ConfirmDialog } from "../components/ConfirmDialog";
import { EmailLink, PhoneLink } from "../components/LinkedContact";
import { PageLoadingSpinner } from "../components/LoadingSpinner";
import { useAuth, getGoogleToken } from "../contexts/AuthContext";
import { useDocumentTitle } from "../hooks/useDocumentTitle";
import { apiFetch } from "../lib/api";
import { ScrollLock } from "../hooks/useBodyScrollLock";

interface ContactData {
  id: string;
  name: string;
  company: string | null;
  phone_numbers: string[];
  email: string | null;
  notes: string | null;
  google_contact_id: string | null;
  created_at: string;
}

export function ContactsPage() {
  useDocumentTitle("Contacts");
  const { tenant } = useAuth();
  const queryClient = useQueryClient();
  const [showForm, setShowForm] = useState(false);
  const [editing, setEditing] = useState<ContactData | null>(null);
  const [showImport, setShowImport] = useState(false);
  const [syncing, setSyncing] = useState(false);
  const [search, setSearch] = useState("");
  const [formError, setFormError] = useState<string | null>(null);
  const [deleting, setDeleting] = useState<ContactData | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  const { data, isLoading } = useQuery({
    queryKey: ["contacts", tenant?.id, search],
    queryFn: () =>
      apiFetch<{ contacts: ContactData[]; total: number }>(
        `/api/v1/tenants/${tenant!.id}/contacts?per_page=100&q=${encodeURIComponent(search)}`
      ),
    enabled: !!tenant,
    placeholderData: keepPreviousData,
  });

  const createMutation = useMutation({
    mutationFn: (d: Record<string, unknown>) =>
      apiFetch(`/api/v1/tenants/${tenant!.id}/contacts`, {
        method: "POST",
        body: JSON.stringify(d),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["contacts"] });
      setFormError(null);
      setShowForm(false);
    },
    onError: (err: Error) => setFormError(err.message),
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, ...d }: { id: string } & Record<string, unknown>) =>
      apiFetch(`/api/v1/contacts/${id}`, {
        method: "PUT",
        body: JSON.stringify(d),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["contacts"] });
      setEditing(null);
      setFormError(null);
      setShowForm(false);
    },
    onError: (err: Error) => setFormError(err.message),
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) =>
      apiFetch(`/api/v1/contacts/${id}`, { method: "DELETE" }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["contacts"] }),
  });

  const handleSubmit = (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    setFormError(null);
    const form = new FormData(e.currentTarget);
    const phones = (form.get("phone_numbers") as string)
      .split(",")
      .map((p) => p.trim())
      .filter(Boolean);
    const d = {
      name: form.get("name"),
      company: form.get("company") || null,
      phone_numbers: phones,
      email: form.get("email") || null,
      notes: form.get("notes") || null,
    };
    if (editing) {
      updateMutation.mutate({ id: editing.id, ...d });
    } else {
      createMutation.mutate(d);
    }
  };

  const handleImport = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    const form = new FormData(e.currentTarget);
    const token = localStorage.getItem("callisto_token");
    const resp = await fetch(
      `/api/v1/tenants/${tenant!.id}/contacts/import`,
      {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` },
        body: form,
      }
    );
    const result = await resp.json();
    alert(`Imported: ${result.created} created, ${result.updated} updated, ${result.skipped} skipped`);
    queryClient.invalidateQueries({ queryKey: ["contacts"] });
    setShowImport(false);
  };

  const handleGoogleSync = async () => {
    const googleToken = getGoogleToken();
    if (!googleToken) {
      alert("No Google token available. Please log out and log back in to grant contacts permission.");
      return;
    }
    setSyncing(true);
    try {
      const result = await apiFetch<{ total: number; created: number; updated: number }>(
        "/api/v1/contacts/sync/google",
        {
          method: "POST",
          body: JSON.stringify({ access_token: googleToken }),
        }
      );
      alert(`Synced: ${result.created} created, ${result.updated} updated (${result.total} total)`);
      queryClient.invalidateQueries({ queryKey: ["contacts"] });
    } catch (err) {
      alert("Sync failed — your Google token may have expired. Log out and back in.");
    } finally {
      setSyncing(false);
    }
  };

  if (isLoading) {
    return <PageLoadingSpinner />;
  }

  return (
    <div className="p-4 sm:p-6">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 sm:gap-6 mb-6">
        <h2 className="text-2xl font-bold text-page-text">Contacts</h2>
        <div className="flex flex-wrap gap-2">
          <button
            onClick={handleGoogleSync}
            disabled={syncing}
            className="flex items-center gap-2 px-3 py-1.5 bg-card-bg border border-card-border rounded-lg hover:bg-page-hover text-sm text-page-text disabled:opacity-50"
          >
            <svg className="w-4 h-4" viewBox="0 0 24 24">
              <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92a5.06 5.06 0 0 1-2.2 3.32v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.1z" />
              <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" />
              <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z" />
              <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" />
            </svg>
            {syncing ? "Syncing..." : "Sync Google Contacts"}
          </button>
          <button
            onClick={() => setShowImport(true)}
            className="flex items-center gap-2 px-3 py-1.5 bg-card-bg border border-card-border rounded-lg hover:bg-page-hover text-sm text-page-text"
          >
            <Upload className="w-4 h-4" />
            Import CSV
          </button>
          <button
            onClick={() => { setEditing(null); setFormError(null); setShowForm(true); }}
            className="flex items-center gap-2 px-3 py-1.5 bg-brand-sky text-white rounded-lg hover:bg-brand-sky/80 text-sm"
          >
            <Plus className="w-4 h-4" />
            Add Contact
          </button>
        </div>
      </div>

      {/* Search */}
      <div className="mb-4">
        <input
          type="text"
          placeholder="Search contacts..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="w-full max-w-sm px-3 py-2 border border-card-border rounded-lg text-sm bg-page-bg-tertiary text-page-text"
        />
      </div>

      {/* Contacts table */}
      <div className="bg-card-bg rounded-lg border border-card-border">
          <div className="overflow-x-auto"><table className="w-full min-w-[640px]">
            <thead>
              <tr className="border-b border-card-border text-left text-sm text-page-text-secondary">
                <th className="p-4 font-medium">Name</th>
                <th className="p-4 font-medium">Company</th>
                <th className="p-4 font-medium">Phone</th>
                <th className="p-4 font-medium">Email</th>
                <th className="p-4 font-medium">Source</th>
                <th className="p-4 font-medium">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-page-divider">
              {data?.contacts.map((c) => (
                <tr key={c.id} className="hover:bg-page-hover">
                  <td className="p-4 text-sm font-medium text-page-text align-middle">
                    <Link to={`/contacts/${c.id}`} className="text-brand-sky hover:underline">
                      {c.name}
                    </Link>
                  </td>
                  <td className="p-4 text-sm text-page-text-secondary align-middle">{c.company ?? "—"}</td>
                  <td className="p-4 text-sm text-page-text-secondary align-middle">
                    {c.phone_numbers.length > 0
                      ? c.phone_numbers.map((p, i) => (
                          <span key={p}>
                            {i > 0 && ", "}
                            <PhoneLink number={p} />
                          </span>
                        ))
                      : "—"}
                  </td>
                  <td className="p-4 text-sm text-page-text-secondary align-middle">
                    {c.email ? <EmailLink email={c.email} /> : "—"}
                  </td>
                  <td className="p-4 text-sm text-page-text-secondary align-middle">
                    {c.google_contact_id ? (
                      <span className="text-xs px-1.5 py-0.5 bg-brand-sky/10 text-brand-sky rounded">
                        Google
                      </span>
                    ) : (
                      <span className="text-xs px-1.5 py-0.5 bg-page-divider text-page-text-secondary rounded">
                        Manual
                      </span>
                    )}
                  </td>
                  <td className="p-4 align-middle">
                    <div className="flex gap-2">
                      <button
                        onClick={() => { setEditing(c); setFormError(null); setShowForm(true); }}
                        className="text-xs px-2.5 py-1 border border-brand-sky text-brand-sky rounded-md hover:bg-brand-sky/10 transition-colors"
                      >
                        Edit
                      </button>
                      <button
                        onClick={() => setDeleting(c)}
                        className="text-xs px-2.5 py-1 border border-danger text-danger rounded-md hover:bg-danger/10 transition-colors"
                      >
                        Delete
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
              {data?.contacts.length === 0 && (
                <tr>
                  <td colSpan={6} className="p-8 text-center text-page-text-muted">
                    No contacts yet. Import a CSV or sync from Google.
                  </td>
                </tr>
              )}
            </tbody>
          </table></div>
      </div>

      <ConfirmDialog
        open={!!deleting}
        title="Delete Contact"
        message={
          <>
            Are you sure you want to delete{" "}
            <span className="font-semibold text-page-text">{deleting?.name}</span>?
          </>
        }
        warning="This will unlink the contact from any calls they're associated with. The calls themselves will not be deleted."
        confirmLabel="Delete Contact"
        onConfirm={() => {
          if (deleting) deleteMutation.mutate(deleting.id);
          setDeleting(null);
        }}
        onCancel={() => setDeleting(null)}
      />

      {/* Create/Edit modal */}
      {showForm && (
        <div className="fixed inset-0 bg-black/30 flex items-center justify-center z-50">
          <ScrollLock />
          <div className="bg-card-bg rounded-xl shadow-lg w-full max-w-lg p-6">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg font-semibold text-page-text">
                {editing ? "Edit Contact" : "New Contact"}
              </h3>
              <button onClick={() => { setShowForm(false); setFormError(null); }} className="p-1 hover:bg-page-hover rounded">
                <X className="w-5 h-5 text-page-text" />
              </button>
            </div>
            {formError && (
              <div className="mb-4 flex items-start gap-2 p-3 rounded-lg bg-danger/10 border border-danger/30 text-danger">
                <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" />
                <p className="text-sm leading-snug">{formError}</p>
              </div>
            )}
            <form onSubmit={handleSubmit} className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-page-text mb-1">Name</label>
                <input name="name" defaultValue={editing?.name ?? ""} required className="w-full px-3 py-2 border border-card-border rounded-lg text-sm bg-page-bg-tertiary text-page-text" />
              </div>
              <div>
                <label className="block text-sm font-medium text-page-text mb-1">Company</label>
                <input name="company" defaultValue={editing?.company ?? ""} className="w-full px-3 py-2 border border-card-border rounded-lg text-sm bg-page-bg-tertiary text-page-text" />
              </div>
              <div>
                <label className="block text-sm font-medium text-page-text mb-1">Phone Numbers (comma-separated)</label>
                <input name="phone_numbers" defaultValue={editing?.phone_numbers.join(", ") ?? ""} className="w-full px-3 py-2 border border-card-border rounded-lg text-sm bg-page-bg-tertiary text-page-text" placeholder="+15551234567" />
              </div>
              <div>
                <label className="block text-sm font-medium text-page-text mb-1">Email</label>
                <input name="email" type="email" defaultValue={editing?.email ?? ""} className="w-full px-3 py-2 border border-card-border rounded-lg text-sm bg-page-bg-tertiary text-page-text" />
              </div>
              <div>
                <label className="block text-sm font-medium text-page-text mb-1">Notes</label>
                <textarea
                  name="notes"
                  defaultValue={editing?.notes ?? ""}
                  rows={3}
                  className="w-full px-3 py-2 border border-card-border rounded-lg text-sm bg-page-bg-tertiary text-page-text placeholder:text-page-text-muted"
                  placeholder="Optional notes about this contact"
                />
              </div>
              <div className="flex justify-end gap-3 pt-2">
                <button type="button" onClick={() => { setShowForm(false); setFormError(null); }} className="px-4 py-2 text-sm text-page-text-secondary hover:bg-page-hover rounded-lg">Cancel</button>
                <button type="submit" className="px-4 py-2 text-sm bg-brand-sky text-white rounded-lg hover:bg-brand-sky/80">{editing ? "Update" : "Create"}</button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* CSV Import modal */}
      {showImport && (
        <div className="fixed inset-0 bg-black/30 flex items-center justify-center z-50">
          <ScrollLock />
          <div className="bg-card-bg rounded-xl shadow-lg w-full max-w-md p-6">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg font-semibold text-page-text">Import CSV</h3>
              <button onClick={() => setShowImport(false)} className="p-1 hover:bg-page-hover rounded">
                <X className="w-5 h-5 text-page-text" />
              </button>
            </div>
            <form onSubmit={handleImport} className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-page-text mb-1">CSV File</label>
                <input ref={fileRef} name="file" type="file" accept=".csv" required className="w-full text-sm" />
              </div>
              <p className="text-xs text-page-text-secondary">
                Specify which columns in your CSV map to each field. Leave defaults if your CSV
                uses standard headers.
              </p>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-medium text-page-text-secondary mb-1">Name column</label>
                  <input name="name_col" defaultValue="name" className="w-full px-2 py-1.5 border border-card-border rounded text-sm bg-page-bg-tertiary text-page-text" />
                </div>
                <div>
                  <label className="block text-xs font-medium text-page-text-secondary mb-1">Company column</label>
                  <input name="company_col" defaultValue="company" className="w-full px-2 py-1.5 border border-card-border rounded text-sm bg-page-bg-tertiary text-page-text" />
                </div>
                <div>
                  <label className="block text-xs font-medium text-page-text-secondary mb-1">Phone column</label>
                  <input name="phone_col" defaultValue="phone" className="w-full px-2 py-1.5 border border-card-border rounded text-sm bg-page-bg-tertiary text-page-text" />
                </div>
                <div>
                  <label className="block text-xs font-medium text-page-text-secondary mb-1">Email column</label>
                  <input name="email_col" defaultValue="email" className="w-full px-2 py-1.5 border border-card-border rounded text-sm bg-page-bg-tertiary text-page-text" />
                </div>
              </div>
              <div className="flex justify-end gap-3 pt-2">
                <button type="button" onClick={() => setShowImport(false)} className="px-4 py-2 text-sm text-page-text-secondary hover:bg-page-hover rounded-lg">Cancel</button>
                <button type="submit" className="px-4 py-2 text-sm bg-brand-sky text-white rounded-lg hover:bg-brand-sky/80">Import</button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
