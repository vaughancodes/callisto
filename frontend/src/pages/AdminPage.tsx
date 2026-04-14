import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Plus, Shield, Trash2, X } from "lucide-react";
import { useState } from "react";
import { ConfirmDialog } from "../components/ConfirmDialog";
import { PageLoadingSpinner } from "../components/LoadingSpinner";
import { useDocumentTitle } from "../hooks/useDocumentTitle";
import { apiFetch } from "../lib/api";

interface TenantData {
  id: string;
  name: string;
  slug: string;
  settings: Record<string, unknown>;
  user_count: number;
  created_at: string;
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
  const [showTenantForm, setShowTenantForm] = useState(false);
  const [assigningUser, setAssigningUser] = useState<UserData | null>(null);
  const [deletingTenant, setDeletingTenant] = useState<TenantData | null>(null);
  const [deletingUser, setDeletingUser] = useState<UserData | null>(null);
  const [removingAdmin, setRemovingAdmin] = useState<UserData | null>(null);

  const { data: tenants, isLoading: tenantsLoading } = useQuery({
    queryKey: ["admin", "tenants"],
    queryFn: () => apiFetch<TenantData[]>("/api/admin/tenants"),
  });

  const { data: users, isLoading: usersLoading } = useQuery({
    queryKey: ["admin", "users"],
    queryFn: () => apiFetch<UserData[]>("/api/admin/users"),
  });

  const createTenant = useMutation({
    mutationFn: (data: Record<string, unknown>) =>
      apiFetch("/api/admin/tenants", {
        method: "POST",
        body: JSON.stringify(data),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["admin", "tenants"] });
      setShowTenantForm(false);
    },
  });

  const deleteTenant = useMutation({
    mutationFn: (id: string) =>
      apiFetch(`/api/admin/tenants/${id}`, { method: "DELETE" }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["admin"] });
    },
  });

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

  const handleTenantSubmit = (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    const form = new FormData(e.currentTarget);
    const twilio = form.get("twilio_numbers") as string;
    const settings: Record<string, unknown> = {};
    if (twilio.trim()) {
      settings.twilio_numbers = twilio.split(",").map((n) => n.trim());
    }
    createTenant.mutate({
      name: form.get("name"),
      slug: form.get("slug"),
      settings,
    });
  };

  if (tenantsLoading || usersLoading) {
    return <PageLoadingSpinner />;
  }

  return (
    <div className="p-6 space-y-8">
      <h2 className="text-2xl font-bold text-page-text">Administration</h2>

      {/* Tenants */}
      <section>
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-semibold text-page-text">Tenants</h3>
          <button
            onClick={() => setShowTenantForm(true)}
            className="flex items-center gap-2 px-3 py-1.5 bg-brand-sky text-white rounded-lg hover:bg-brand-sky/80 text-sm"
          >
            <Plus className="w-4 h-4" />
            New Tenant
          </button>
        </div>
        <div className="bg-card-bg rounded-lg border border-card-border">
          <table className="w-full">
            <thead>
              <tr className="border-b border-card-border text-left text-sm text-page-text-secondary">
                <th className="p-4 font-medium">Name</th>
                <th className="p-4 font-medium">Slug</th>
                <th className="p-4 font-medium">Users</th>
                <th className="p-4 font-medium">Twilio Numbers</th>
                <th className="p-4 font-medium">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-page-divider">
              {tenants?.map((t) => (
                <tr key={t.id} className="hover:bg-page-hover">
                  <td className="p-4 text-sm font-medium text-page-text">{t.name}</td>
                  <td className="p-4 text-sm text-page-text-secondary">{t.slug}</td>
                  <td className="p-4 text-sm text-page-text-secondary">{t.user_count}</td>
                  <td className="p-4 text-sm text-page-text-secondary">
                    {(
                      (t.settings?.twilio_numbers as string[]) ?? []
                    ).join(", ") || "—"}
                  </td>
                  <td className="p-4">
                    <button
                      onClick={() => setDeletingTenant(t)}
                      className="text-xs px-2.5 py-1 border border-danger text-danger rounded-md hover:bg-danger/10 transition-colors"
                    >
                      Delete
                    </button>
                  </td>
                </tr>
              ))}
              {tenants?.length === 0 && (
                <tr>
                  <td colSpan={5} className="p-8 text-center text-page-text-muted">
                    No tenants yet
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </section>

      {/* Users */}
      <section>
        <h3 className="text-lg font-semibold text-page-text mb-4">Users</h3>
        <div className="bg-card-bg rounded-lg border border-card-border">
          <table className="w-full">
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
                  <td className="p-4 text-sm font-medium text-page-text">{u.name}</td>
                  <td className="p-4 text-sm text-page-text-secondary">{u.email}</td>
                  <td className="p-4">
                    {u.tenant_name ? (
                      <span className="text-sm text-page-text">{u.tenant_name}</span>
                    ) : (
                      <span className="text-xs px-2 py-0.5 bg-warning/15 text-warning rounded-full">
                        Unassigned
                      </span>
                    )}
                  </td>
                  <td className="p-4">
                    {u.is_superadmin && (
                      <span className="flex items-center gap-1 text-xs text-purple-600">
                        <Shield className="w-3 h-3" />
                        Admin
                      </span>
                    )}
                  </td>
                  <td className="p-4 flex gap-2">
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
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      {/* Create Tenant Modal */}
      {showTenantForm && (
        <div className="fixed inset-0 bg-black/30 flex items-center justify-center z-50">
          <div className="bg-card-bg rounded-xl shadow-lg w-full max-w-md p-6">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg font-semibold text-page-text">New Tenant</h3>
              <button
                onClick={() => setShowTenantForm(false)}
                className="p-1 hover:bg-page-hover rounded"
              >
                <X className="w-5 h-5 text-page-text" />
              </button>
            </div>
            <form onSubmit={handleTenantSubmit} className="space-y-4">
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
              <div>
                <label className="block text-sm font-medium text-page-text mb-1">
                  Slug
                </label>
                <input
                  name="slug"
                  required
                  className="w-full px-3 py-2 border border-card-border rounded-lg text-sm bg-page-bg-tertiary text-page-text"
                  placeholder="acme"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-page-text mb-1">
                  Twilio Numbers (comma-separated)
                </label>
                <input
                  name="twilio_numbers"
                  className="w-full px-3 py-2 border border-card-border rounded-lg text-sm bg-page-bg-tertiary text-page-text"
                  placeholder="+15551234567, +15559876543"
                />
              </div>
              <div className="flex justify-end gap-3 pt-2">
                <button
                  type="button"
                  onClick={() => setShowTenantForm(false)}
                  className="px-4 py-2 text-sm text-page-text-secondary hover:bg-page-hover rounded-lg"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-4 py-2 text-sm bg-brand-sky text-white rounded-lg hover:bg-brand-sky/80"
                >
                  Create
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      <ConfirmDialog
        open={!!deletingTenant}
        title="Delete Tenant"
        message={
          <>
            Are you sure you want to delete{" "}
            <span className="font-semibold text-page-text">{deletingTenant?.name}</span>?
          </>
        }
        warning="This will permanently delete all calls, transcripts, insights, templates, and summaries associated with this tenant. This action cannot be undone."
        confirmLabel="Delete Tenant"
        onConfirm={() => {
          if (deletingTenant) deleteTenant.mutate(deletingTenant.id);
          setDeletingTenant(null);
        }}
        onCancel={() => setDeletingTenant(null)}
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
