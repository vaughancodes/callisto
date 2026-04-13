/**
 * Format a date string in the user's local timezone with abbreviation and UTC offset.
 * e.g. "Apr 12, 2026, 6:02 PM EST (UTC-5)"
 */
export function formatDateTime(iso: string): string {
  const date = new Date(iso);
  const formatted = date.toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    year: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
  const tzAbbr = date.toLocaleString(undefined, { timeZoneName: "short" })
    .split(" ")
    .pop() ?? "";
  const offset = -date.getTimezoneOffset();
  const sign = offset >= 0 ? "+" : "-";
  const hours = Math.floor(Math.abs(offset) / 60);
  const minutes = Math.abs(offset) % 60;
  const utc = minutes ? `UTC${sign}${hours}:${minutes.toString().padStart(2, "0")}` : `UTC${sign}${hours}`;
  return `${formatted} ${tzAbbr} (${utc})`;
}

const STATUS_LABELS: Record<string, string> = {
  active: "Active",
  processing: "Processing",
  completed: "Completed",
  failed: "Failed",
};

export function formatStatus(status: string): string {
  return STATUS_LABELS[status] ?? status.charAt(0).toUpperCase() + status.slice(1);
}

const SOURCE_LABELS: Record<string, string> = {
  realtime: "Real-time",
  post_call: "Post-call",
};

export function formatInsightSource(source: string): string {
  return SOURCE_LABELS[source] ?? source.charAt(0).toUpperCase() + source.slice(1);
}

export function capitalize(s: string): string {
  return s.charAt(0).toUpperCase() + s.slice(1);
}
