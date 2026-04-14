import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Plus, Shield, UserPlus, X } from "lucide-react";
import { useEffect, useState } from "react";
import { Navigate } from "react-router-dom";
import { ConfirmDialog } from "../components/ConfirmDialog";
import { Dropdown } from "../components/Dropdown";
import { EmailLink } from "../components/LinkedContact";
import { PageLoadingSpinner } from "../components/LoadingSpinner";
import { useAuth } from "../contexts/AuthContext";
import { useDocumentTitle } from "../hooks/useDocumentTitle";
import { apiFetch } from "../lib/api";

interface OrganizationData {
  id: string;
  name: string;
  slug: string;
  description: string | null;
}

interface TenantBrief {
  id: string;
  name: string;
  slug: string;
  description: string | null;
}

interface PhoneNumberData {
  id: string;
  organization_id: string;
  tenant_id: string | null;
  e164: string;
  twilio_sid: string | null;
  inbound_enabled: boolean;
  outbound_enabled: boolean;
}

interface OrgAdminData {
  user_id: string;
  email: string;
  name: string;
  is_admin: boolean;
}

export function OrganizationSettingsPage() {
  useDocumentTitle("Organization Settings");
  const { tenant, isOrgAdmin } = useAuth();
  const queryClient = useQueryClient();

  const orgId = tenant?.organization_id ?? "";
  const allowed = !!orgId && isOrgAdmin(orgId);

  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [saveMessage, setSaveMessage] = useState<string | null>(null);
  const [showAddAdmin, setShowAddAdmin] = useState(false);
  const [showCreateTenant, setShowCreateTenant] = useState(false);
  const [editingTenant, setEditingTenant] = useState<TenantBrief | null>(null);
  const [editTenantName, setEditTenantName] = useState("");
  const [editTenantDescription, setEditTenantDescription] = useState("");
  const [removingTenant, setRemovingTenant] = useState<TenantBrief | null>(null);
  const [removingAdmin, setRemovingAdmin] = useState<OrgAdminData | null>(null);
  const [formError, setFormError] = useState<string | null>(null);

  const { data: org, isLoading: orgLoading } = useQuery({
    queryKey: ["organization", orgId],
    queryFn: () => apiFetch<OrganizationData>(`/api/v1/organizations/${orgId}`),
    enabled: allowed,
  });

  const { data: tenants, isLoading: tenantsLoading } = useQuery({
    queryKey: ["organization-tenants", orgId],
    queryFn: () =>
      apiFetch<TenantBrief[]>(`/api/v1/organizations/${orgId}/tenants`),
    enabled: allowed,
  });

  const { data: numbers, isLoading: numbersLoading } = useQuery({
    queryKey: ["organization-numbers", orgId],
    queryFn: () =>
      apiFetch<PhoneNumberData[]>(`/api/v1/organizations/${orgId}/numbers`),
    enabled: allowed,
  });

  const { data: admins, isLoading: adminsLoading } = useQuery({
    queryKey: ["organization-admins", orgId],
    queryFn: () =>
      apiFetch<OrgAdminData[]>(`/api/v1/organizations/${orgId}/admins`),
    enabled: allowed,
  });

  useEffect(() => {
    if (org) {
      setName(org.name);
      setDescription(org.description ?? "");
    }
  }, [org]);

  const saveOrg = useMutation({
    mutationFn: (data: Record<string, unknown>) =>
      apiFetch(`/api/v1/organizations/${orgId}`, {
        method: "PUT",
        body: JSON.stringify(data),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["organization", orgId] });
      setSaveMessage("Settings saved.");
      setTimeout(() => setSaveMessage(null), 3000);
    },
  });

  const assignNumber = useMutation({
    mutationFn: (vars: { numberId: string; tenantId: string | null }) =>
      apiFetch(
        `/api/v1/organizations/${orgId}/numbers/${vars.numberId}`,
        {
          method: "PUT",
          body: JSON.stringify({ tenant_id: vars.tenantId }),
        }
      ),
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: ["organization-numbers", orgId] }),
  });

  const addAdmin = useMutation({
    mutationFn: (data: { email: string }) =>
      apiFetch(`/api/v1/organizations/${orgId}/admins`, {
        method: "POST",
        body: JSON.stringify(data),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["organization-admins", orgId] });
      setShowAddAdmin(false);
      setFormError(null);
    },
    onError: (err: Error) => setFormError(err.message),
  });

  const removeAdmin = useMutation({
    mutationFn: (userId: string) =>
      apiFetch(`/api/v1/organizations/${orgId}/admins/${userId}`, {
        method: "DELETE",
      }),
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: ["organization-admins", orgId] }),
  });

  const createTenant = useMutation({
    mutationFn: (data: { name: string; description?: string }) =>
      apiFetch(`/api/v1/organizations/${orgId}/tenants`, {
        method: "POST",
        body: JSON.stringify(data),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["organization-tenants", orgId] });
      setShowCreateTenant(false);
      setFormError(null);
    },
    onError: (err: Error) => setFormError(err.message),
  });

  const updateTenant = useMutation({
    mutationFn: (vars: {
      tenantId: string;
      name: string;
      description: string | null;
    }) =>
      apiFetch(`/api/v1/organizations/${orgId}/tenants/${vars.tenantId}`, {
        method: "PUT",
        body: JSON.stringify({
          name: vars.name,
          description: vars.description,
        }),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["organization-tenants", orgId] });
      setEditingTenant(null);
      setFormError(null);
    },
    onError: (err: Error) => setFormError(err.message),
  });

  const deleteTenant = useMutation({
    mutationFn: (tenantId: string) =>
      apiFetch(`/api/v1/organizations/${orgId}/tenants/${tenantId}`, {
        method: "DELETE",
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["organization-tenants", orgId] });
      queryClient.invalidateQueries({ queryKey: ["organization-numbers", orgId] });
      setRemovingTenant(null);
    },
  });

  if (!tenant) return <Navigate to="/" replace />;
  if (!allowed) {
    return (
      <div className="p-6">
        <div className="text-page-text-secondary">
          You need to be an organization administrator to view these settings.
        </div>
      </div>
    );
  }

  if (orgLoading || tenantsLoading || numbersLoading || adminsLoading) {
    return <PageLoadingSpinner />;
  }

  const handleSave = (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    saveOrg.mutate({ description: description || null });
  };

  const handleAddAdmin = (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    setFormError(null);
    const form = new FormData(e.currentTarget);
    addAdmin.mutate({ email: (form.get("email") as string).trim() });
  };

  const handleCreateTenant = (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    setFormError(null);
    const form = new FormData(e.currentTarget);
    createTenant.mutate({
      name: (form.get("name") as string).trim(),
      description: ((form.get("description") as string) || "").trim() || undefined,
    });
  };

  return (
    <div className="p-6 max-w-4xl">
      <h2 className="text-2xl font-bold text-page-text mb-6">
        Organization Settings
      </h2>

      {/* General */}
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
            <label className="block text-sm font-medium text-page-text mb-1">
              Description
            </label>
            <input
              type="text"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              className="w-full px-3 py-2 border border-card-border rounded-lg text-sm bg-page-bg-tertiary text-page-text"
              placeholder="A short description of this organization"
            />
          </div>
          <div className="flex items-center gap-3">
            <button
              type="submit"
              disabled={saveOrg.isPending}
              className="px-4 py-2 text-sm bg-brand-sky text-white rounded-lg hover:bg-brand-sky/80 disabled:opacity-50"
            >
              {saveOrg.isPending ? "Saving..." : "Save Settings"}
            </button>
            {saveMessage && (
              <span className="text-sm text-success">{saveMessage}</span>
            )}
          </div>
        </form>
      </div>

      {/* Tenants */}
      <div className="bg-card-bg rounded-lg border border-card-border mb-6">
        <div className="p-4 border-b border-card-border flex items-center justify-between">
          <h3 className="font-semibold text-page-text">Tenants</h3>
          <button
            onClick={() => {
              setFormError(null);
              setShowCreateTenant(true);
            }}
            className="flex items-center gap-2 px-3 py-1.5 bg-brand-sky text-white rounded-lg hover:bg-brand-sky/80 text-sm"
          >
            <Plus className="w-4 h-4" />
            New Tenant
          </button>
        </div>
        <table className="w-full">
          <thead>
            <tr className="border-b border-card-border text-left text-sm text-page-text-secondary">
              <th className="p-4 font-medium">Name</th>
              <th className="p-4 font-medium">Slug</th>
              <th className="p-4 font-medium">Description</th>
              <th className="p-4 font-medium">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-page-divider">
            {tenants?.map((t) => (
              <tr key={t.id} className="hover:bg-page-hover">
                <td className="p-4 text-sm font-medium text-page-text">{t.name}</td>
                <td className="p-4 text-sm text-page-text-secondary">{t.slug}</td>
                <td className="p-4 text-sm text-page-text-secondary">
                  {t.description ?? "—"}
                </td>
                <td className="p-4 flex gap-2">
                  <button
                    onClick={() => {
                      setEditingTenant(t);
                      setEditTenantName(t.name);
                      setEditTenantDescription(t.description ?? "");
                      setFormError(null);
                    }}
                    className="text-xs px-2.5 py-1 border border-brand-sky text-brand-sky rounded-md hover:bg-brand-sky/10 transition-colors"
                  >
                    Edit
                  </button>
                  <button
                    onClick={() => setRemovingTenant(t)}
                    className="text-xs px-2.5 py-1 border border-danger text-danger rounded-md hover:bg-danger/10 transition-colors"
                  >
                    Delete
                  </button>
                </td>
              </tr>
            ))}
            {tenants?.length === 0 && (
              <tr>
                <td colSpan={4} className="p-6 text-center text-page-text-muted">
                  No tenants in this organization yet
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      {/* Number pool */}
      <div className="bg-card-bg rounded-lg border border-card-border mb-6">
        <div className="p-4 border-b border-card-border">
          <h3 className="font-semibold text-page-text">Phone Number Pool</h3>
          <p className="text-xs text-page-text-secondary mt-1">
            Assign a number to a tenant to make it available there. Tenant
            admins can then enable it for inbound and/or outbound use.
          </p>
        </div>
        <table className="w-full">
          <thead>
            <tr className="border-b border-card-border text-left text-sm text-page-text-secondary">
              <th className="p-4 font-medium">Number</th>
              <th className="p-4 font-medium">Assigned to</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-page-divider">
            {numbers?.map((n) => (
              <tr key={n.id} className="hover:bg-page-hover">
                <td className="p-4 text-sm font-mono text-page-text">{n.e164}</td>
                <td className="p-4">
                  <Dropdown
                    value={n.tenant_id ?? ""}
                    onChange={(v) =>
                      assignNumber.mutate({
                        numberId: n.id,
                        tenantId: v || null,
                      })
                    }
                    options={[
                      { value: "", label: "Unassigned" },
                      ...(tenants ?? []).map((t) => ({
                        value: t.id,
                        label: t.name,
                      })),
                    ]}
                  />
                </td>
              </tr>
            ))}
            {numbers?.length === 0 && (
              <tr>
                <td colSpan={2} className="p-6 text-center text-page-text-muted">
                  No numbers in this organization. A superadmin needs to assign
                  numbers to your organization first.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      {/* Org admins */}
      <div className="bg-card-bg rounded-lg border border-card-border">
        <div className="p-4 border-b border-card-border flex items-center justify-between">
          <h3 className="font-semibold text-page-text">Organization Admins</h3>
          <button
            onClick={() => {
              setFormError(null);
              setShowAddAdmin(true);
            }}
            className="flex items-center gap-2 px-3 py-1.5 bg-brand-sky text-white rounded-lg hover:bg-brand-sky/80 text-sm"
          >
            <UserPlus className="w-4 h-4" />
            Add Admin
          </button>
        </div>
        <table className="w-full">
          <thead>
            <tr className="border-b border-card-border text-left text-sm text-page-text-secondary">
              <th className="p-4 font-medium">Name</th>
              <th className="p-4 font-medium">Email</th>
              <th className="p-4 font-medium">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-page-divider">
            {admins?.map((a) => (
              <tr key={a.user_id} className="hover:bg-page-hover">
                <td className="p-4 text-sm font-medium text-page-text">
                  <span className="inline-flex items-center gap-1.5">
                    <Shield className="w-3.5 h-3.5 text-accent-lavender" />
                    {a.name}
                  </span>
                </td>
                <td className="p-4 text-sm text-page-text-secondary">
                  <EmailLink email={a.email} />
                </td>
                <td className="p-4">
                  <button
                    onClick={() => setRemovingAdmin(a)}
                    className="text-xs px-2.5 py-1 border border-danger text-danger rounded-md hover:bg-danger/10 transition-colors"
                  >
                    Remove
                  </button>
                </td>
              </tr>
            ))}
            {admins?.length === 0 && (
              <tr>
                <td colSpan={3} className="p-6 text-center text-page-text-muted">
                  No organization admins yet
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      <ConfirmDialog
        open={!!removingAdmin}
        title="Remove Organization Admin"
        message={
          <>
            Remove organization admin access from{" "}
            <span className="font-semibold text-page-text">
              {removingAdmin?.name}
            </span>
            ?
          </>
        }
        warning="They will lose the ability to manage this organization, its tenants, and its number pool."
        confirmLabel="Remove Admin"
        onConfirm={() => {
          if (removingAdmin) removeAdmin.mutate(removingAdmin.user_id);
          setRemovingAdmin(null);
        }}
        onCancel={() => setRemovingAdmin(null)}
      />

      {/* Add admin modal */}
      {showAddAdmin && (
        <div className="fixed inset-0 bg-black/30 flex items-center justify-center z-50">
          <div className="bg-card-bg rounded-xl shadow-lg w-full max-w-md p-6">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg font-semibold text-page-text">
                Add Organization Admin
              </h3>
              <button
                onClick={() => {
                  setShowAddAdmin(false);
                  setFormError(null);
                }}
                className="p-1 hover:bg-page-hover rounded"
              >
                <X className="w-5 h-5 text-page-text" />
              </button>
            </div>
            {formError && (
              <div className="mb-4 p-3 rounded-lg bg-danger/10 border border-danger/30 text-danger text-sm">
                {formError}
              </div>
            )}
            <form onSubmit={handleAddAdmin} className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-page-text mb-1">
                  Email
                </label>
                <input
                  name="email"
                  type="email"
                  required
                  className="w-full px-3 py-2 border border-card-border rounded-lg text-sm bg-page-bg-tertiary text-page-text"
                  placeholder="admin@example.com"
                />
                <p className="text-xs text-page-text-muted mt-1">
                  The user must have signed in at least once before they can be
                  promoted.
                </p>
              </div>
              <div className="flex justify-end gap-3 pt-2">
                <button
                  type="button"
                  onClick={() => {
                    setShowAddAdmin(false);
                    setFormError(null);
                  }}
                  className="px-4 py-2 text-sm text-page-text-secondary hover:bg-page-hover rounded-lg"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={addAdmin.isPending}
                  className="px-4 py-2 text-sm bg-brand-sky text-white rounded-lg hover:bg-brand-sky/80 disabled:opacity-50"
                >
                  Add
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Edit tenant modal */}
      {editingTenant && (
        <div className="fixed inset-0 bg-black/30 flex items-center justify-center z-50">
          <div className="bg-card-bg rounded-xl shadow-lg w-full max-w-md p-6">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg font-semibold text-page-text">
                Edit Tenant
              </h3>
              <button
                onClick={() => {
                  setEditingTenant(null);
                  setFormError(null);
                }}
                className="p-1 hover:bg-page-hover rounded"
              >
                <X className="w-5 h-5 text-page-text" />
              </button>
            </div>
            {formError && (
              <div className="mb-4 p-3 rounded-lg bg-danger/10 border border-danger/30 text-danger text-sm">
                {formError}
              </div>
            )}
            <form
              onSubmit={(e) => {
                e.preventDefault();
                if (!editingTenant) return;
                updateTenant.mutate({
                  tenantId: editingTenant.id,
                  name: editTenantName.trim(),
                  description: editTenantDescription.trim() || null,
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
                  value={editTenantName}
                  onChange={(e) => setEditTenantName(e.target.value)}
                  className="w-full px-3 py-2 border border-card-border rounded-lg text-sm bg-page-bg-tertiary text-page-text"
                />
                <p className="text-xs text-page-text-muted mt-1">
                  The slug will update automatically to match the new name.
                </p>
              </div>
              <div>
                <label className="block text-sm font-medium text-page-text mb-1">
                  Description
                </label>
                <input
                  value={editTenantDescription}
                  onChange={(e) => setEditTenantDescription(e.target.value)}
                  className="w-full px-3 py-2 border border-card-border rounded-lg text-sm bg-page-bg-tertiary text-page-text"
                  placeholder="Optional"
                />
              </div>
              <div className="flex justify-end gap-3 pt-2">
                <button
                  type="button"
                  onClick={() => {
                    setEditingTenant(null);
                    setFormError(null);
                  }}
                  className="px-4 py-2 text-sm text-page-text-secondary hover:bg-page-hover rounded-lg"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={updateTenant.isPending}
                  className="px-4 py-2 text-sm bg-brand-sky text-white rounded-lg hover:bg-brand-sky/80 disabled:opacity-50"
                >
                  {updateTenant.isPending ? "Saving..." : "Save"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      <ConfirmDialog
        open={!!removingTenant}
        title="Delete Tenant"
        message={
          <>
            Delete{" "}
            <span className="font-semibold text-page-text">
              {removingTenant?.name}
            </span>
            ?
          </>
        }
        warning="This permanently deletes all of the tenant's calls, transcripts, insights, templates, and SIP credentials. Phone numbers assigned to this tenant return to the organization pool. This action cannot be undone."
        confirmLabel="Delete Tenant"
        onConfirm={() => {
          if (removingTenant) deleteTenant.mutate(removingTenant.id);
        }}
        onCancel={() => setRemovingTenant(null)}
      />

      {/* Create tenant modal */}
      {showCreateTenant && (
        <div className="fixed inset-0 bg-black/30 flex items-center justify-center z-50">
          <div className="bg-card-bg rounded-xl shadow-lg w-full max-w-md p-6">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg font-semibold text-page-text">
                New Tenant
              </h3>
              <button
                onClick={() => {
                  setShowCreateTenant(false);
                  setFormError(null);
                }}
                className="p-1 hover:bg-page-hover rounded"
              >
                <X className="w-5 h-5 text-page-text" />
              </button>
            </div>
            {formError && (
              <div className="mb-4 p-3 rounded-lg bg-danger/10 border border-danger/30 text-danger text-sm">
                {formError}
              </div>
            )}
            <form onSubmit={handleCreateTenant} className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-page-text mb-1">
                  Name
                </label>
                <input
                  name="name"
                  required
                  className="w-full px-3 py-2 border border-card-border rounded-lg text-sm bg-page-bg-tertiary text-page-text"
                  placeholder="Sales Team"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-page-text mb-1">
                  Description
                </label>
                <input
                  name="description"
                  className="w-full px-3 py-2 border border-card-border rounded-lg text-sm bg-page-bg-tertiary text-page-text"
                  placeholder="Optional"
                />
              </div>
              <div className="flex justify-end gap-3 pt-2">
                <button
                  type="button"
                  onClick={() => {
                    setShowCreateTenant(false);
                    setFormError(null);
                  }}
                  className="px-4 py-2 text-sm text-page-text-secondary hover:bg-page-hover rounded-lg"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={createTenant.isPending}
                  className="px-4 py-2 text-sm bg-brand-sky text-white rounded-lg hover:bg-brand-sky/80 disabled:opacity-50"
                >
                  Create
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
