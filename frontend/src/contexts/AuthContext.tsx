import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from "react";
import { apiFetch, clearToken, setToken } from "../lib/api";
import { enterDemo, exitDemo, isDemoMode } from "../lib/demoMode";

interface UserInfo {
  id: string;
  email: string;
  name: string;
  is_superadmin: boolean;
}

interface TenantInfo {
  id: string;
  name: string;
  slug: string;
  description: string | null;
  organization_id: string;
  settings: Record<string, unknown>;
}

export interface Membership {
  tenant_id: string;
  tenant_name: string;
  tenant_slug: string;
  organization_id: string;
  organization_name: string | null;
  is_admin: boolean;
}

export interface OrganizationMembership {
  organization_id: string;
  organization_name: string;
  organization_slug: string;
  is_admin: boolean;
}

interface AuthMeResponse {
  user: UserInfo;
  tenant: TenantInfo | null;
  is_tenant_admin: boolean;
  memberships: Membership[];
  organization_memberships: OrganizationMembership[];
}

interface AuthState {
  user: UserInfo | null;
  tenant: TenantInfo | null;
  isTenantAdmin: boolean;
  memberships: Membership[];
  organizationMemberships: OrganizationMembership[];
  isOrgAdmin: (organizationId: string) => boolean;
  isLoading: boolean;
  login: () => void;
  logout: () => void;
  switchTenant: (tenantId: string) => Promise<void>;
  refresh: () => Promise<void>;
}

const AuthContext = createContext<AuthState>({
  user: null,
  tenant: null,
  isTenantAdmin: false,
  memberships: [],
  organizationMemberships: [],
  isOrgAdmin: () => false,
  isLoading: true,
  login: () => {},
  logout: () => {},
  switchTenant: async () => {},
  refresh: async () => {},
});

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<UserInfo | null>(null);
  const [tenant, setTenant] = useState<TenantInfo | null>(null);
  const [isTenantAdmin, setIsTenantAdmin] = useState(false);
  const [memberships, setMemberships] = useState<Membership[]>([]);
  const [organizationMemberships, setOrganizationMemberships] = useState<
    OrganizationMembership[]
  >([]);
  const [isLoading, setIsLoading] = useState(true);

  const refresh = useCallback(async () => {
    const demo = isDemoMode();
    const token = localStorage.getItem("callisto_token");
    if (!demo && !token) {
      setIsLoading(false);
      return;
    }
    try {
      // In demo mode apiFetch rewrites /auth/me to the demo equivalent
      // and returns a synthetic user + tenant from the fixture data.
      const data = await apiFetch<AuthMeResponse>("/auth/me");
      setUser(data.user);
      setTenant(data.tenant);
      setIsTenantAdmin(data.is_tenant_admin);
      setMemberships(data.memberships);
      setOrganizationMemberships(data.organization_memberships ?? []);
    } catch {
      if (demo) {
        // Demo backend rejected — bail out of demo so the visitor isn't
        // stuck on a blank page.
        exitDemo();
      } else {
        clearToken();
      }
    } finally {
      setIsLoading(false);
    }
  }, []);

  const isOrgAdmin = useCallback(
    (organizationId: string) => {
      if (user?.is_superadmin) return true;
      return organizationMemberships.some(
        (m) => m.organization_id === organizationId && m.is_admin
      );
    },
    [user, organizationMemberships]
  );

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const login = () => {
    window.location.href = "/auth/google/login";
  };

  const logout = () => {
    clearToken();
    setUser(null);
    setTenant(null);
    setIsTenantAdmin(false);
    setMemberships([]);
    setOrganizationMemberships([]);
    window.location.href = "/login";
  };

  const switchTenant = async (tenantId: string) => {
    if (isDemoMode()) {
      // No backend swap in demo mode: rewrite the localStorage demo
      // slug to the target tenant and hard-reload so AuthProvider
      // re-mounts and fetches /api/demo/me with the new slug.
      const target = memberships.find((m) => m.tenant_id === tenantId);
      if (!target) return;
      enterDemo(target.tenant_slug);
      window.location.href = "/";
      return;
    }
    const data = await apiFetch<{ token: string }>("/auth/switch-tenant", {
      method: "POST",
      body: JSON.stringify({ tenant_id: tenantId }),
    });
    setToken(data.token);
    // Refresh the auth state with the new tenant
    await refresh();
  };

  return (
    <AuthContext.Provider
      value={{
        user,
        tenant,
        isTenantAdmin,
        memberships,
        organizationMemberships,
        isOrgAdmin,
        isLoading,
        login,
        logout,
        switchTenant,
        refresh,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  return useContext(AuthContext);
}

export function handleAuthCallback(): string | null {
  const params = new URLSearchParams(window.location.search);
  const token = params.get("token");
  const googleToken = params.get("google_token");
  if (token) {
    setToken(token);
    if (googleToken) {
      localStorage.setItem("callisto_google_token", googleToken);
    }
    return token;
  }
  return null;
}

export function getGoogleToken(): string | null {
  return localStorage.getItem("callisto_google_token");
}
