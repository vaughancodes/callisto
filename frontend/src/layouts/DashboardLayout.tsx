import {
  BarChart3,
  ChevronsUpDown,
  Cog,
  FileText,
  LayoutDashboard,
  LogOut,
  Moon,
  Shield,
  Sun,
  Users,
} from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { NavLink, Outlet } from "react-router-dom";
import { useAuth } from "../contexts/AuthContext";
import { useTheme } from "../contexts/ThemeContext";

export function DashboardLayout() {
  const {
    user,
    tenant,
    isTenantAdmin,
    memberships,
    logout,
    switchTenant,
  } = useAuth();
  const { theme, toggle: toggleTheme } = useTheme();

  const [showTenantPicker, setShowTenantPicker] = useState(false);
  const pickerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const onClick = (e: MouseEvent) => {
      if (pickerRef.current && !pickerRef.current.contains(e.target as Node)) {
        setShowTenantPicker(false);
      }
    };
    if (showTenantPicker) {
      document.addEventListener("mousedown", onClick);
      return () => document.removeEventListener("mousedown", onClick);
    }
  }, [showTenantPicker]);

  const navItems = [
    { to: "/", icon: LayoutDashboard, label: "Dashboard" },
    { to: "/contacts", icon: Users, label: "Contacts" },
    { to: "/templates", icon: FileText, label: "Templates" },
    { to: "/analytics", icon: BarChart3, label: "Analytics" },
  ];

  const canSwitchTenant = memberships.length > 1;

  const handleSwitch = async (tenantId: string) => {
    setShowTenantPicker(false);
    if (tenantId === tenant?.id) return;
    await switchTenant(tenantId);
    // Reload the page so all queries re-fetch for the new tenant
    window.location.href = "/";
  };

  return (
    <div className="flex h-screen bg-page-bg">
      {/* Sidebar — always dark, uses dark palette colors directly */}
      <aside className="w-64 bg-surface-dark dark:bg-surface-elevated flex flex-col">
        <div className="px-3 py-4 border-b border-[#252a36]">
          <div className="flex items-center gap-3 min-w-0">
            <img
              src="/callisto-icon-animated.svg"
              alt=""
              className="w-10 h-10 shrink-0"
            />
            <img
              src="/callisto-wordmark-dark.svg"
              alt="Callisto"
              className="h-6 min-w-0 max-w-full object-contain"
            />
          </div>

          {/* Tenant switcher */}
          <div className="mt-3 relative" ref={pickerRef}>
            {canSwitchTenant ? (
              <button
                onClick={() => setShowTenantPicker((v) => !v)}
                className="w-full flex items-center justify-between gap-2 px-2 py-1.5 text-xs rounded-lg hover:bg-white/5 transition-colors"
              >
                <span className="text-[#94a3b8] truncate">
                  {tenant?.name ?? "No tenant"}
                </span>
                <ChevronsUpDown className="w-3 h-3 text-[#64748b] shrink-0" />
              </button>
            ) : (
              <p className="px-2 text-xs text-[#64748b]">
                {tenant?.name ?? "No tenant assigned"}
              </p>
            )}

            {showTenantPicker && canSwitchTenant && (
              <div className="absolute left-0 right-0 mt-1 bg-[#1a1e28] border border-[#252a36] rounded-lg shadow-lg overflow-hidden z-10">
                {memberships.map((m) => (
                  <button
                    key={m.tenant_id}
                    onClick={() => handleSwitch(m.tenant_id)}
                    className={`w-full text-left px-3 py-2 text-xs transition-colors ${
                      m.tenant_id === tenant?.id
                        ? "bg-brand-sky/15 text-accent-light"
                        : "text-[#94a3b8] hover:bg-white/5 hover:text-[#e2e8f0]"
                    }`}
                  >
                    <div className="flex items-center justify-between gap-2">
                      <span className="truncate">{m.tenant_name}</span>
                      {m.is_admin && (
                        <Shield className="w-3 h-3 text-accent-lavender shrink-0" />
                      )}
                    </div>
                  </button>
                ))}
              </div>
            )}
          </div>
        </div>

        <nav className="flex-1 p-3 space-y-1">
          {tenant &&
            navItems.map(({ to, icon: Icon, label }) => (
              <NavLink
                key={to}
                to={to}
                end={to === "/"}
                className={({ isActive }) =>
                  `flex items-center gap-3 px-3 py-2 rounded-lg text-sm transition-colors ${
                    isActive
                      ? "bg-brand-sky/15 text-accent-light"
                      : "text-[#94a3b8] hover:bg-white/5 hover:text-[#e2e8f0]"
                  }`
                }
              >
                <Icon className="w-4 h-4" />
                {label}
              </NavLink>
            ))}

          {tenant && isTenantAdmin && (
            <NavLink
              to="/tenant-settings"
              className={({ isActive }) =>
                `flex items-center gap-3 px-3 py-2 rounded-lg text-sm transition-colors ${
                  isActive
                    ? "bg-brand-sky/15 text-accent-light"
                    : "text-[#94a3b8] hover:bg-white/5 hover:text-[#e2e8f0]"
                }`
              }
            >
              <Cog className="w-4 h-4" />
              Tenant Settings
            </NavLink>
          )}

          {!tenant && !user?.is_superadmin && (
            <p className="px-3 py-4 text-sm text-[#64748b]">
              Waiting for admin to assign you to a tenant.
            </p>
          )}

          {user?.is_superadmin && (
            <>
              <div className="border-t border-[#252a36] my-3" />
              <NavLink
                to="/admin"
                className={({ isActive }) =>
                  `flex items-center gap-3 px-3 py-2 rounded-lg text-sm transition-colors ${
                    isActive
                      ? "bg-accent-lavender/15 text-accent-lavender"
                      : "text-accent-lavender/60 hover:bg-white/5 hover:text-accent-lavender"
                  }`
                }
              >
                <Shield className="w-4 h-4" />
                Administration
              </NavLink>
            </>
          )}
        </nav>

        <div className="p-3 border-t border-[#252a36]">
          <div className="flex items-center justify-between">
            <div className="text-sm truncate">
              <p className="font-medium text-[#e2e8f0]">{user?.name}</p>
              <p className="text-xs text-[#64748b]">{user?.email}</p>
            </div>
            <div className="flex gap-1">
              <button
                onClick={toggleTheme}
                className="p-2 text-[#64748b] hover:text-[#e2e8f0] rounded transition-colors"
                title={
                  theme === "dark"
                    ? "Switch to light mode"
                    : "Switch to dark mode"
                }
              >
                {theme === "dark" ? (
                  <Sun className="w-4 h-4" />
                ) : (
                  <Moon className="w-4 h-4" />
                )}
              </button>
              <button
                onClick={logout}
                className="p-2 text-[#64748b] hover:text-[#e2e8f0] rounded transition-colors"
              >
                <LogOut className="w-4 h-4" />
              </button>
            </div>
          </div>
        </div>
      </aside>

      <main className="flex-1 overflow-auto">
        <Outlet />
      </main>
    </div>
  );
}
