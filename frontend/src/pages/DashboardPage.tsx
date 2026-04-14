import { useQuery } from "@tanstack/react-query";
import { CallListItem, type CallListData } from "../components/CallListItem";
import { PageLoadingSpinner } from "../components/LoadingSpinner";
import { useAuth } from "../contexts/AuthContext";
import { useDocumentTitle } from "../hooks/useDocumentTitle";
import { useInsightStream } from "../hooks/useWebSocket";
import { apiFetch } from "../lib/api";

export function DashboardPage() {
  useDocumentTitle("Dashboard");
  const { tenant } = useAuth();
  const insights = useInsightStream();

  const { data, isLoading } = useQuery({
    queryKey: ["calls", tenant?.id],
    queryFn: () =>
      apiFetch<{ calls: CallListData[]; total: number }>(
        `/api/v1/tenants/${tenant!.id}/calls?per_page=50`
      ),
    enabled: !!tenant,
    refetchInterval: 10000,
  });

  if (isLoading) {
    return <PageLoadingSpinner />;
  }

  return (
    <div className="p-6">
      <h2 className="text-2xl font-bold text-page-text mb-6">Dashboard</h2>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Calls list */}
        <div className="lg:col-span-2">
          <div className="bg-card-bg rounded-lg border border-card-border">
            <div className="p-4 border-b border-card-border">
              <h3 className="font-semibold text-page-text">Recent Calls</h3>
            </div>
            {data?.calls.length === 0 ? (
              <div className="p-8 text-center text-page-text-muted">
                No calls yet. Call your Twilio number to get started.
              </div>
            ) : (
              data?.calls.map((call) => (
                <CallListItem key={call.id} call={call} />
              ))
            )}
          </div>
        </div>

        {/* Live insights feed */}
        <div>
          <div className="bg-card-bg rounded-lg border border-card-border">
            <div className="p-4 border-b border-card-border">
              <h3 className="font-semibold text-page-text">Live Insights</h3>
            </div>
            <div className="divide-y divide-page-divider max-h-96 overflow-auto">
              {insights.length === 0 ? (
                <div className="p-6 text-center text-page-text-muted text-sm">
                  Insights will appear here during active calls
                </div>
              ) : (
                insights.slice(0, 20).map((ins) => (
                  <div key={ins.insight_id} className="p-3">
                    <div className="flex items-center gap-2">
                      <span
                        className={`w-2 h-2 rounded-full ${
                          ins.severity === "critical"
                            ? "bg-danger"
                            : ins.severity === "warning"
                              ? "bg-warning"
                              : "bg-brand-sky"
                        }`}
                      />
                      <span className="text-sm font-medium text-page-text">
                        {ins.template_name}
                      </span>
                      <span className="text-xs text-page-text-muted ml-auto">
                        {Math.round(ins.confidence * 100)}%
                      </span>
                    </div>
                    <p className="text-xs text-page-text-secondary mt-1 line-clamp-2">
                      {ins.evidence}
                    </p>
                  </div>
                ))
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
