import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  AlertTriangle,
  Check,
  Copy,
  Eye,
  EyeOff,
  Shield,
  Trash2,
  UserPlus,
  X,
} from "lucide-react";
import { useEffect, useState } from "react";
import { Navigate } from "react-router-dom";
import { ConfirmDialog } from "../components/ConfirmDialog";
import { Dropdown } from "../components/Dropdown";
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

interface PhoneNumberData {
  id: string;
  e164: string;
  friendly_name: string | null;
  inbound_enabled: boolean;
  outbound_enabled: boolean;
  sip_username: string | null;
  has_sip_user: boolean;
  inbound_mode: "none" | "sip" | "forward";
  inbound_forward_to: string | null;
}

interface SipCredentialResponse {
  username: string;
  password: string;
  sip_domain: string;
  sip_uri: string;
}

function CopyButton({ value, ariaLabel }: { value: string; ariaLabel: string }) {
  const [copied, setCopied] = useState(false);
  return (
    <button
      type="button"
      aria-label={ariaLabel}
      onClick={async () => {
        try {
          await navigator.clipboard.writeText(value);
          setCopied(true);
          setTimeout(() => setCopied(false), 1500);
        } catch {
          /* clipboard blocked */
        }
      }}
      className="p-1.5 text-page-text-muted hover:text-page-text rounded transition-colors"
    >
      {copied ? (
        <Check className="w-4 h-4 text-success" />
      ) : (
        <Copy className="w-4 h-4" />
      )}
    </button>
  );
}

function CredentialField({
  label,
  value,
  monospace = true,
}: {
  label: string;
  value: string;
  monospace?: boolean;
}) {
  return (
    <div>
      <label className="block text-xs font-medium text-page-text-muted uppercase tracking-wide mb-1">
        {label}
      </label>
      <div className="flex items-center gap-2 p-2 border border-card-border rounded-lg bg-page-bg-tertiary">
        <span
          className={`flex-1 text-sm text-page-text break-all ${
            monospace ? "font-mono" : ""
          }`}
        >
          {value}
        </span>
        <CopyButton value={value} ariaLabel={`Copy ${label}`} />
      </div>
    </div>
  );
}

function PasswordField({ value }: { value: string }) {
  const [shown, setShown] = useState(false);
  return (
    <div>
      <label className="block text-xs font-medium text-page-text-muted uppercase tracking-wide mb-1">
        Password
      </label>
      <div className="flex items-center gap-2 p-2 border border-card-border rounded-lg bg-page-bg-tertiary">
        <span className="flex-1 text-sm font-mono text-page-text break-all select-all">
          {shown ? value : "•".repeat(Math.min(value.length, 24))}
        </span>
        <button
          type="button"
          aria-label={shown ? "Hide password" : "Show password"}
          onClick={() => setShown((v) => !v)}
          className="p-1.5 text-page-text-muted hover:text-page-text rounded transition-colors"
        >
          {shown ? (
            <EyeOff className="w-4 h-4" />
          ) : (
            <Eye className="w-4 h-4" />
          )}
        </button>
        <CopyButton value={value} ariaLabel="Copy password" />
      </div>
    </div>
  );
}

function CredentialRevealModal({
  creds,
  onClose,
}: {
  creds: SipCredentialResponse;
  onClose: () => void;
}) {
  const [acknowledged, setAcknowledged] = useState(false);
  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-[60]">
      <div className="bg-card-bg rounded-xl shadow-lg w-full max-w-lg p-6 max-h-[90vh] overflow-y-auto">
        <div className="flex items-center gap-3 mb-3">
          <div className="p-2 bg-warning/15 rounded-full">
            <AlertTriangle className="w-5 h-5 text-warning" />
          </div>
          <h3 className="text-lg font-semibold text-page-text">
            SIP Credentials Created
          </h3>
        </div>
        <p className="text-sm text-page-text-secondary mb-4">
          Copy these credentials into the SIP device now. The password
          is shown <strong className="text-page-text">only once</strong>: once
          you close this dialog, it cannot be retrieved. If you lose it, delete
          the SIP user and create a new one.
        </p>
        <div className="space-y-3">
          <CredentialField label="SIP Domain" value={creds.sip_domain} />
          <CredentialField label="Username" value={creds.username} />
          <PasswordField value={creds.password} />
          <CredentialField label="Full SIP URI" value={creds.sip_uri} />
        </div>
        <label className="flex items-start gap-2 mt-5 mb-2">
          <input
            type="checkbox"
            checked={acknowledged}
            onChange={(e) => setAcknowledged(e.target.checked)}
            className="mt-0.5"
          />
          <span className="text-sm text-page-text">
            I have copied the password somewhere safe.
          </span>
        </label>
        <div className="flex justify-end pt-2">
          <button
            type="button"
            onClick={onClose}
            disabled={!acknowledged}
            className="px-4 py-2 text-sm bg-brand-sky text-white rounded-lg hover:bg-brand-sky/80 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            Done
          </button>
        </div>
      </div>
    </div>
  );
}

export function TenantSettingsPage() {
  useDocumentTitle("Tenant Settings");
  const { tenant, isTenantAdmin, refresh } = useAuth();
  const queryClient = useQueryClient();
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [context, setContext] = useState("");
  const [saveMessage, setSaveMessage] = useState<string | null>(null);
  const [showAddMember, setShowAddMember] = useState(false);
  const [removingMember, setRemovingMember] = useState<Member | null>(null);
  const [demotingAdmin, setDemotingAdmin] = useState<Member | null>(null);
  const [editingNumber, setEditingNumber] = useState<PhoneNumberData | null>(null);
  const [editFriendlyName, setEditFriendlyName] = useState("");
  const [editInbound, setEditInbound] = useState(true);
  const [editOutbound, setEditOutbound] = useState(false);
  const [editInboundMode, setEditInboundMode] = useState<"none" | "sip" | "forward">("none");
  const [editForwardTo, setEditForwardTo] = useState("");
  const [editError, setEditError] = useState<string | null>(null);
  const [revealedCreds, setRevealedCreds] = useState<SipCredentialResponse | null>(null);
  const [removingSipUser, setRemovingSipUser] = useState<PhoneNumberData | null>(null);

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
    }
  }, [settings]);

  const { data: members, isLoading: membersLoading } = useQuery({
    queryKey: ["tenant-members", tenant?.id],
    queryFn: () =>
      apiFetch<Member[]>(`/api/v1/tenants/${tenant!.id}/members`),
    enabled: !!tenant && isTenantAdmin,
  });

  const { data: phoneNumbers, isLoading: phoneNumbersLoading } = useQuery({
    queryKey: ["tenant-numbers", tenant?.id],
    queryFn: () =>
      apiFetch<PhoneNumberData[]>(`/api/v1/tenants/${tenant!.id}/numbers`),
    enabled: !!tenant && isTenantAdmin,
  });

  const updateNumber = useMutation({
    mutationFn: (vars: {
      numberId: string;
      inbound_enabled?: boolean;
      outbound_enabled?: boolean;
      friendly_name?: string | null;
      inbound_mode?: "none" | "sip" | "forward";
      inbound_forward_to?: string | null;
    }) => {
      const { numberId, ...body } = vars;
      return apiFetch(
        `/api/v1/tenants/${tenant!.id}/numbers/${numberId}`,
        {
          method: "PUT",
          body: JSON.stringify(body),
        }
      );
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["tenant-numbers", tenant?.id] });
      setEditingNumber(null);
      setEditError(null);
    },
    onError: (err: Error) => setEditError(err.message),
  });

  const createSipUser = useMutation({
    mutationFn: (numberId: string) =>
      apiFetch<SipCredentialResponse>(
        `/api/v1/tenants/${tenant!.id}/numbers/${numberId}/sip-user`,
        { method: "POST" }
      ),
    onSuccess: (data) => {
      setRevealedCreds(data);
      queryClient.invalidateQueries({ queryKey: ["tenant-numbers", tenant?.id] });
    },
    onError: (err: Error) => setEditError(err.message),
  });

  const deleteSipUser = useMutation({
    mutationFn: (numberId: string) =>
      apiFetch(
        `/api/v1/tenants/${tenant!.id}/numbers/${numberId}/sip-user`,
        { method: "DELETE" }
      ),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["tenant-numbers", tenant?.id] });
      setRemovingSipUser(null);
    },
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

  if (settingsLoading || membersLoading || phoneNumbersLoading) {
    return <PageLoadingSpinner />;
  }

  const handleSave = (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    saveSettings.mutate({
      context: context || null,
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
            <p className="block text-sm font-medium text-page-text mb-1">
              Name
            </p>
            <p className="text-sm text-page-text-secondary">{name}</p>
          </div>

          <div>
            <p className="block text-sm font-medium text-page-text mb-1">
              Description
            </p>
            <p className="text-sm text-page-text-secondary">
              {description || "—"}
            </p>
          </div>

          <div>
            <label className="block text-sm font-medium text-page-text mb-1">
              Context
            </label>
            <p className="text-xs text-page-text-secondary mb-2">
              Describe the kinds of calls that happen here — whether on
              behalf of a business, a team, or just you personally. This
              context is provided to the LLM during analysis so insights
              are evaluated through the right lens. For a business, that
              might be: "We're a university admissions office. Our calls
              are usually with prospective students or parents discussing
              application deadlines, financial aid, campus visits, and
              program requirements." For an individual, it might be:
              "Personal line. Most calls are with contractors about home
              repairs, appointments with my doctor's office, or family."
            </p>
            <textarea
              value={context}
              onChange={(e) => setContext(e.target.value)}
              rows={8}
              className="w-full px-3 py-2 border border-card-border rounded-lg text-sm bg-page-bg-tertiary text-page-text"
              placeholder="Describe who's on this line and the typical reasons for calls..."
            />
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

      {/* Phone numbers */}
      <div className="bg-card-bg rounded-lg border border-card-border mb-6">
        <div className="p-4 border-b border-card-border">
          <h3 className="font-semibold text-page-text">Phone Numbers</h3>
          <p className="text-xs text-page-text-secondary mt-1">
            Numbers your organization has assigned to this tenant. Click
            <span className="font-medium"> "Edit Configuration" </span>
            on a number to set its friendly name, allowed call directions,
            inbound call routing, and SIP device credentials.
          </p>
        </div>
        <table className="w-full">
          <thead>
            <tr className="border-b border-card-border text-left text-sm text-page-text-secondary">
              <th className="p-4 font-medium">Number</th>
              <th className="p-4 font-medium">Friendly Name</th>
              <th className="p-4 font-medium">Routing</th>
              <th className="p-4 font-medium">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-page-divider">
            {phoneNumbers?.map((p) => (
              <tr key={p.id} className="hover:bg-page-hover">
                <td className="p-4 text-sm font-mono text-page-text">{p.e164}</td>
                <td className="p-4 text-sm text-page-text-secondary">
                  {p.friendly_name ?? "—"}
                </td>
                <td className="p-4">
                  <div className="flex flex-wrap gap-1.5">
                    {p.inbound_enabled && (
                      <span className="text-xs px-2 py-0.5 rounded-full bg-brand-sky/10 text-brand-sky">
                        Inbound
                      </span>
                    )}
                    {p.outbound_enabled && (
                      <span className="text-xs px-2 py-0.5 rounded-full bg-accent-periwinkle/10 text-accent-periwinkle">
                        Outbound
                      </span>
                    )}
                    {!p.inbound_enabled && !p.outbound_enabled && (
                      <span className="text-xs px-2 py-0.5 rounded-full bg-page-divider text-page-text-muted">
                        Disabled
                      </span>
                    )}
                  </div>
                </td>
                <td className="p-4">
                  <button
                    onClick={() => {
                      setEditingNumber(p);
                      setEditFriendlyName(p.friendly_name ?? "");
                      setEditInbound(p.inbound_enabled);
                      setEditOutbound(p.outbound_enabled);
                      setEditInboundMode(p.inbound_mode);
                      setEditForwardTo(p.inbound_forward_to ?? "");
                      setEditError(null);
                    }}
                    className="text-xs px-2.5 py-1 border border-brand-sky text-brand-sky rounded-md hover:bg-brand-sky/10 transition-colors"
                  >
                    Edit Configuration
                  </button>
                </td>
              </tr>
            ))}
            {phoneNumbers?.length === 0 && (
              <tr>
                <td colSpan={4} className="p-6 text-center text-page-text-muted">
                  No numbers assigned to this tenant. Ask your organization
                  admin to assign one from the org's number pool.
                </td>
              </tr>
            )}
          </tbody>
        </table>
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

      {/* Edit number configuration modal */}
      {editingNumber && (() => {
        // Always read the live row from the current query so SIP user
        // create/delete updates show up immediately after the mutation.
        const liveNumber =
          phoneNumbers?.find((p) => p.id === editingNumber.id) ?? editingNumber;
        return (
        <div className="fixed inset-0 bg-black/30 flex items-center justify-center z-50">
          <div className="bg-card-bg rounded-xl shadow-lg w-full max-w-lg p-6 max-h-[90vh] overflow-y-auto">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg font-semibold text-page-text">
                Edit Configuration
              </h3>
              <button
                onClick={() => setEditingNumber(null)}
                className="p-1 hover:bg-page-hover rounded"
              >
                <X className="w-5 h-5 text-page-text" />
              </button>
            </div>
            <p className="text-sm font-mono text-page-text-secondary mb-4">
              {liveNumber.e164}
            </p>
            {editError && (
              <div className="mb-4 p-3 rounded-lg bg-danger/10 border border-danger/30 text-danger text-sm">
                {editError}
              </div>
            )}
            <form
              onSubmit={(e) => {
                e.preventDefault();
                if (editInboundMode === "sip" && !liveNumber.has_sip_user) {
                  setEditError(
                    "Create a SIP user below before setting inbound to ring it."
                  );
                  return;
                }
                if (editInboundMode === "forward" && !editForwardTo.trim()) {
                  setEditError(
                    "Enter a forwarding number for inbound mode 'forward'."
                  );
                  return;
                }
                updateNumber.mutate({
                  numberId: liveNumber.id,
                  friendly_name: editFriendlyName.trim() || null,
                  inbound_enabled: editInbound,
                  outbound_enabled: editOutbound,
                  inbound_mode: editInboundMode,
                  inbound_forward_to:
                    editInboundMode === "forward"
                      ? editForwardTo.trim() || null
                      : null,
                });
              }}
              className="space-y-5"
            >
              <div>
                <label className="block text-sm font-medium text-page-text mb-1">
                  Friendly Name
                </label>
                <input
                  type="text"
                  value={editFriendlyName}
                  onChange={(e) => setEditFriendlyName(e.target.value)}
                  className="w-full px-3 py-2 border border-card-border rounded-lg text-sm bg-page-bg-tertiary text-page-text"
                  placeholder="e.g. Sales main line"
                />
                <p className="text-xs text-page-text-muted mt-1">
                  Optional label shown alongside the number in dropdowns and
                  call lists.
                </p>
              </div>

              <div>
                <label className="block text-sm font-medium text-page-text mb-2">
                  Allowed Directions
                </label>
                <div className="space-y-2">
                  <label className="flex items-center gap-2">
                    <input
                      type="checkbox"
                      checked={editInbound}
                      onChange={(e) => setEditInbound(e.target.checked)}
                    />
                    <span className="text-sm text-page-text">
                      Accept inbound calls
                    </span>
                  </label>
                  <label className="flex items-center gap-2">
                    <input
                      type="checkbox"
                      checked={editOutbound}
                      onChange={(e) => setEditOutbound(e.target.checked)}
                    />
                    <span className="text-sm text-page-text">
                      Allow outbound calls
                    </span>
                  </label>
                </div>
              </div>

              {editInbound && (
                <div>
                  <label className="block text-sm font-medium text-page-text mb-1">
                    Inbound Routing
                  </label>
                  <p className="text-xs text-page-text-muted mb-2">
                    What should happen when this number receives a call?
                  </p>
                  <Dropdown
                    value={editInboundMode}
                    onChange={(v) =>
                      setEditInboundMode(v as "none" | "sip" | "forward")
                    }
                    options={[
                      {
                        value: "none",
                        label: "Record only (no ringing)",
                      },
                      {
                        value: "sip",
                        label: "Ring the SIP device on this number",
                      },
                      {
                        value: "forward",
                        label: "Forward to another number",
                      },
                    ]}
                  />
                  {editInboundMode === "forward" && (
                    <input
                      type="tel"
                      value={editForwardTo}
                      onChange={(e) => setEditForwardTo(e.target.value)}
                      placeholder="+15551234567"
                      className="mt-2 w-full px-3 py-2 border border-card-border rounded-lg text-sm bg-page-bg-tertiary text-page-text"
                    />
                  )}
                </div>
              )}

              {/* SIP user */}
              <div className="border-t border-card-border pt-4">
                <div className="flex items-center justify-between mb-2">
                  <div>
                    <label className="block text-sm font-medium text-page-text">
                      SIP Device User
                    </label>
                    <p className="text-xs text-page-text-muted mt-0.5">
                      Lets a SIP device register for this number, so calls
                      can be placed and received directly on the device.
                    </p>
                  </div>
                </div>
                {liveNumber.has_sip_user ? (
                  <div className="flex items-center justify-between gap-3 p-3 border border-card-border rounded-lg bg-page-bg-tertiary">
                    <div className="text-sm">
                      <p className="font-mono text-page-text">
                        {liveNumber.sip_username}
                      </p>
                      <p className="text-xs text-page-text-muted">
                        SIP user active
                      </p>
                    </div>
                    <button
                      type="button"
                      onClick={() => setRemovingSipUser(liveNumber)}
                      className="text-xs px-2.5 py-1 border border-danger text-danger rounded-md hover:bg-danger/10 transition-colors"
                    >
                      Delete
                    </button>
                  </div>
                ) : (
                  <button
                    type="button"
                    disabled={createSipUser.isPending}
                    onClick={() => createSipUser.mutate(liveNumber.id)}
                    className="px-3 py-1.5 text-sm border border-brand-sky text-brand-sky rounded-md hover:bg-brand-sky/10 transition-colors disabled:opacity-50"
                  >
                    {createSipUser.isPending ? "Creating..." : "Create SIP User"}
                  </button>
                )}
              </div>

              <div className="flex justify-end gap-3 pt-2">
                <button
                  type="button"
                  onClick={() => setEditingNumber(null)}
                  className="px-4 py-2 text-sm text-page-text-secondary hover:bg-page-hover rounded-lg"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={updateNumber.isPending}
                  className="px-4 py-2 text-sm bg-brand-sky text-white rounded-lg hover:bg-brand-sky/80 disabled:opacity-50"
                >
                  {updateNumber.isPending ? "Saving..." : "Save"}
                </button>
              </div>
            </form>
          </div>
        </div>
        );
      })()}

      {/* Reveal-once SIP credentials modal */}
      {revealedCreds && (
        <CredentialRevealModal
          creds={revealedCreds}
          onClose={() => setRevealedCreds(null)}
        />
      )}

      <ConfirmDialog
        open={!!removingSipUser}
        title="Delete SIP User"
        message={
          <>
            Delete the SIP user for{" "}
            <span className="font-semibold text-page-text">
              {removingSipUser?.e164}
            </span>
            ?
          </>
        }
        warning="The SIP device will immediately stop being able to register or place calls. You can mint a new credential afterwards if you change your mind, but the password is different each time."
        confirmLabel="Delete SIP User"
        onConfirm={() => {
          if (removingSipUser) deleteSipUser.mutate(removingSipUser.id);
        }}
        onCancel={() => setRemovingSipUser(null)}
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
