/**
 * Demo-mode helpers.
 *
 * When localStorage["callisto_demo_tenant"] is set, the app runs against
 * the public read-only /api/demo backend instead of /api/v1, no JWT, with
 * a synthetic auth context derived from the chosen tenant slug. The whole
 * existing UI then "just works" against fake data.
 */

const KEY = "callisto_demo_tenant";

export function getDemoTenantSlug(): string | null {
  try {
    return localStorage.getItem(KEY);
  } catch {
    return null;
  }
}

export function isDemoMode(): boolean {
  return getDemoTenantSlug() !== null;
}

export function enterDemo(slug: string) {
  try {
    localStorage.setItem(KEY, slug);
    // Wipe any real-user JWT so we don't accidentally call /api/v1 with
    // stale credentials in demo mode.
    localStorage.removeItem("callisto_token");
    localStorage.removeItem("callisto_google_token");
  } catch {
    /* localStorage unavailable — nothing we can do */
  }
}

export function exitDemo() {
  try {
    localStorage.removeItem(KEY);
  } catch {
    /* ignore */
  }
}
