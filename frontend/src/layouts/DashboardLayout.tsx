import {
  BarChart3,
  Building2,
  ChevronsUpDown,
  Cog,
  FileText,
  Info,
  LayoutDashboard,
  LogOut,
  Menu,
  Moon,
  Shield,
  Sun,
  Users,
} from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { NavLink, Outlet, useLocation } from "react-router-dom";
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
  // Below `lg`, the sidebar is a slide-in drawer toggled by a hamburger.
  // Above `lg`, it's always visible and `sidebarOpen` is irrelevant.
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const location = useLocation();

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

  // Saved Y offset used by the body-lock effect to restore scroll on
  // drawer close. Hoisted into a ref so the navigation effect can zero
  // it out before the lock's cleanup runs (otherwise the restore
  // overrides the scroll-to-top we want on route change).
  const lockedScrollYRef = useRef(0);

  // Auto-close the mobile drawer on navigation, and reset scroll to
  // the top so the new page doesn't open at the previous page's
  // scroll offset (React Router preserves it by default).
  useEffect(() => {
    lockedScrollYRef.current = 0;
    setSidebarOpen(false);
    window.scrollTo(0, 0);
  }, [location.pathname]);

  // ESC closes the drawer.
  useEffect(() => {
    if (!sidebarOpen) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setSidebarOpen(false);
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [sidebarOpen]);

  // Lock the page from scrolling while the drawer is open. iOS Safari
  // ignores `overflow: hidden` on the body for touch scrolling, so we
  // also pin the body with `position: fixed` and the negative current
  // scroll offset, then restore the scroll position on close.
  // The pathname effect zeros lockedScrollYRef so navigation lands at
  // the top of the new page rather than restoring the prior offset.
  useEffect(() => {
    if (!sidebarOpen) return;
    const body = document.body;
    lockedScrollYRef.current = window.scrollY;
    const prev = {
      overflow: body.style.overflow,
      position: body.style.position,
      top: body.style.top,
      left: body.style.left,
      right: body.style.right,
      width: body.style.width,
    };
    body.style.overflow = "hidden";
    body.style.position = "fixed";
    body.style.top = `-${lockedScrollYRef.current}px`;
    body.style.left = "0";
    body.style.right = "0";
    body.style.width = "100%";
    return () => {
      body.style.overflow = prev.overflow;
      body.style.position = prev.position;
      body.style.top = prev.top;
      body.style.left = prev.left;
      body.style.right = prev.right;
      body.style.width = prev.width;
      window.scrollTo(0, lockedScrollYRef.current);
    };
  }, [sidebarOpen]);

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
    <div className="flex min-h-screen bg-page-bg">
      {/* Mobile drawer backdrop */}
      {sidebarOpen && (
        <div
          onClick={() => setSidebarOpen(false)}
          aria-hidden="true"
          className="fixed inset-0 bg-black/50 z-30 lg:hidden"
        />
      )}

      {/* Sidebar — always dark, uses dark palette colors directly. On
          screens below lg it's a slide-in drawer (fixed). On lg+ it
          becomes a sticky sidebar at the top of its column so the body
          scrolls naturally underneath; that lets mobile browsers
          collapse their URL bar on scroll instead of getting trapped
          inside an inner overflow:auto container. */}
      <aside
        className={`fixed lg:sticky lg:top-0 top-0 left-0 h-[100dvh] z-40 w-64 lg:self-start bg-surface-dark dark:bg-surface-elevated flex flex-col transition-transform duration-200 ease-out lg:translate-x-0 ${
          sidebarOpen ? "translate-x-0" : "-translate-x-full lg:translate-x-0"
        }`}
      >
        <div className="px-3 py-3 border-b border-[#252a36]">
          <div className="flex items-center gap-2 min-w-0">
            <img
              src="/callisto-icon-animated.svg"
              alt=""
              className="w-8 h-8 shrink-0"
            />
            <img
              src="/callisto-wordmark-dark.svg"
              alt="Callisto"
              className="h-5 min-w-0 max-w-full object-contain"
            />
          </div>

          {/* Tenant switcher */}
          <div className="mt-2 relative" ref={pickerRef}>
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

        <nav className="flex-1 min-h-0 p-3 space-y-1 overflow-y-auto">
          {tenant &&
            navItems.map(({ to, icon: Icon, label }) => (
              <NavLink
                key={to}
                to={to}
                end={to === "/"}
                className={({ isActive }) =>
                  `flex items-center gap-3 px-3 py-1.5 rounded-lg text-sm transition-colors ${
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
                `flex items-center gap-3 px-3 py-1.5 rounded-lg text-sm transition-colors ${
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
                `flex items-center gap-3 px-3 py-1.5 rounded-lg text-sm transition-colors ${
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
                `flex items-center gap-3 px-3 py-1.5 rounded-lg text-sm transition-colors ${
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

      <main className="flex-1 min-w-0">
        {/* Mobile-only top bar with hamburger + small wordmark. Hidden
            on lg+ where the sidebar is always visible. */}
        <div className="lg:hidden sticky top-0 z-20 flex items-center gap-3 px-4 py-3 bg-surface-dark text-white border-b border-[#252a36]">
          <button
            onClick={() => setSidebarOpen(true)}
            aria-label="Open menu"
            className="p-1.5 -ml-1 hover:bg-white/10 rounded transition-colors"
          >
            <Menu className="w-5 h-5" />
          </button>
          <img
            src="/callisto-icon-animated.svg"
            alt=""
            className="w-7 h-7 shrink-0"
          />
          <img
            src="/callisto-wordmark-dark.svg"
            alt="Callisto"
            className="h-5 min-w-0 max-w-[140px] object-contain"
          />
        </div>

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
