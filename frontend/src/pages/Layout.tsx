import { LogOut, ChevronRight } from "lucide-react";
import { NavLink, Outlet, useLocation } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import { FilterBar, type FilterApplicability } from "@/components/FilterBar";
import { useAuth } from "@/auth/AuthProvider";
import { cn } from "@/lib/utils";

const TABS: { to: string; label: string; applicability: FilterApplicability }[] = [
  { to: "/", label: "Overview", applicability: { restaurants: true, categories: false } },
  { to: "/best-sellers", label: "Best Sellers", applicability: { restaurants: true, categories: true } },
  { to: "/time-series", label: "Time Series", applicability: { restaurants: true, categories: false } },
  { to: "/peak-hours", label: "Peak Hours", applicability: { restaurants: true, categories: false } },
  { to: "/comparison", label: "Comparison", applicability: { restaurants: true, categories: false } },
];

export default function Layout() {
  const { state, logout } = useAuth();
  const location = useLocation();
  const currentTab = TABS.find((t) => t.to === location.pathname) ?? TABS[0];

  return (
    <div className="flex min-h-screen flex-col bg-background">
      <header className="flex items-center gap-4 border-b bg-card px-6 py-3">
        <div className="text-base font-semibold">Tortilla Analytics</div>
        <Separator orientation="vertical" className="h-5" />
        <nav className="flex items-center gap-1">
          {TABS.map((t) => (
            <NavLink
              key={t.to}
              // Carry the current ?from=...&to=...&r=...&cat=... across nav so
              // filter state survives a tab change. Without this, react-router
              // navigates to a clean path and nuqs resets to the URL defaults.
              to={{ pathname: t.to, search: location.search }}
              end={t.to === "/"}
              className={({ isActive }) =>
                cn(
                  "rounded-md px-3 py-1 text-sm transition-colors",
                  isActive ? "bg-secondary text-secondary-foreground" : "hover:bg-accent",
                )
              }
            >
              {t.label}
            </NavLink>
          ))}
        </nav>
        <div className="ml-auto flex items-center gap-3 text-sm">
          {state.status === "authed" && (
            <>
              <span className="text-muted-foreground">{state.user.username}</span>
              <Button variant="ghost" size="sm" onClick={logout}>
                <LogOut className="h-4 w-4" />
                Sign out
              </Button>
            </>
          )}
        </div>
      </header>

      <FilterBar applicability={currentTab.applicability} />

      <main className="flex-1 px-6 py-6">
        <Outlet />
      </main>

      <footer className="border-t bg-card px-6 py-2 text-xs text-muted-foreground">
        <span>Tortilla Restaurant Chain Analytics · v0.1.0</span>
        <ChevronRight className="mx-1 inline h-3 w-3" />
        <span>{location.pathname}</span>
      </footer>
    </div>
  );
}
