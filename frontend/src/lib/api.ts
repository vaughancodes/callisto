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

export async function apiFetch<T = unknown>(
  path: string,
  options: RequestInit = {}
): Promise<T> {
  const token = getToken();
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options.headers as Record<string, string>),
  };
  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  const resp = await fetch(`${BASE}${path}`, { ...options, headers });

  if (resp.status === 401) {
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
