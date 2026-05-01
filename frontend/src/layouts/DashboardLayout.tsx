import {
  BarChart3,
  Building2,
  ChevronsUpDown,
  Cog,
  FileText,
  Info,
  LayoutDashboard,
  LogOut,
  Moon,
  Shield,
  Sun,
  Users,
} from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { NavLink, Outlet } from "react-router-dom";
import { Tooltip } from "../components/Tooltip";
import { useAuth } from "../contexts/AuthContext";
import { useTheme } from "../contexts/ThemeContext";
import { exitDemo, isDemoMode } from "../lib/demoMode";

export function DashboardLayout() {
  const {
    user,
    tenant,
    isTenantAdmin,
    memberships,
    isOrgAdmin,
    logout,
    switchTenant,
  } = useAuth();
  const showOrgSettings = !!tenant && isOrgAdmin(tenant.organization_id);
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
    try {
      await switchTenant(tenantId);
      // Reload the page so all queries re-fetch for the new tenant
      window.location.href = "/";
    } catch (err) {
      console.error("Failed to switch tenant:", err);
      alert(
        `Failed to switch tenant: ${
          err instanceof Error ? err.message : String(err)
        }`
      );
    }
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
                className="w-full flex items-center justify-between gap-2 px-2 py-1.5 text-sm rounded-lg hover:bg-white/5 transition-colors"
              >
                <span className="text-[#94a3b8] truncate">
                  {tenant?.name ?? "No tenant"}
                </span>
                <ChevronsUpDown className="w-3.5 h-3.5 text-[#64748b] shrink-0" />
              </button>
            ) : (
              <p className="px-2 text-sm text-[#64748b]">
                {tenant?.name ?? "No tenant assigned"}
              </p>
            )}

            {showTenantPicker && canSwitchTenant && (
              <div className="absolute left-0 right-0 mt-1 bg-[#1a1e28] border border-[#252a36] rounded-lg shadow-lg overflow-hidden z-10 max-h-96 overflow-y-auto">
                {(() => {
                  // Group memberships by organization, preserving the order
                  // they came back from /auth/me.
                  const groups: {
                    orgId: string;
                    orgName: string;
                    items: typeof memberships;
                  }[] = [];
                  for (const m of memberships) {
                    const last = groups[groups.length - 1];
                    if (last && last.orgId === m.organization_id) {
                      last.items.push(m);
                    } else {
                      groups.push({
                        orgId: m.organization_id,
                        orgName: m.organization_name ?? "Unknown organization",
                        items: [m],
                      });
                    }
                  }
                  return groups.map((g, gi) => (
                    <div key={g.orgId}>
                      {gi > 0 && <div className="border-t border-[#252a36]" />}
                      <div className="px-3 pt-2 pb-1 text-xs uppercase tracking-wide font-semibold text-[#64748b]">
                        {g.orgName}
                      </div>
                      {g.items.map((m) => (
                        <button
                          key={m.tenant_id}
                          onClick={() => handleSwitch(m.tenant_id)}
                          className={`w-full text-left px-3 py-2 text-sm transition-colors ${
                            m.tenant_id === tenant?.id
                              ? "bg-brand-sky/15 text-accent-light"
                              : "text-[#94a3b8] hover:bg-white/5 hover:text-[#e2e8f0]"
                          }`}
                        >
                          <div className="flex items-center justify-between gap-2">
                            <span className="truncate">{m.tenant_name}</span>
                            {m.is_admin && (
                              <Shield className="w-3.5 h-3.5 text-accent-lavender shrink-0" />
                            )}
                          </div>
                        </button>
                      ))}
                    </div>
                  ));
                })()}
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

          {(showOrgSettings || user?.is_superadmin) && (
            <div className="border-t border-[#252a36] my-3" />
          )}

          {showOrgSettings && (
            <NavLink
              to="/organization-settings"
              className={({ isActive }) =>
                `flex items-center gap-3 px-3 py-2 rounded-lg text-sm transition-colors ${
                  isActive
                    ? "bg-accent-lavender/15 text-accent-lavender"
                    : "text-accent-lavender/60 hover:bg-white/5 hover:text-accent-lavender"
                }`
              }
            >
              <Building2 className="w-4 h-4" />
              Organization Settings
            </NavLink>
          )}

          {user?.is_superadmin && (
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
          )}
        </nav>

        <div className="p-3 border-t border-[#252a36]">
          <div className="flex items-center justify-between">
            <div className="text-sm truncate">
              <p className="font-medium text-[#e2e8f0]">{user?.name}</p>
              <p className="text-xs text-[#64748b]">{user?.email}</p>
            </div>
            <div className="flex gap-1">
              <Tooltip
                content={
                  theme === "dark"
                    ? "Switch to light mode"
                    : "Switch to dark mode"
                }
              >
                <button
                  onClick={toggleTheme}
                  aria-label="Toggle theme"
                  className="p-2 text-[#64748b] hover:text-[#e2e8f0] rounded transition-colors"
                >
                  {theme === "dark" ? (
                    <Sun className="w-4 h-4" />
                  ) : (
                    <Moon className="w-4 h-4" />
                  )}
                </button>
              </Tooltip>
              <Tooltip content={isDemoMode() ? "Exit demo" : "Log out"}>
                <button
                  onClick={() => {
                    if (isDemoMode()) {
                      exitDemo();
                      window.location.href = "/demo";
                    } else {
                      logout();
                    }
                  }}
                  aria-label={isDemoMode() ? "Exit demo" : "Log out"}
                  className="p-2 text-[#64748b] hover:text-[#e2e8f0] rounded transition-colors"
                >
                  <LogOut className="w-4 h-4" />
                </button>
              </Tooltip>
            </div>
          </div>
        </div>
      </aside>

      <main className="flex-1 overflow-auto">
        {isDemoMode() && (
          <div className="bg-accent-lavender/15 border-b border-accent-lavender/40 px-6 py-2 flex items-center gap-3 text-sm">
            <Info className="w-4 h-4 text-accent-lavender shrink-0" />
            <span className="text-page-text">
              <span className="font-semibold">Demo mode</span> — viewing
              seeded fake data. Editing and re-analysis are disabled.
            </span>
            <button
              onClick={() => {
                exitDemo();
                window.location.href = "/demo";
              }}
              className="ml-auto text-xs px-2.5 py-1 border border-accent-lavender text-accent-lavender rounded-md hover:bg-accent-lavender/10 transition-colors"
            >
              Exit demo
            </button>
          </div>
        )}
        <Outlet />
      </main>
    </div>
  );
}
