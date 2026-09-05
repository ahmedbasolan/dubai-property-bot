"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";
import { useDataSource } from "@/components/data-source-provider";
import {
  LayoutDashboard,
  Building2,
  Trophy,
  TrendingUp,
  Map,
  Calculator,
  GitCompare,
  MessageSquare,
  Menu,
  X,
  Radio,
  Database,
} from "lucide-react";
import { useState } from "react";

const navItems = [
  { href: "/", label: "Dashboard", icon: LayoutDashboard },
  { href: "/chat", label: "Advisor", icon: MessageSquare },
  { href: "/properties", label: "Properties", icon: Building2 },
  { href: "/communities", label: "Leaderboard", icon: Trophy },
  { href: "/trends", label: "Trends", icon: TrendingUp },
  { href: "/map", label: "Map", icon: Map },
  { href: "/calculator", label: "Calculator", icon: Calculator },
  { href: "/compare", label: "Compare", icon: GitCompare },
];

export function Sidebar() {
  const pathname = usePathname();
  const [open, setOpen] = useState(false);
  const { useLive, setUseLive, source, bayutConfigured } = useDataSource();

  return (
    <>
      <button
        onClick={() => setOpen(!open)}
        className="fixed top-4 left-4 z-50 md:hidden bg-card border border-border rounded-lg p-2 shadow-lg btn-press"
      >
        {open ? <X size={20} /> : <Menu size={20} />}
      </button>

      {/* Backdrop */}
      <div
        className={cn(
          "fixed inset-0 bg-black/50 z-40 md:hidden transition-opacity duration-300",
          open ? "opacity-100" : "opacity-0 pointer-events-none"
        )}
        onClick={() => setOpen(false)}
      />

      <aside
        className={cn(
          "fixed md:static inset-y-0 left-0 z-50 w-64 bg-card border-r border-border flex flex-col transition-all duration-300 ease-out",
          open ? "translate-x-0" : "-translate-x-full md:translate-x-0"
        )}
      >
        <div className="p-6 border-b border-border">
          <h1 className="text-lg font-bold tracking-tight">
            Dubai Property
          </h1>
          <p className="text-xs text-muted-foreground mt-1">
            Investment Analysis Platform
          </p>
        </div>

        <nav className="flex-1 p-3 space-y-0.5 stagger-children">
          {navItems.map((item) => {
            const isActive = pathname === item.href;
            return (
              <Link
                key={item.href}
                href={item.href}
                onClick={() => setOpen(false)}
                className={cn(
                  "flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-all duration-200",
                  isActive
                    ? "bg-primary text-primary-foreground"
                    : "text-muted-foreground hover:bg-accent hover:text-accent-foreground"
                )}
              >
                <item.icon size={18} className="transition-transform duration-200" />
                {item.label}
              </Link>
            );
          })}
        </nav>

        <div className="p-4 border-t border-border space-y-3">
          {/* Data Source Toggle */}
          <div className="space-y-2">
            <div className="flex items-center gap-2 text-xs font-medium text-muted-foreground">
              <Database size={14} />
              Data Source
            </div>
            {bayutConfigured ? (
              <button
                onClick={() => setUseLive(!useLive)}
                className={cn(
                  "w-full flex items-center justify-between px-3 py-2 rounded-lg text-sm font-medium transition-all duration-200",
                  useLive
                    ? "bg-emerald-500/20 text-emerald-400 border border-emerald-500/30"
                    : "bg-accent text-muted-foreground border border-border"
                )}
              >
                <span className="flex items-center gap-2">
                  <Radio size={14} className={useLive ? "text-emerald-400" : "text-muted-foreground"} />
                  {useLive ? "Live (BayutAPI)" : "Mock Data"}
                </span>
                <div
                  className={cn(
                    "w-8 h-4 rounded-full transition-colors duration-200 relative",
                    useLive ? "bg-emerald-500" : "bg-muted"
                  )}
                >
                  <div
                    className={cn(
                      "absolute top-0.5 w-3 h-3 rounded-full bg-white transition-transform duration-200 ease-out",
                      useLive ? "translate-x-4" : "translate-x-0.5"
                    )}
                  />
                </div>
              </button>
            ) : (
              <div className="px-3 py-2 rounded-lg text-xs text-muted-foreground bg-accent/50 border border-border">
                Add BAYUT_API_KEY to .env for real data
              </div>
            )}
          </div>

          <div className="text-xs text-muted-foreground space-y-1">
            <p>73 Mock Transactions</p>
            <p>25 Communities</p>
            <p>7-Factor Scoring</p>
          </div>
        </div>
      </aside>
    </>
  );
}
