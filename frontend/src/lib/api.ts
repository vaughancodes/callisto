import { getDemoTenantSlug, isDemoMode } from "./demoMode";

const BASE = "";

function getToken(): string | null {
  return localStorage.getItem("callisto_token");
}

export function setToken(token: string) {
  localStorage.setItem("callisto_token", token);
}

export function clearToken() {
  localStorage.removeItem("callisto_token");
}

function rewriteForDemo(path: string): string {
  // The existing UI hits /api/v1/... and /auth/me. In demo mode we
  // transparently swap those for the matching /api/demo/... routes which
  // serve seeded read-only fixture data. Everything else (e.g. asset
  // paths) passes through untouched.
  if (path.startsWith("/api/v1/")) {
    return "/api/demo/" + path.slice("/api/v1/".length);
  }
  if (path === "/auth/me") {
    const slug = getDemoTenantSlug();
    return slug ? `/api/demo/me?slug=${encodeURIComponent(slug)}` : path;
  }
  return path;
}

export async function apiFetch<T = unknown>(
  path: string,
  options: RequestInit = {}
): Promise<T> {
  const demo = isDemoMode();

  // Short-circuit any mutation in demo mode with a friendly error. The
  // demo backend only registers GET routes; without this guard the
  // existing UI edit flows surface a raw 405 from the server.
  const method = (options.method || "GET").toUpperCase();
  if (demo && method !== "GET" && method !== "HEAD") {
    throw new Error(
      "Demo mode is read-only. Editing, re-analysis, and uploads are disabled in the sandbox."
    );
  }

  const finalPath = demo ? rewriteForDemo(path) : path;

  const headers: Record<string, string> = {
    ...(options.headers as Record<string, string>),
  };
  // Let the browser set Content-Type (with boundary) for FormData uploads.
  if (!(options.body instanceof FormData) && !headers["Content-Type"]) {
    headers["Content-Type"] = "application/json";
  }
  if (!demo) {
    const token = getToken();
    if (token) {
      headers["Authorization"] = `Bearer ${token}`;
    }
  }

  const resp = await fetch(`${BASE}${finalPath}`, { ...options, headers });

  if (resp.status === 401 && !demo) {
    clearToken();
    window.location.href = "/login";
    throw new Error("Unauthorized");
  }

  if (!resp.ok) {
    const body = await resp.text();
    let message = body || `Request failed (${resp.status})`;
    try {
      const parsed = JSON.parse(body);
      if (parsed?.error) message = parsed.error;
      else if (parsed?.message) message = parsed.message;
    } catch {
      // body wasn't JSON — fall back to raw text
    }
    throw new Error(message);
  }

  if (resp.status === 204) return undefined as T;
  return resp.json();
}
