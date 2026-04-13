import {
  createContext,
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
  settings: Record<string, unknown>;
}

interface AuthState {
  user: UserInfo | null;
  tenant: TenantInfo | null;
  isLoading: boolean;
  login: () => void;
  logout: () => void;
}

const AuthContext = createContext<AuthState>({
  user: null,
  tenant: null,
  isLoading: true,
  login: () => {},
  logout: () => {},
});

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<UserInfo | null>(null);
  const [tenant, setTenant] = useState<TenantInfo | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    const token = localStorage.getItem("callisto_token");
    if (!token) {
      setIsLoading(false);
      return;
    }

    apiFetch<{ user: UserInfo; tenant: TenantInfo | null }>("/auth/me")
      .then((data) => {
        setUser(data.user);
        setTenant(data.tenant);
      })
      .catch(() => {
        clearToken();
      })
      .finally(() => setIsLoading(false));
  }, []);

  const login = () => {
    window.location.href = "/auth/google/login";
  };

  const logout = () => {
    clearToken();
    setUser(null);
    setTenant(null);
    window.location.href = "/login";
  };

  return (
    <AuthContext.Provider value={{ user, tenant, isLoading, login, logout }}>
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
