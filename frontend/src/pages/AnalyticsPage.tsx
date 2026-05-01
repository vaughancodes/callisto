import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { useState } from "react";
import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { Dropdown } from "../components/Dropdown";
import { PageLoadingSpinner } from "../components/LoadingSpinner";
import { useAuth } from "../contexts/AuthContext";
import { useDocumentTitle } from "../hooks/useDocumentTitle";
import { apiFetch } from "../lib/api";

interface TrendPoint {
  date: string;
  template_name: string;
  template_id: string;
  count: number;
}

const COLORS = [
  "#3b82f6",
  "#ef4444",
  "#f59e0b",
  "#10b981",
  "#8b5cf6",
  "#ec4899",
  "#06b6d4",
];

export function AnalyticsPage() {
  useDocumentTitle("Analytics");
  const { tenant } = useAuth();
  const [days, setDays] = useState(30);
  // Name of the legend label currently being hovered, or null. Highlights
  // the matching line and dims the rest so individual templates are easier
  // to follow when several overlap.
  const [hoveredTemplate, setHoveredTemplate] = useState<string | null>(null);

  const { data: trends, isLoading } = useQuery({
    queryKey: ["analytics", tenant?.id, days],
    queryFn: () =>
      apiFetch<TrendPoint[]>(
        `/api/v1/tenants/${tenant!.id}/analytics/insights?days=${days}`
      ),
    enabled: !!tenant,
    placeholderData: keepPreviousData,
  });

  // Transform for recharts: pivot to {date, template1: count, template2: count, ...}
  const templateNames = [...new Set(trends?.map((t) => t.template_name) ?? [])];
  const chartData: Record<string, string | number>[] = [];

  if (trends) {
    const byDate = new Map<string, Record<string, number>>();
    for (const point of trends) {
      if (!byDate.has(point.date)) byDate.set(point.date, {});
      byDate.get(point.date)![point.template_name] = point.count;
    }
    for (const [date, counts] of byDate) {
      chartData.push({ date, ...counts });
    }
    chartData.sort((a, b) => (a.date as string).localeCompare(b.date as string));
  }

  if (isLoading) {
    return <PageLoadingSpinner />;
  }

  return (
    <div className="p-6">
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-2xl font-bold text-page-text">Analytics</h2>
        <Dropdown
          value={String(days)}
          onChange={(v) => setDays(Number(v))}
          options={[
            { value: "7", label: "Last 7 days" },
            { value: "14", label: "Last 14 days" },
            { value: "30", label: "Last 30 days" },
            { value: "90", label: "Last 90 days" },
          ]}
          className="w-44"
        />
      </div>

      <div className="bg-card-bg rounded-lg border border-card-border p-6">
        <h3 className="font-semibold text-page-text mb-4">
          Insight Trends Over Time
        </h3>
        {chartData.length === 0 ? (
          <div className="h-64 flex items-center justify-center text-page-text-muted">
            No insight data for the selected period
          </div>
        ) : (
          <ResponsiveContainer width="100%" height={400}>
            <LineChart data={chartData}>
              <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
              {/*
                Force evenly-spaced ticks. Recharts' default tick picker
                drops some labels but keeps others, which produces visible
                1-day vs 2-day gaps on a continuous date axis. We pick an
                interval that aims for ~10 labels regardless of range.
              */}
              <XAxis
                dataKey="date"
                tick={{ fontSize: 13 }}
                interval={Math.max(0, Math.ceil(chartData.length / 10) - 1)}
                minTickGap={0}
              />
              <YAxis allowDecimals={false} tick={{ fontSize: 13 }} />
              <Tooltip />
              <Legend
                verticalAlign="bottom"
                wrapperStyle={{ paddingTop: 16 }}
                content={(props: {
                  payload?: Array<{
                    value?: string | number;
                    color?: string;
                    dataKey?: string | number;
                  }>;
                }) => (
                  <div className="flex flex-wrap justify-center gap-x-8 gap-y-2 mt-2">
                    {(props.payload ?? []).map((entry) => {
                      const name =
                        entry.value != null ? String(entry.value) : "";
                      return (
                        <div
                          key={String(entry.dataKey ?? name)}
                          onMouseEnter={() => setHoveredTemplate(name)}
                          onMouseLeave={() => setHoveredTemplate(null)}
                          className="flex items-center gap-2 cursor-default select-none text-sm text-page-text-secondary"
                        >
                          <span
                            className="inline-block w-3.5 h-3.5 rounded-sm"
                            style={{ backgroundColor: entry.color }}
                          />
                          <span>{name}</span>
                        </div>
                      );
                    })}
                  </div>
                )}
              />
              {templateNames.map((name, i) => {
                const dimmed =
                  hoveredTemplate !== null && hoveredTemplate !== name;
                const highlighted = hoveredTemplate === name;
                return (
                  <Line
                    key={name}
                    type="monotone"
                    dataKey={name}
                    stroke={COLORS[i % COLORS.length]}
                    strokeWidth={highlighted ? 3 : 2}
                    strokeOpacity={dimmed ? 0.15 : 1}
                    dot={{ r: dimmed ? 2 : 3, opacity: dimmed ? 0.2 : 1 }}
                    activeDot={{ r: highlighted ? 6 : 4 }}
                    isAnimationActive={false}
                  />
                );
              })}
            </LineChart>
          </ResponsiveContainer>
        )}
      </div>
    </div>
  );
}
