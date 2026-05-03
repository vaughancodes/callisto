import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertCircle, Pencil, Plus, Tag, Trash2, X } from "lucide-react";
import { useEffect, useState } from "react";
import { ConfirmDialog } from "../components/ConfirmDialog";
import { Dropdown } from "../components/Dropdown";
import { HelpTooltip } from "../components/HelpTooltip";
import { PageLoadingSpinner } from "../components/LoadingSpinner";
import { useAuth } from "../contexts/AuthContext";
import { useDocumentTitle } from "../hooks/useDocumentTitle";
import { apiFetch } from "../lib/api";
import { ScrollLock } from "../hooks/useBodyScrollLock";

interface Template {
  id: string;
  tenant_id: string;
  name: string;
  description: string | null;
  prompt: string;
  category: string;
  severity: string;
  is_realtime: boolean;
  inbound_enabled: boolean;
  outbound_enabled: boolean;
  applies_to: "external" | "internal" | "both";
  output_schema: unknown;
  active: boolean;
}

interface Category {
  id: string;
  tenant_id: string;
  name: string;
}

const severities = ["info", "warning", "critical"];
const appliesToOptions = [
  { value: "both", label: "Both speakers" },
  { value: "external", label: "External only" },
  { value: "internal", label: "Internal only" },
];

export function TemplatesPage() {
  useDocumentTitle("Templates");
  const { tenant } = useAuth();
  const queryClient = useQueryClient();
  const [showForm, setShowForm] = useState(false);
  const [editing, setEditing] = useState<Template | null>(null);
  // Defaults used to pre-fill the form (separate from `editing` so we can
  // create a new template from an existing one without editing it in place).
  const [formDefaults, setFormDefaults] = useState<Template | null>(null);
  const [deleting, setDeleting] = useState<Template | null>(null);
  const [showCategories, setShowCategories] = useState(false);
  const [category, setCategory] = useState<string>("custom");
  const [severity, setSeverity] = useState<string>("info");
  const [appliesTo, setAppliesTo] = useState<string>("both");

  useEffect(() => {
    if (showForm) {
      setCategory(formDefaults?.category ?? "custom");
      setSeverity(formDefaults?.severity ?? "info");
      setAppliesTo(formDefaults?.applies_to ?? "both");
    }
  }, [showForm, formDefaults]);

  const { data: templates, isLoading } = useQuery({
    queryKey: ["templates", tenant?.id],
    queryFn: () =>
      apiFetch<Template[]>(`/api/v1/tenants/${tenant!.id}/templates`),
    enabled: !!tenant,
  });

  const { data: categoriesData } = useQuery({
    queryKey: ["template-categories", tenant?.id],
    queryFn: () =>
      apiFetch<Category[]>(
        `/api/v1/tenants/${tenant!.id}/template-categories`
      ),
    enabled: !!tenant,
  });
  const categoryOptions = (categoriesData ?? []).map((c) => ({
    value: c.name,
    label: c.name,
  }));

  const createMutation = useMutation({
    mutationFn: (data: Record<string, unknown>) =>
      apiFetch(`/api/v1/tenants/${tenant!.id}/templates`, {
        method: "POST",
        body: JSON.stringify(data),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["templates"] });
      setShowForm(false);
    },
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, ...data }: Record<string, unknown>) =>
      apiFetch(`/api/v1/templates/${id}`, {
        method: "PUT",
        body: JSON.stringify(data),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["templates"] });
      setEditing(null);
      setFormDefaults(null);
      setShowForm(false);
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) =>
      apiFetch(`/api/v1/templates/${id}`, { method: "DELETE" }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["templates"] }),
  });

  const handleSubmit = (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    const form = new FormData(e.currentTarget);
    const data: Record<string, unknown> = {
      name: form.get("name"),
      description: form.get("description") || null,
      prompt: form.get("prompt"),
      category: form.get("category"),
      severity: form.get("severity"),
      is_realtime: form.get("is_realtime") === "on",
      inbound_enabled: form.get("inbound_enabled") === "on",
      outbound_enabled: form.get("outbound_enabled") === "on",
      applies_to: form.get("applies_to"),
    };

    if (editing) {
      updateMutation.mutate({ id: editing.id, ...data });
    } else {
      createMutation.mutate(data);
    }
  };

  if (isLoading) {
    return <PageLoadingSpinner />;
  }

  return (
    <div className="p-4 sm:p-6">
      <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-4 sm:gap-6 mb-6">
        <div className="max-w-2xl min-w-0">
          <h2 className="text-2xl font-bold text-page-text">Insight Templates</h2>
          <p className="text-sm text-page-text-secondary mt-2">
            Templates define what Callisto looks for in calls. Each one is a
            natural-language rule the LLM evaluates against the transcript —
            things like follow-up requests, questions about pricing, or
            mentions of a specific topic.
          </p>
        </div>
        <div className="flex flex-wrap gap-2 sm:shrink-0">
          <button
            onClick={() => setShowCategories(true)}
            className="flex items-center gap-2 px-3 py-2 bg-card-bg border border-card-border rounded-lg hover:bg-page-hover text-sm text-page-text"
          >
            <Tag className="w-4 h-4" />
            Manage Categories
          </button>
          <button
            onClick={() => {
              setEditing(null);
              setFormDefaults(null);
              setShowForm(true);
            }}
            className="flex items-center gap-2 px-4 py-2 bg-brand-sky text-white rounded-lg hover:bg-brand-sky/80 transition-colors text-sm"
          >
            <Plus className="w-4 h-4" />
            New Template
          </button>
        </div>
      </div>

      {/* Template list */}
      <div className="bg-card-bg rounded-lg border border-card-border">
        <div className="overflow-x-auto">
          <table className="w-full min-w-[640px]">
            <thead>
              <tr className="border-b border-card-border text-left text-sm text-page-text-secondary">
                <th className="p-4 font-medium">Name</th>
                <th className="p-4 font-medium">Category</th>
                <th className="p-4 font-medium">Severity</th>
                <th className="p-4 font-medium">Real-time</th>
                <th className="p-4 font-medium">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-page-divider">
              {templates?.map((t) => (
                <tr key={t.id} className="hover:bg-page-hover">
                  <td className="p-4 align-middle">
                    <p className="text-sm font-medium text-page-text">
                      {t.name}
                    </p>
                    {t.description && (
                      <p className="text-xs text-page-text-secondary mt-0.5">
                        {t.description}
                      </p>
                    )}
                  </td>
                  <td className="p-4 text-sm text-page-text-secondary align-middle">{t.category}</td>
                  <td className="p-4 align-middle">
                    <span
                      className={`text-xs px-2 py-0.5 rounded-full ${
                        t.severity === "critical"
                          ? "bg-danger/15 text-danger"
                          : t.severity === "warning"
                            ? "bg-warning/15 text-warning"
                            : "bg-brand-sky/10 text-brand-sky"
                      }`}
                    >
                      {t.severity}
                    </span>
                  </td>
                  <td className="p-4 text-sm text-page-text-secondary align-middle">
                    {t.is_realtime ? "Yes" : "No"}
                  </td>
                  <td className="p-4 align-middle">
                    <div className="flex gap-2">
                      <button
                        onClick={() => {
                          setEditing(t);
                          setFormDefaults(t);
                          setShowForm(true);
                        }}
                        className="text-xs px-2.5 py-1 border border-brand-sky text-brand-sky rounded-md hover:bg-brand-sky/10 transition-colors"
                      >
                        Edit
                      </button>
                      <button
                        onClick={() => {
                          setEditing(null);
                          setFormDefaults({
                            ...t,
                            name: `${t.name} (copy)`,
                          });
                          setShowForm(true);
                        }}
                        className="text-xs px-2.5 py-1 border border-brand-sky text-brand-sky rounded-md hover:bg-brand-sky/10 transition-colors"
                      >
                        Duplicate
                      </button>
                      <button
                        onClick={() => setDeleting(t)}
                        className="text-xs px-2.5 py-1 border border-danger text-danger rounded-md hover:bg-danger/10 transition-colors"
                      >
                        Delete
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <ConfirmDialog
        open={!!deleting}
        title="Delete Template"
        message={
          <>
            Are you sure you want to delete{" "}
            <span className="font-semibold text-page-text">{deleting?.name}</span>?
          </>
        }
        warning="Existing insights detected with this template will remain, but it will no longer be evaluated on future calls."
        confirmLabel="Delete Template"
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
                {editing ? "Edit Template" : "New Template"}
              </h3>
              <button
                onClick={() => setShowForm(false)}
                className="p-1 hover:bg-page-hover rounded"
              >
                <X className="w-5 h-5 text-page-text" />
              </button>
            </div>

            <form onSubmit={handleSubmit} className="space-y-4">
              <div>
                <label className="flex items-center gap-1.5 text-sm font-medium text-page-text mb-1">
                  Name
                  <HelpTooltip>
                    A short, human-readable name for this template (e.g.
                    "Follow-up Request").
                  </HelpTooltip>
                </label>
                <input
                  name="name"
                  defaultValue={formDefaults?.name ?? ""}
                  required
                  className="w-full px-3 py-2 border border-card-border rounded-lg text-sm bg-page-bg-tertiary text-page-text"
                />
              </div>
              <div>
                <label className="flex items-center gap-1.5 text-sm font-medium text-page-text mb-1">
                  Description
                  <HelpTooltip>
                    Optional notes for your team about what this template is
                    for. Not sent to the LLM.
                  </HelpTooltip>
                </label>
                <input
                  name="description"
                  defaultValue={formDefaults?.description ?? ""}
                  className="w-full px-3 py-2 border border-card-border rounded-lg text-sm bg-page-bg-tertiary text-page-text"
                />
              </div>
              <div>
                <label className="flex items-center gap-1.5 text-sm font-medium text-page-text mb-1">
                  Detection Prompt
                  <HelpTooltip>
                    The instruction sent to the LLM describing what to
                    detect. Be specific — e.g. "Detect if the external
                    party asks for a callback or requests that someone
                    follow up with them." You can reference the two
                    speakers as [external] (the other party) and [internal]
                    (your team).
                  </HelpTooltip>
                </label>
                <textarea
                  name="prompt"
                  defaultValue={formDefaults?.prompt ?? ""}
                  required
                  rows={3}
                  className="w-full px-3 py-2 border border-card-border rounded-lg text-sm bg-page-bg-tertiary text-page-text"
                />
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="flex items-center gap-1.5 text-sm font-medium text-page-text mb-1">
                    Category
                    <HelpTooltip>
                      A grouping label used for organization and filtering
                      in analytics.
                    </HelpTooltip>
                  </label>
                  <Dropdown
                    name="category"
                    value={category}
                    onChange={setCategory}
                    options={
                      categoryOptions.some((o) => o.value === category)
                        ? categoryOptions
                        : [
                            ...categoryOptions,
                            { value: category, label: category },
                          ]
                    }
                  />
                  <p className="text-xs text-page-text-muted mt-1">
                    <button
                      type="button"
                      onClick={() => setShowCategories(true)}
                      className="text-brand-sky hover:underline"
                    >
                      Manage categories
                    </button>
                  </p>
                </div>
                <div>
                  <label className="flex items-center gap-1.5 text-sm font-medium text-page-text mb-1">
                    Severity
                    <HelpTooltip>
                      How important a detection is. "Critical" insights
                      show up as red, "warning" as yellow, "info" as blue.
                    </HelpTooltip>
                  </label>
                  <Dropdown
                    name="severity"
                    value={severity}
                    onChange={setSeverity}
                    options={severities.map((s) => ({ value: s, label: s }))}
                  />
                </div>
              </div>
              <div>
                <label className="flex items-center gap-2">
                  <input
                    type="checkbox"
                    name="is_realtime"
                    defaultChecked={formDefaults?.is_realtime ?? true}
                  />
                  <span className="flex items-center gap-1.5 text-sm text-page-text">
                    Evaluate in real-time
                    <HelpTooltip>
                      <>
                        Enabled: fires during the live call.
                        <br />
                        Disabled: evaluated during the post-call analysis.
                      </>
                    </HelpTooltip>
                  </span>
                </label>
              </div>
              <div>
                <label className="flex items-center gap-1.5 text-sm font-medium text-page-text mb-1">
                  Applies to speaker
                  <HelpTooltip>
                    Which side of the conversation this template evaluates
                    against. "External only" fires on the other party's
                    utterances (e.g. a pricing question from a prospect),
                    "Internal only" fires on your team's utterances (e.g. a
                    compliance disclosure), and "Both speakers" evaluates
                    the whole conversation.
                  </HelpTooltip>
                </label>
                <Dropdown
                  name="applies_to"
                  value={appliesTo}
                  onChange={setAppliesTo}
                  options={appliesToOptions}
                />
              </div>
              <div>
                <label className="flex items-center gap-1.5 text-sm font-medium text-page-text mb-2">
                  Evaluate on
                  <HelpTooltip>
                    Which call directions this template applies to. At least
                    one should be enabled, otherwise the template never fires.
                  </HelpTooltip>
                </label>
                <div className="flex items-center gap-6">
                  <label className="flex items-center gap-2">
                    <input
                      type="checkbox"
                      name="inbound_enabled"
                      defaultChecked={formDefaults?.inbound_enabled ?? true}
                    />
                    <span className="text-sm text-page-text">Inbound calls</span>
                  </label>
                  <label className="flex items-center gap-2">
                    <input
                      type="checkbox"
                      name="outbound_enabled"
                      defaultChecked={formDefaults?.outbound_enabled ?? true}
                    />
                    <span className="text-sm text-page-text">Outbound calls</span>
                  </label>
                </div>
              </div>
              <div className="flex justify-end gap-3 pt-2">
                <button
                  type="button"
                  onClick={() => setShowForm(false)}
                  className="px-4 py-2 text-sm text-page-text-secondary hover:bg-page-hover rounded-lg"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-4 py-2 text-sm bg-brand-sky text-white rounded-lg hover:bg-brand-sky/80"
                >
                  {editing ? "Update" : "Create"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {showCategories && tenant && (
        <CategoriesModal
          tenantId={tenant.id}
          onClose={() => setShowCategories(false)}
        />
      )}
    </div>
  );
}

function CategoriesModal({
  tenantId,
  onClose,
}: {
  tenantId: string;
  onClose: () => void;
}) {
  const queryClient = useQueryClient();
  const [newName, setNewName] = useState("");
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editName, setEditName] = useState("");
  const [error, setError] = useState<string | null>(null);

  const extractError = (err: Error): string => {
    const match = err.message.match(/API error \d+: (.*)/);
    if (match) {
      try {
        const parsed = JSON.parse(match[1]);
        if (parsed?.error) return parsed.error;
      } catch {
        /* fall through */
      }
    }
    return err.message;
  };

  const { data: categories, isLoading } = useQuery({
    queryKey: ["template-categories", tenantId],
    queryFn: () =>
      apiFetch<Category[]>(
        `/api/v1/tenants/${tenantId}/template-categories`
      ),
  });

  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: ["template-categories"] });
    queryClient.invalidateQueries({ queryKey: ["templates"] });
  };

  const createMutation = useMutation({
    mutationFn: (name: string) =>
      apiFetch(`/api/v1/tenants/${tenantId}/template-categories`, {
        method: "POST",
        body: JSON.stringify({ name }),
      }),
    onSuccess: () => {
      setNewName("");
      setError(null);
      invalidate();
    },
    onError: (err: Error) => setError(extractError(err)),
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, name }: { id: string; name: string }) =>
      apiFetch(`/api/v1/template-categories/${id}`, {
        method: "PUT",
        body: JSON.stringify({ name }),
      }),
    onSuccess: () => {
      setEditingId(null);
      setEditName("");
      setError(null);
      invalidate();
    },
    onError: (err: Error) => setError(extractError(err)),
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) =>
      apiFetch(`/api/v1/template-categories/${id}`, { method: "DELETE" }),
    onSuccess: () => {
      setError(null);
      invalidate();
    },
    onError: (err: Error) => setError(extractError(err)),
  });

  return (
    <div className="fixed inset-0 bg-black/30 flex items-center justify-center z-50">
      <ScrollLock />
      <div className="bg-card-bg rounded-xl shadow-lg w-full max-w-md p-6">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-semibold text-page-text">
            Manage Categories
          </h3>
          <button
            onClick={onClose}
            className="p-1 hover:bg-page-hover rounded"
          >
            <X className="w-5 h-5 text-page-text" />
          </button>
        </div>

        {error && (
          <div className="mb-3 flex items-start gap-2 p-3 rounded-lg bg-danger/10 border border-danger/30 text-danger">
            <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" />
            <p className="text-sm leading-snug">{error}</p>
          </div>
        )}

        <form
          onSubmit={(e) => {
            e.preventDefault();
            const name = newName.trim();
            if (!name) return;
            createMutation.mutate(name);
          }}
          className="flex gap-2 mb-4"
        >
          <input
            value={newName}
            onChange={(e) => setNewName(e.target.value)}
            placeholder="New category name"
            className="flex-1 px-3 py-2 border border-card-border rounded-lg text-sm bg-page-bg-tertiary text-page-text"
          />
          <button
            type="submit"
            disabled={!newName.trim() || createMutation.isPending}
            className="px-3 py-2 text-sm bg-brand-sky text-white rounded-lg hover:bg-brand-sky/80 disabled:opacity-50"
          >
            Add
          </button>
        </form>

        {isLoading ? (
          <p className="text-sm text-page-text-muted py-3 text-center">
            Loading...
          </p>
        ) : (categories ?? []).length === 0 ? (
          <p className="text-sm text-page-text-muted py-3 text-center">
            No categories yet. Add one above.
          </p>
        ) : (
          <ul className="divide-y divide-page-divider border border-card-border rounded-lg overflow-hidden">
            {categories!.map((c) => (
              <li
                key={c.id}
                className="flex items-center gap-2 px-3 py-2 hover:bg-page-hover"
              >
                {editingId === c.id ? (
                  <>
                    <input
                      value={editName}
                      onChange={(e) => setEditName(e.target.value)}
                      autoFocus
                      className="flex-1 px-2 py-1 border border-card-border rounded text-sm bg-page-bg-tertiary text-page-text"
                    />
                    <button
                      onClick={() => {
                        const name = editName.trim();
                        if (!name) return;
                        updateMutation.mutate({ id: c.id, name });
                      }}
                      className="text-xs px-2 py-1 bg-brand-sky text-white rounded hover:bg-brand-sky/80"
                    >
                      Save
                    </button>
                    <button
                      onClick={() => {
                        setEditingId(null);
                        setEditName("");
                        setError(null);
                      }}
                      className="text-xs px-2 py-1 text-page-text-secondary hover:bg-page-hover rounded"
                    >
                      Cancel
                    </button>
                  </>
                ) : (
                  <>
                    <span className="flex-1 text-sm text-page-text">
                      {c.name}
                    </span>
                    <button
                      onClick={() => {
                        setEditingId(c.id);
                        setEditName(c.name);
                        setError(null);
                      }}
                      title="Rename"
                      className="p-1 text-brand-sky hover:bg-brand-sky/10 rounded"
                    >
                      <Pencil className="w-4 h-4" />
                    </button>
                    <button
                      onClick={() => deleteMutation.mutate(c.id)}
                      title="Delete"
                      className="p-1 text-danger hover:bg-danger/10 rounded"
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </>
                )}
              </li>
            ))}
          </ul>
        )}

        <p className="text-xs text-page-text-muted mt-3">
          Renaming a category updates every template that uses it. A category
          can't be deleted while active templates still reference it.
        </p>
      </div>
    </div>
  );
}
