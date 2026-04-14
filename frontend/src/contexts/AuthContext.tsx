import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from "react";
import { apiFetch, clearToken, setToken } from "../lib/api";

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
  settings: Record<string, unknown>;
}

export interface Membership {
  tenant_id: string;
  tenant_name: string;
  tenant_slug: string;
  is_admin: boolean;
}

interface AuthMeResponse {
  user: UserInfo;
  tenant: TenantInfo | null;
  is_tenant_admin: boolean;
  memberships: Membership[];
}

interface AuthState {
  user: UserInfo | null;
  tenant: TenantInfo | null;
  isTenantAdmin: boolean;
  memberships: Membership[];
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
  const [isLoading, setIsLoading] = useState(true);

  const refresh = useCallback(async () => {
    const token = localStorage.getItem("callisto_token");
    if (!token) {
      setIsLoading(false);
      return;
    }
    try {
      const data = await apiFetch<AuthMeResponse>("/auth/me");
      setUser(data.user);
      setTenant(data.tenant);
      setIsTenantAdmin(data.is_tenant_admin);
      setMemberships(data.memberships);
    } catch {
      clearToken();
    } finally {
      setIsLoading(false);
    }
  }, []);

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
    window.location.href = "/login";
  };

  const switchTenant = async (tenantId: string) => {
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
