/**
 * Format a date string in the user's local timezone with abbreviation and UTC offset.
 * e.g. "Apr 12, 2026 · 6:02 PM EST (UTC-5)"
 */
export function formatDateTime(iso: string): string {
  const date = new Date(iso);
  const datePart = date.toLocaleDateString(undefined, {
    month: "short",
    day: "numeric",
    year: "numeric",
  });
  const timePart = date.toLocaleTimeString(undefined, {
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
  return `${datePart} · ${timePart} ${tzAbbr} (${utc})`;
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

const DIAL_STATUS_LABELS: Record<string, string> = {
  "no-answer": "Not answered",
  busy: "Line was busy",
  failed: "Call failed",
  canceled: "Canceled",
  completed: "Picked up",
};

/** Humanize a Twilio DialCallStatus value for display. */
export function formatDialStatus(status: string): string {
  return DIAL_STATUS_LABELS[status] ?? capitalize(status.replace(/[-_]/g, " "));
}
