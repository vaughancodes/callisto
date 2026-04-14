import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Shield, Trash2, UserPlus, X } from "lucide-react";
import { useEffect, useState } from "react";
import { Navigate } from "react-router-dom";
import { ConfirmDialog } from "../components/ConfirmDialog";
import { EmailLink } from "../components/LinkedContact";
import { PageLoadingSpinner } from "../components/LoadingSpinner";
import { useAuth } from "../contexts/AuthContext";
import { useDocumentTitle } from "../hooks/useDocumentTitle";
import { apiFetch } from "../lib/api";

interface TenantSettings {
  id: string;
  name: string;
  slug: string;
  description: string | null;
  context: string | null;
  forward_to: string;
  twilio_numbers: string[];
  settings: Record<string, unknown>;
}

interface Member {
  user_id: string;
  tenant_id: string;
  email: string;
  name: string;
  is_admin: boolean;
  created_at: string;
}

export function TenantSettingsPage() {
  useDocumentTitle("Tenant Settings");
  const { tenant, isTenantAdmin, refresh } = useAuth();
  const queryClient = useQueryClient();
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [context, setContext] = useState("");
  const [forwardTo, setForwardTo] = useState("");
  const [saveMessage, setSaveMessage] = useState<string | null>(null);
  const [showAddMember, setShowAddMember] = useState(false);
  const [removingMember, setRemovingMember] = useState<Member | null>(null);
  const [demotingAdmin, setDemotingAdmin] = useState<Member | null>(null);

  const { data: settings, isLoading: settingsLoading } = useQuery({
    queryKey: ["tenant-settings", tenant?.id],
    queryFn: () =>
      apiFetch<TenantSettings>(`/api/v1/tenants/${tenant!.id}/settings`),
    enabled: !!tenant && isTenantAdmin,
  });

  useEffect(() => {
    if (settings) {
      setName(settings.name);
      setDescription(settings.description ?? "");
      setContext(settings.context ?? "");
      setForwardTo(settings.forward_to ?? "");
    }
  }, [settings]);

  const { data: members, isLoading: membersLoading } = useQuery({
    queryKey: ["tenant-members", tenant?.id],
    queryFn: () =>
      apiFetch<Member[]>(`/api/v1/tenants/${tenant!.id}/members`),
    enabled: !!tenant && isTenantAdmin,
  });

  const saveSettings = useMutation({
    mutationFn: (data: Record<string, unknown>) =>
      apiFetch(`/api/v1/tenants/${tenant!.id}/settings`, {
        method: "PUT",
        body: JSON.stringify(data),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["tenant-settings"] });
      void refresh();
      setSaveMessage("Settings saved.");
      setTimeout(() => setSaveMessage(null), 3000);
    },
  });

  const addMember = useMutation({
    mutationFn: (data: { email: string; is_admin: boolean }) =>
      apiFetch(`/api/v1/tenants/${tenant!.id}/members`, {
        method: "POST",
        body: JSON.stringify(data),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["tenant-members"] });
      setShowAddMember(false);
    },
    onError: (err: Error) => {
      alert(err.message);
    },
  });

  const toggleAdmin = useMutation({
    mutationFn: ({ userId, isAdmin }: { userId: string; isAdmin: boolean }) =>
      apiFetch(`/api/v1/tenants/${tenant!.id}/members/${userId}`, {
        method: "PUT",
        body: JSON.stringify({ is_admin: isAdmin }),
      }),
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: ["tenant-members"] }),
  });

  const removeMember = useMutation({
    mutationFn: (userId: string) =>
      apiFetch(`/api/v1/tenants/${tenant!.id}/members/${userId}`, {
        method: "DELETE",
      }),
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: ["tenant-members"] }),
  });

  if (!tenant) {
    return <Navigate to="/" replace />;
  }

  if (!isTenantAdmin) {
    return (
      <div className="p-6">
        <div className="text-page-text-secondary">
          You need to be a tenant administrator to view these settings.
        </div>
      </div>
    );
  }

  if (settingsLoading || membersLoading) {
    return <PageLoadingSpinner />;
  }

  const handleSave = (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    saveSettings.mutate({
      name,
      description: description || null,
      context: context || null,
      forward_to: forwardTo.trim(),
    });
  };

  const handleAddMember = (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    const form = new FormData(e.currentTarget);
    addMember.mutate({
      email: (form.get("email") as string).trim(),
      is_admin: form.get("is_admin") === "on",
    });
  };

  return (
    <div className="p-6 max-w-4xl">
      <h2 className="text-2xl font-bold text-page-text mb-6">Tenant Settings</h2>

      {/* Basic settings */}
      <div className="bg-card-bg rounded-lg border border-card-border mb-6">
        <div className="p-4 border-b border-card-border">
          <h3 className="font-semibold text-page-text">General</h3>
        </div>
        <form onSubmit={handleSave} className="p-6 space-y-5">
          <div>
            <label className="block text-sm font-medium text-page-text mb-1">
              Name
            </label>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="w-full px-3 py-2 border border-card-border rounded-lg text-sm bg-page-bg-tertiary text-page-text"
              required
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-page-text mb-1">
              Description
            </label>
            <input
              type="text"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              className="w-full px-3 py-2 border border-card-border rounded-lg text-sm bg-page-bg-tertiary text-page-text"
              placeholder="A short description of this tenant"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-page-text mb-1">
              Business Context
            </label>
            <p className="text-xs text-page-text-secondary mb-2">
              Describe your business and the conversations your team
              typically has over the phone — whether calls come in or your
              team places them. This context is provided to the LLM during
              analysis, so insights are evaluated through the lens of your
              business. For example: "We're a university admissions office.
              Our calls are usually with prospective students or parents
              discussing application deadlines, financial aid, campus
              visits, and program requirements."
            </p>
            <textarea
              value={context}
              onChange={(e) => setContext(e.target.value)}
              rows={8}
              className="w-full px-3 py-2 border border-card-border rounded-lg text-sm bg-page-bg-tertiary text-page-text"
              placeholder="Describe your business and the typical reasons people call..."
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-page-text mb-1">
              Inbound Call Destination
            </label>
            <p className="text-xs text-page-text-secondary mb-2">
              When a call arrives at this tenant's Twilio number, it will be
              forwarded to this destination — typically an E.164 phone number
              (e.g. <code>+15551234567</code>) or a SIP URI. Leave blank to
              keep the call open without forwarding (useful for testing).
            </p>
            <input
              type="text"
              value={forwardTo}
              onChange={(e) => setForwardTo(e.target.value)}
              className="w-full px-3 py-2 border border-card-border rounded-lg text-sm bg-page-bg-tertiary text-page-text"
              placeholder="+15551234567"
            />
            {settings?.twilio_numbers && settings.twilio_numbers.length > 0 && (
              <p className="text-xs text-page-text-muted mt-2">
                Applies to inbound calls on:{" "}
                {settings.twilio_numbers.join(", ")}
              </p>
            )}
          </div>

          <div className="flex items-center gap-3">
            <button
              type="submit"
              disabled={saveSettings.isPending}
              className="px-4 py-2 text-sm bg-brand-sky text-white rounded-lg hover:bg-brand-sky/80 disabled:opacity-50"
            >
              {saveSettings.isPending ? "Saving..." : "Save Settings"}
            </button>
            {saveMessage && (
              <span className="text-sm text-success">{saveMessage}</span>
            )}
          </div>
        </form>
      </div>

      {/* Members */}
      <div className="bg-card-bg rounded-lg border border-card-border">
        <div className="p-4 border-b border-card-border flex items-center justify-between">
          <h3 className="font-semibold text-page-text">Members</h3>
          <button
            onClick={() => setShowAddMember(true)}
            className="flex items-center gap-2 px-3 py-1.5 bg-brand-sky text-white rounded-lg hover:bg-brand-sky/80 text-sm"
          >
            <UserPlus className="w-4 h-4" />
            Add Member
          </button>
        </div>
        <table className="w-full">
          <thead>
            <tr className="border-b border-card-border text-left text-sm text-page-text-secondary">
              <th className="p-4 font-medium">Name</th>
              <th className="p-4 font-medium">Email</th>
              <th className="p-4 font-medium">Role</th>
              <th className="p-4 font-medium">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-page-divider">
            {members?.map((m) => (
              <tr key={m.user_id} className="hover:bg-page-hover">
                <td className="p-4 text-sm font-medium text-page-text">
                  {m.name}
                </td>
                <td className="p-4 text-sm text-page-text-secondary">
                  <EmailLink email={m.email} />
                </td>
                <td className="p-4">
                  {m.is_admin ? (
                    <span className="inline-flex items-center gap-1 text-xs px-2 py-0.5 bg-accent-lavender/15 text-accent-lavender rounded-full">
                      <Shield className="w-3 h-3" />
                      Admin
                    </span>
                  ) : (
                    <span className="text-xs text-page-text-muted">Member</span>
                  )}
                </td>
                <td className="p-4 flex gap-3">
                  <button
                    onClick={() => {
                      if (m.is_admin) {
                        setDemotingAdmin(m);
                      } else {
                        toggleAdmin.mutate({
                          userId: m.user_id,
                          isAdmin: true,
                        });
                      }
                    }}
                    className="text-xs px-2.5 py-1 border border-brand-sky text-brand-sky rounded-md hover:bg-brand-sky/10 transition-colors"
                  >
                    {m.is_admin ? "Remove Admin" : "Make Admin"}
                  </button>
                  <button
                    onClick={() => setRemovingMember(m)}
                    className="text-xs px-2.5 py-1 border border-danger text-danger rounded-md hover:bg-danger/10 transition-colors"
                  >
                    <Trash2 className="w-3 h-3 inline" /> Remove
                  </button>
                </td>
              </tr>
            ))}
            {members?.length === 0 && (
              <tr>
                <td colSpan={4} className="p-6 text-center text-page-text-muted">
                  No members yet
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      <ConfirmDialog
        open={!!removingMember}
        title="Remove Member"
        message={
          <>
            Remove{" "}
            <span className="font-semibold text-page-text">{removingMember?.name}</span>{" "}
            from this tenant?
          </>
        }
        warning="They will lose access to this tenant's calls, contacts, templates, and settings."
        confirmLabel="Remove Member"
        onConfirm={() => {
          if (removingMember) removeMember.mutate(removingMember.user_id);
          setRemovingMember(null);
        }}
        onCancel={() => setRemovingMember(null)}
      />

      <ConfirmDialog
        open={!!demotingAdmin}
        title="Remove Tenant Admin"
        message={
          <>
            Remove tenant admin access from{" "}
            <span className="font-semibold text-page-text">{demotingAdmin?.name}</span>?
          </>
        }
        warning="They will remain a member of this tenant but will no longer be able to manage settings, members, or templates."
        confirmLabel="Remove Admin"
        onConfirm={() => {
          if (demotingAdmin) {
            toggleAdmin.mutate({ userId: demotingAdmin.user_id, isAdmin: false });
          }
          setDemotingAdmin(null);
        }}
        onCancel={() => setDemotingAdmin(null)}
      />

      {/* Add member modal */}
      {showAddMember && (
        <div className="fixed inset-0 bg-black/30 flex items-center justify-center z-50">
          <div className="bg-card-bg rounded-xl shadow-lg w-full max-w-md p-6">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg font-semibold text-page-text">
                Add Member
              </h3>
              <button
                onClick={() => setShowAddMember(false)}
                className="p-1 hover:bg-page-hover rounded"
              >
                <X className="w-5 h-5 text-page-text" />
              </button>
            </div>
            <form onSubmit={handleAddMember} className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-page-text mb-1">
                  Email
                </label>
                <input
                  name="email"
                  type="email"
                  required
                  className="w-full px-3 py-2 border border-card-border rounded-lg text-sm bg-page-bg-tertiary text-page-text"
                  placeholder="user@example.com"
                />
                <p className="text-xs text-page-text-muted mt-1">
                  The user must have signed in at least once before they can
                  be added.
                </p>
              </div>
              <label className="flex items-center gap-2">
                <input type="checkbox" name="is_admin" />
                <span className="text-sm text-page-text">
                  Make this user an administrator
                </span>
              </label>
              <div className="flex justify-end gap-3 pt-2">
                <button
                  type="button"
                  onClick={() => setShowAddMember(false)}
                  className="px-4 py-2 text-sm text-page-text-secondary hover:bg-page-hover rounded-lg"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={addMember.isPending}
                  className="px-4 py-2 text-sm bg-brand-sky text-white rounded-lg hover:bg-brand-sky/80 disabled:opacity-50"
                >
                  Add
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
