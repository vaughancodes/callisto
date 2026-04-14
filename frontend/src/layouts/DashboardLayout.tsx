import {
  BarChart3,
  FileText,
  LayoutDashboard,
  LogOut,
  Moon,
  Shield,
  Sun,
  Users,
} from "lucide-react";
import { NavLink, Outlet } from "react-router-dom";
import { useAuth } from "../contexts/AuthContext";
import { useTheme } from "../contexts/ThemeContext";

export function DashboardLayout() {
  const { user, tenant, logout } = useAuth();
  const { theme, toggle: toggleTheme } = useTheme();

  const navItems = [
    { to: "/", icon: LayoutDashboard, label: "Dashboard" },
    { to: "/contacts", icon: Users, label: "Contacts" },
    { to: "/templates", icon: FileText, label: "Templates" },
    { to: "/analytics", icon: BarChart3, label: "Analytics" },
  ];

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
          <p className="text-xs text-[#64748b] mt-2">
            {tenant?.name ?? "No tenant assigned"}
          </p>
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
                title={theme === "dark" ? "Switch to light mode" : "Switch to dark mode"}
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
