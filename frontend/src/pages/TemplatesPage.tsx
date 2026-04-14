import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Plus, X } from "lucide-react";
import { useState } from "react";
import { HelpTooltip } from "../components/HelpTooltip";
import { useAuth } from "../contexts/AuthContext";
import { useDocumentTitle } from "../hooks/useDocumentTitle";
import { apiFetch } from "../lib/api";

interface Template {
  id: string;
  tenant_id: string;
  name: string;
  description: string | null;
  prompt: string;
  category: string;
  severity: string;
  is_realtime: boolean;
  output_schema: unknown;
  active: boolean;
}

const categories = ["sales", "support", "compliance", "custom"];
const severities = ["info", "warning", "critical"];

export function TemplatesPage() {
  useDocumentTitle("Templates");
  const { tenant } = useAuth();
  const queryClient = useQueryClient();
  const [showForm, setShowForm] = useState(false);
  const [editing, setEditing] = useState<Template | null>(null);
  // Defaults used to pre-fill the form (separate from `editing` so we can
  // create a new template from an existing one without editing it in place).
  const [formDefaults, setFormDefaults] = useState<Template | null>(null);

  const { data: templates, isLoading } = useQuery({
    queryKey: ["templates", tenant?.id],
    queryFn: () =>
      apiFetch<Template[]>(`/api/v1/tenants/${tenant!.id}/templates`),
    enabled: !!tenant,
  });

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
    };

    if (editing) {
      updateMutation.mutate({ id: editing.id, ...data });
    } else {
      createMutation.mutate(data);
    }
  };

  return (
    <div className="p-6">
      <div className="flex items-start justify-between gap-6 mb-6">
        <div className="max-w-2xl">
          <h2 className="text-2xl font-bold text-page-text">Insight Templates</h2>
          <p className="text-sm text-page-text-secondary mt-2">
            Templates define what Callisto looks for in calls. Each one is a
            natural-language rule the LLM evaluates against the transcript —
            things like follow-up requests, questions about pricing, or
            mentions of a specific topic.
          </p>
        </div>
        <button
          onClick={() => {
            setEditing(null);
            setFormDefaults(null);
            setShowForm(true);
          }}
          className="flex items-center gap-2 px-4 py-2 bg-brand-sky text-white rounded-lg hover:bg-brand-sky/80 transition-colors text-sm shrink-0"
        >
          <Plus className="w-4 h-4" />
          New Template
        </button>
      </div>

      {/* Template list */}
      <div className="bg-card-bg rounded-lg border border-card-border">
        {isLoading ? (
          <div className="p-8 text-center text-page-text-muted">Loading...</div>
        ) : (
          <table className="w-full">
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
                  <td className="p-4">
                    <p className="text-sm font-medium text-page-text">
                      {t.name}
                    </p>
                    {t.description && (
                      <p className="text-xs text-page-text-secondary mt-0.5">
                        {t.description}
                      </p>
                    )}
                  </td>
                  <td className="p-4 text-sm text-page-text-secondary">{t.category}</td>
                  <td className="p-4">
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
                  <td className="p-4 text-sm text-page-text-secondary">
                    {t.is_realtime ? "Yes" : "No"}
                  </td>
                  <td className="p-4">
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
                        onClick={() => deleteMutation.mutate(t.id)}
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
        )}
      </div>

      {/* Create/Edit modal */}
      {showForm && (
        <div className="fixed inset-0 bg-black/30 flex items-center justify-center z-50">
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
                    detect. Be specific — e.g. "Detect if the caller asks
                    for a callback or requests that someone follow up with
                    them."
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
                  <select
                    name="category"
                    defaultValue={formDefaults?.category ?? "custom"}
                    className="w-full px-3 py-2 border border-card-border rounded-lg text-sm bg-page-bg-tertiary text-page-text"
                  >
                    {categories.map((c) => (
                      <option key={c} value={c}>
                        {c}
                      </option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="flex items-center gap-1.5 text-sm font-medium text-page-text mb-1">
                    Severity
                    <HelpTooltip>
                      How important a detection is. "Critical" insights
                      show up as red, "warning" as yellow, "info" as blue.
                    </HelpTooltip>
                  </label>
                  <select
                    name="severity"
                    defaultValue={formDefaults?.severity ?? "info"}
                    className="w-full px-3 py-2 border border-card-border rounded-lg text-sm bg-page-bg-tertiary text-page-text"
                  >
                    {severities.map((s) => (
                      <option key={s} value={s}>
                        {s}
                      </option>
                    ))}
                  </select>
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
    </div>
  );
}
