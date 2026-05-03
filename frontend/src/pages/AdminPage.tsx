import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Plus, Shield, Trash2, X } from "lucide-react";
import { useState } from "react";
import { ConfirmDialog } from "../components/ConfirmDialog";
import { Dropdown } from "../components/Dropdown";
import { PageLoadingSpinner } from "../components/LoadingSpinner";
import { useDocumentTitle } from "../hooks/useDocumentTitle";
import { apiFetch } from "../lib/api";
import { ScrollLock } from "../hooks/useBodyScrollLock";

interface TenantData {
  id: string;
  name: string;
  slug: string;
  settings: Record<string, unknown>;
  organization_id?: string;
  organization_name?: string | null;
  user_count: number;
  created_at: string;
}

interface OrganizationData {
  id: string;
  name: string;
  slug: string;
  description: string | null;
  tenant_count: number;
  phone_number_count: number;
  created_at: string;
}

interface TwilioNumberData {
  sid: string;
  e164: string;
  friendly_name: string | null;
  voice_url: string | null;
  phone_number_id: string | null;
  organization_id: string | null;
  organization_name: string | null;
  tenant_id: string | null;
}

interface UserData {
  id: string;
  email: string;
  name: string;
  is_superadmin: boolean;
  tenant_id: string | null;
  tenant_name: string | null;
  created_at: string;
}

export function AdminPage() {
  useDocumentTitle("Administration");
  const queryClient = useQueryClient();
  const [showOrgForm, setShowOrgForm] = useState(false);
  const [editingOrg, setEditingOrg] = useState<OrganizationData | null>(null);
  const [editOrgName, setEditOrgName] = useState("");
  const [editOrgError, setEditOrgError] = useState<string | null>(null);
  const [assigningUser, setAssigningUser] = useState<UserData | null>(null);
  const [deletingOrg, setDeletingOrg] = useState<OrganizationData | null>(null);
  const [deletingUser, setDeletingUser] = useState<UserData | null>(null);
  const [removingAdmin, setRemovingAdmin] = useState<UserData | null>(null);
  const [orgFormError, setOrgFormError] = useState<string | null>(null);
  const [twilioError, setTwilioError] = useState<string | null>(null);

  const { data: organizations, isLoading: orgsLoading } = useQuery({
    queryKey: ["admin", "organizations"],
    queryFn: () => apiFetch<OrganizationData[]>("/api/admin/organizations"),
  });

  const { data: tenants, isLoading: tenantsLoading } = useQuery({
    queryKey: ["admin", "tenants"],
    queryFn: () => apiFetch<TenantData[]>("/api/admin/tenants"),
  });

  const { data: users, isLoading: usersLoading } = useQuery({
    queryKey: ["admin", "users"],
    queryFn: () => apiFetch<UserData[]>("/api/admin/users"),
  });

  const { data: twilioNumbers, isLoading: numbersLoading, error: numbersError } = useQuery({
    queryKey: ["admin", "twilio-numbers"],
    queryFn: () => apiFetch<TwilioNumberData[]>("/api/admin/twilio/numbers"),
    retry: false,
  });

  const createOrganization = useMutation({
    mutationFn: (data: Record<string, unknown>) =>
      apiFetch("/api/admin/organizations", {
        method: "POST",
        body: JSON.stringify(data),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["admin", "organizations"] });
      setShowOrgForm(false);
      setOrgFormError(null);
    },
    onError: (err: Error) => setOrgFormError(err.message),
  });

  const updateOrganization = useMutation({
    mutationFn: (vars: { id: string; name: string }) =>
      apiFetch(`/api/admin/organizations/${vars.id}`, {
        method: "PUT",
        body: JSON.stringify({ name: vars.name }),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["admin", "organizations"] });
      setEditingOrg(null);
      setEditOrgError(null);
    },
    onError: (err: Error) => setEditOrgError(err.message),
  });

  const deleteOrganization = useMutation({
    mutationFn: (id: string) =>
      apiFetch(`/api/admin/organizations/${id}`, { method: "DELETE" }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["admin"] });
    },
  });

  const assignNumberToOrg = useMutation({
    mutationFn: (vars: { orgId: string; sid: string }) =>
      apiFetch(`/api/admin/organizations/${vars.orgId}/numbers`, {
        method: "POST",
        body: JSON.stringify({ sid: vars.sid }),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["admin", "twilio-numbers"] });
      queryClient.invalidateQueries({ queryKey: ["admin", "organizations"] });
      setTwilioError(null);
    },
    onError: (err: Error) => setTwilioError(err.message),
  });

  const unassignNumberFromOrg = useMutation({
    mutationFn: (vars: { orgId: string; phoneNumberId: string }) =>
      apiFetch(
        `/api/admin/organizations/${vars.orgId}/numbers/${vars.phoneNumberId}`,
        { method: "DELETE" }
      ),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["admin", "twilio-numbers"] });
      queryClient.invalidateQueries({ queryKey: ["admin", "organizations"] });
      setTwilioError(null);
    },
    onError: (err: Error) => setTwilioError(err.message),
  });

  // Reassign a number to a different org (or unassign). Handles all three
  // transitions: assign to org, unassign, reassign between orgs.
  const handleNumberAssignment = async (
    n: TwilioNumberData,
    nextOrgId: string
  ) => {
    setTwilioError(null);
    try {
      // Same org → no-op
      if (n.organization_id === (nextOrgId || null)) return;
      // Currently assigned somewhere → unassign first
      if (n.organization_id && n.phone_number_id) {
        await unassignNumberFromOrg.mutateAsync({
          orgId: n.organization_id,
          phoneNumberId: n.phone_number_id,
        });
      }
      // Assigning to a new org
      if (nextOrgId) {
        await assignNumberToOrg.mutateAsync({ orgId: nextOrgId, sid: n.sid });
      }
    } catch {
      // mutation onError already set the error
    }
  };

  const updateUser = useMutation({
    mutationFn: ({ id, ...data }: { id: string } & Record<string, unknown>) =>
      apiFetch(`/api/admin/users/${id}`, {
        method: "PUT",
        body: JSON.stringify(data),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["admin"] });
      setAssigningUser(null);
    },
  });

  const deleteUser = useMutation({
    mutationFn: (id: string) =>
      apiFetch(`/api/admin/users/${id}`, { method: "DELETE" }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["admin", "users"] });
    },
  });

  const handleOrgSubmit = (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    setOrgFormError(null);
    const form = new FormData(e.currentTarget);
    createOrganization.mutate({
      name: form.get("name"),
    });
  };

  if (tenantsLoading || usersLoading || orgsLoading) {
    return <PageLoadingSpinner />;
  }

  return (
    <div className="p-6 space-y-8">
      <h2 className="text-2xl font-bold text-page-text">Administration</h2>

      {/* Organizations */}
      <section>
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-semibold text-page-text">Organizations</h3>
          <button
            onClick={() => {
              setOrgFormError(null);
              setShowOrgForm(true);
            }}
            className="flex items-center gap-2 px-3 py-1.5 bg-brand-sky text-white rounded-lg hover:bg-brand-sky/80 text-sm"
          >
            <Plus className="w-4 h-4" />
            New Organization
          </button>
        </div>
        <div className="bg-card-bg rounded-lg border border-card-border">
          <div className="overflow-x-auto"><table className="w-full min-w-[640px]">
            <thead>
              <tr className="border-b border-card-border text-left text-sm text-page-text-secondary">
                <th className="p-4 font-medium">Name</th>
                <th className="p-4 font-medium">Slug</th>
                <th className="p-4 font-medium">Tenants</th>
                <th className="p-4 font-medium">Numbers</th>
                <th className="p-4 font-medium">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-page-divider">
              {organizations?.map((o) => (
                <tr key={o.id} className="hover:bg-page-hover">
                  <td className="p-4 text-sm font-medium text-page-text align-middle">{o.name}</td>
                  <td className="p-4 text-sm text-page-text-secondary align-middle">{o.slug}</td>
                  <td className="p-4 text-sm text-page-text-secondary align-middle">{o.tenant_count}</td>
                  <td className="p-4 text-sm text-page-text-secondary align-middle">{o.phone_number_count}</td>
                  <td className="p-4 align-middle">
                    <div className="flex gap-2">
                      <button
                        onClick={() => {
                          setEditingOrg(o);
                          setEditOrgName(o.name);
                          setEditOrgError(null);
                        }}
                        className="text-xs px-2.5 py-1 border border-brand-sky text-brand-sky rounded-md hover:bg-brand-sky/10 transition-colors"
                      >
                        Edit
                      </button>
                      <button
                        onClick={() => setDeletingOrg(o)}
                        className="text-xs px-2.5 py-1 border border-danger text-danger rounded-md hover:bg-danger/10 transition-colors"
                      >
                        Delete
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
              {organizations?.length === 0 && (
                <tr>
                  <td colSpan={5} className="p-8 text-center text-page-text-muted">
                    No organizations yet
                  </td>
                </tr>
              )}
            </tbody>
          </table></div>
        </div>
      </section>

      {/* Phone Numbers (Twilio account → Organizations) */}
      <section>
        <div className="mb-4">
          <h3 className="text-lg font-semibold text-page-text">Phone Numbers</h3>
          <p className="text-xs text-page-text-secondary mt-1">
            Numbers from your Twilio account. Assign each one to an
            organization to make it available in their number pool.
          </p>
        </div>
        {twilioError && (
          <div className="mb-3 p-3 rounded-lg bg-danger/10 border border-danger/30 text-danger text-sm">
            {twilioError}
          </div>
        )}
        <div className="bg-card-bg rounded-lg border border-card-border">
          {numbersLoading ? (
            <div className="p-8 text-center text-page-text-muted">
              Loading numbers from Twilio…
            </div>
          ) : numbersError ? (
            <div className="p-6 text-sm text-danger">
              Failed to fetch Twilio numbers:{" "}
              {numbersError instanceof Error
                ? numbersError.message
                : String(numbersError)}
            </div>
          ) : (
            <div className="overflow-x-auto"><table className="w-full min-w-[640px]">
              <thead>
                <tr className="border-b border-card-border text-left text-sm text-page-text-secondary">
                  <th className="p-4 font-medium">Number</th>
                  <th className="p-4 font-medium">Friendly Name</th>
                  <th className="p-4 font-medium w-72">Organization</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-page-divider">
                {twilioNumbers?.map((n) => (
                  <tr key={n.sid} className="hover:bg-page-hover">
                    <td className="p-4 text-sm font-mono text-page-text align-middle">{n.e164}</td>
                    <td className="p-4 text-sm text-page-text-secondary align-middle">
                      {n.friendly_name ?? "—"}
                    </td>
                    <td className="p-4 align-middle">
                      <Dropdown
                        value={n.organization_id ?? ""}
                        onChange={(v) => handleNumberAssignment(n, v)}
                        options={[
                          { value: "", label: "Unassigned" },
                          ...(organizations ?? []).map((o) => ({
                            value: o.id,
                            label: o.name,
                          })),
                        ]}
                      />
                    </td>
                  </tr>
                ))}
                {twilioNumbers?.length === 0 && (
                  <tr>
                    <td colSpan={3} className="p-8 text-center text-page-text-muted">
                      No numbers on the Twilio account
                    </td>
                  </tr>
                )}
              </tbody>
            </table></div>
          )}
        </div>
      </section>

      {/* Users */}
      <section>
        <h3 className="text-lg font-semibold text-page-text mb-4">Users</h3>
        <div className="bg-card-bg rounded-lg border border-card-border">
          <div className="overflow-x-auto"><table className="w-full min-w-[640px]">
            <thead>
              <tr className="border-b border-card-border text-left text-sm text-page-text-secondary">
                <th className="p-4 font-medium">Name</th>
                <th className="p-4 font-medium">Email</th>
                <th className="p-4 font-medium">Tenant</th>
                <th className="p-4 font-medium">Role</th>
                <th className="p-4 font-medium">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-page-divider">
              {users?.map((u) => (
                <tr key={u.id} className="hover:bg-page-hover">
                  <td className="p-4 text-sm font-medium text-page-text align-middle">{u.name}</td>
                  <td className="p-4 text-sm text-page-text-secondary align-middle">{u.email}</td>
                  <td className="p-4 align-middle">
                    {u.tenant_name ? (
                      <span className="text-sm text-page-text">{u.tenant_name}</span>
                    ) : (
                      <span className="text-xs px-2 py-0.5 bg-warning/15 text-warning rounded-full">
                        Unassigned
                      </span>
                    )}
                  </td>
                  <td className="p-4 align-middle">
                    {u.is_superadmin && (
                      <span className="flex items-center gap-1 text-xs text-purple-600">
                        <Shield className="w-3 h-3" />
                        Admin
                      </span>
                    )}
                  </td>
                  <td className="p-4 align-middle">
                    <div className="flex gap-2">
                      <button
                        onClick={() => setAssigningUser(u)}
                        className="text-xs px-2.5 py-1 border border-brand-sky text-brand-sky rounded-md hover:bg-brand-sky/10 transition-colors"
                      >
                        Assign Tenant
                      </button>
                      <button
                        onClick={() => {
                          if (u.is_superadmin) {
                            setRemovingAdmin(u);
                          } else {
                            updateUser.mutate({
                              id: u.id,
                              is_superadmin: true,
                            });
                          }
                        }}
                        className="text-xs px-2.5 py-1 border border-accent-lavender text-accent-lavender rounded-md hover:bg-accent-lavender/10 transition-colors"
                      >
                        {u.is_superadmin ? "Remove Admin" : "Make Admin"}
                      </button>
                      <button
                        onClick={() => setDeletingUser(u)}
                        className="text-xs px-2.5 py-1 border border-danger text-danger rounded-md hover:bg-danger/10 transition-colors"
                      >
                        <Trash2 className="w-3 h-3" />
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table></div>
        </div>
      </section>

      {/* Edit Organization Modal */}
      {editingOrg && (
        <div className="fixed inset-0 bg-black/30 flex items-center justify-center z-50">
          <ScrollLock />
          <div className="bg-card-bg rounded-xl shadow-lg w-full max-w-md p-6">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg font-semibold text-page-text">
                Edit Organization
              </h3>
              <button
                onClick={() => setEditingOrg(null)}
                className="p-1 hover:bg-page-hover rounded"
              >
                <X className="w-5 h-5 text-page-text" />
              </button>
            </div>
            {editOrgError && (
              <div className="mb-4 p-3 rounded-lg bg-danger/10 border border-danger/30 text-danger text-sm">
                {editOrgError}
              </div>
            )}
            <form
              onSubmit={(e) => {
                e.preventDefault();
                if (!editingOrg) return;
                updateOrganization.mutate({
                  id: editingOrg.id,
                  name: editOrgName.trim(),
                });
              }}
              className="space-y-4"
            >
              <div>
                <label className="block text-sm font-medium text-page-text mb-1">
                  Name
                </label>
                <input
                  required
                  value={editOrgName}
                  onChange={(e) => setEditOrgName(e.target.value)}
                  className="w-full px-3 py-2 border border-card-border rounded-lg text-sm bg-page-bg-tertiary text-page-text"
                />
                <p className="text-xs text-page-text-muted mt-1">
                  The slug will update automatically to match the new name.
                </p>
              </div>
              <div className="flex justify-end gap-3 pt-2">
                <button
                  type="button"
                  onClick={() => setEditingOrg(null)}
                  className="px-4 py-2 text-sm text-page-text-secondary hover:bg-page-hover rounded-lg"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={updateOrganization.isPending}
                  className="px-4 py-2 text-sm bg-brand-sky text-white rounded-lg hover:bg-brand-sky/80 disabled:opacity-50"
                >
                  {updateOrganization.isPending ? "Saving..." : "Save"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Create Organization Modal */}
      {showOrgForm && (
        <div className="fixed inset-0 bg-black/30 flex items-center justify-center z-50">
          <ScrollLock />
          <div className="bg-card-bg rounded-xl shadow-lg w-full max-w-md p-6">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg font-semibold text-page-text">
                New Organization
              </h3>
              <button
                onClick={() => setShowOrgForm(false)}
                className="p-1 hover:bg-page-hover rounded"
              >
                <X className="w-5 h-5 text-page-text" />
              </button>
            </div>
            {orgFormError && (
              <div className="mb-4 p-3 rounded-lg bg-danger/10 border border-danger/30 text-danger text-sm">
                {orgFormError}
              </div>
            )}
            <form onSubmit={handleOrgSubmit} className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-page-text mb-1">
                  Name
                </label>
                <input
                  name="name"
                  required
                  className="w-full px-3 py-2 border border-card-border rounded-lg text-sm bg-page-bg-tertiary text-page-text"
                  placeholder="Acme Corp"
                />
              </div>
              <div className="flex justify-end gap-3 pt-2">
                <button
                  type="button"
                  onClick={() => setShowOrgForm(false)}
                  className="px-4 py-2 text-sm text-page-text-secondary hover:bg-page-hover rounded-lg"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={createOrganization.isPending}
                  className="px-4 py-2 text-sm bg-brand-sky text-white rounded-lg hover:bg-brand-sky/80 disabled:opacity-50"
                >
                  {createOrganization.isPending ? "Creating..." : "Create"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      <ConfirmDialog
        open={!!deletingOrg}
        title="Delete Organization"
        message={
          <>
            Delete{" "}
            <span className="font-semibold text-page-text">{deletingOrg?.name}</span>?
          </>
        }
        warning="The organization must have zero tenants before it can be deleted. Any phone numbers it owns will have their voice webhooks cleared."
        confirmLabel="Delete Organization"
        onConfirm={() => {
          if (deletingOrg) deleteOrganization.mutate(deletingOrg.id);
          setDeletingOrg(null);
        }}
        onCancel={() => setDeletingOrg(null)}
      />

      <ConfirmDialog
        open={!!deletingUser}
        title="Delete User"
        message={
          <>
            Are you sure you want to delete{" "}
            <span className="font-semibold text-page-text">{deletingUser?.name}</span>{" "}
            ({deletingUser?.email})?
          </>
        }
        warning="The user will lose access immediately. They can sign back in with Google, but their tenant memberships and admin status will need to be re-assigned."
        confirmLabel="Delete User"
        onConfirm={() => {
          if (deletingUser) deleteUser.mutate(deletingUser.id);
          setDeletingUser(null);
        }}
        onCancel={() => setDeletingUser(null)}
      />

      <ConfirmDialog
        open={!!removingAdmin}
        title="Remove Superadmin"
        message={
          <>
            Remove superadmin access from{" "}
            <span className="font-semibold text-page-text">{removingAdmin?.name}</span>?
          </>
        }
        warning="They will lose access to the Administration page and all cross-tenant controls."
        confirmLabel="Remove Admin"
        onConfirm={() => {
          if (removingAdmin) {
            updateUser.mutate({ id: removingAdmin.id, is_superadmin: false });
          }
          setRemovingAdmin(null);
        }}
        onCancel={() => setRemovingAdmin(null)}
      />

      {assigningUser && (
        <div className="fixed inset-0 bg-black/30 flex items-center justify-center z-50">
          <ScrollLock />
          <div className="bg-card-bg rounded-xl shadow-lg w-full max-w-sm p-6">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg font-semibold text-page-text">
                Assign {assigningUser.name}
              </h3>
              <button
                onClick={() => setAssigningUser(null)}
                className="p-1 hover:bg-page-hover rounded"
              >
                <X className="w-5 h-5 text-page-text" />
              </button>
            </div>
            <div className="space-y-2">
              <button
                onClick={() =>
                  updateUser.mutate({
                    id: assigningUser.id,
                    tenant_id: null,
                  })
                }
                className="w-full text-left px-3 py-2 text-sm rounded-lg hover:bg-page-hover text-page-text-secondary"
              >
                Unassigned
              </button>
              {tenants?.map((t) => (
                <button
                  key={t.id}
                  onClick={() =>
                    updateUser.mutate({
                      id: assigningUser.id,
                      tenant_id: t.id,
                    })
                  }
                  className={`w-full text-left px-3 py-2 text-sm rounded-lg hover:bg-page-hover ${
                    assigningUser.tenant_id === t.id
                      ? "bg-brand-sky/10 text-brand-sky"
                      : "text-page-text"
                  }`}
                >
                  {t.name}
                  <span className="text-page-text-muted ml-2">({t.slug})</span>
                </button>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
