"use client";

import { useEffect, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { api, type CommunityScore, type Transaction } from "@/lib/api";
import { useDataSource } from "@/components/data-source-provider";
import {
  Building2,
  TrendingUp,
  MapPin,
  DollarSign,
  ArrowUpRight,
  ArrowDownRight,
  Radio,
  AlertCircle,
} from "lucide-react";

function formatBedrooms(n: number | null) {
  if (n === null || n === undefined) return "";
  return n === 0 ? "Studio" : `${n}BR`;
}

function getCommunityName(community: unknown): string {
  if (typeof community === "string") return community;
  if (community && typeof community === "object") {
    const c = community as Record<string, unknown>;
    return (c.name || c.name_l1 || c.name_l2 || c.name_l3) as string || "Unknown";
  }
  return "Unknown";
}

function getPropertyType(pt: unknown): string {
  if (typeof pt === "string") return pt;
  if (Array.isArray(pt) && pt.length > 0) {
    const first = pt[0] as Record<string, unknown> | null;
    return (first?.name || first?.name_l1) as string || "Property";
  }
  if (pt && typeof pt === "object") {
    const o = pt as Record<string, unknown>;
    return (o.name || o.name_l1) as string || "Property";
  }
  return "Property";
}

export default function Dashboard() {
  const [communities, setCommunities] = useState<CommunityScore[]>([]);
  const [transactions, setTransactions] = useState<Transaction[]>([]);
  const [transactionTotal, setTransactionTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const { useLive } = useDataSource();

  useEffect(() => {
    let stale = false;
    Promise.all([api.getCommunities(), api.getTransactions({ limit: "8" }, useLive)])
      .then(([c, t]) => {
        if (stale) return;
        setCommunities(c.communities);
        setTransactions(t.transactions);
        setTransactionTotal(t.total ?? t.transactions.length);
        setError(null);
        setLoading(false);
      })
      .catch((err) => {
        if (stale) return;
        setError(err instanceof Error ? err.message : "Failed to load data");
        setLoading(false);
      });
    return () => {
      stale = true;
    };
  }, [useLive]);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="flex flex-col items-center gap-4">
          <div className="relative w-10 h-10">
            <div className="absolute inset-0 rounded-full border-2 border-muted" />
            <div className="absolute inset-0 rounded-full border-2 border-primary border-t-transparent animate-spin" />
          </div>
          <span className="text-sm text-muted-foreground animate-fade-in">Loading dashboard...</span>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex items-center justify-center h-full">
        <Card className="max-w-md animate-scale-in">
          <CardContent className="py-8 text-center">
            <AlertCircle className="h-10 w-10 mx-auto text-red-400 mb-3" />
            <p className="font-medium">Failed to load data</p>
            <p className="text-sm text-muted-foreground mt-1">{error}</p>
            <button
              onClick={() => window.location.reload()}
              className="mt-4 px-4 py-2 rounded-lg bg-accent text-sm hover:bg-accent/80 btn-press"
            >
              Retry
            </button>
          </CardContent>
        </Card>
      </div>
    );
  }

  const investCount = communities.filter(
    (c) => c.recommendation === "INVEST"
  ).length;
  const holdCount = communities.filter(
    (c) => c.recommendation === "HOLD"
  ).length;
  const avoidCount = communities.filter(
    (c) => c.recommendation === "AVOID"
  ).length;
  // Only communities with enough Ejari contracts have a yield and a score.
  const scored = communities.filter((c) => c.composite_score !== null);
  const avgYield =
    scored.reduce((s, c) => s + (c.avg_roi_pct ?? 0), 0) / (scored.length || 1);
  const avgScore =
    scored.reduce((s, c) => s + (c.composite_score ?? 0), 0) / (scored.length || 1);

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between animate-fade-in">
        <div>
          <h1 className="text-3xl font-bold tracking-tight font-[family-name:var(--font-cinzel)] text-gradient">
            Dashboard
          </h1>
          <p className="text-muted-foreground mt-1">
            Dubai real estate investment overview
          </p>
        </div>
        <div className="flex items-center gap-2 text-xs glass-badge rounded-full px-3 py-1.5">
          <Radio size={14} className={useLive ? "text-emerald-400" : "text-muted-foreground"} />
          <span className={useLive ? "text-emerald-400" : "text-muted-foreground"}>
            {useLive ? "Live listings (Bayut)" : "DLD open data, Jan–Sep 2026"}
          </span>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 stagger-children">
        <Card className="glass-card border-0 animate-fade-in-up">
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              Communities
            </CardTitle>
            <Building2 className="h-4 w-4 text-primary" />
          </CardHeader>
          <CardContent>
            <div className="text-3xl font-bold tabular-nums">{communities.length}</div>
            <p className="text-xs text-muted-foreground mt-1">
              {transactionTotal.toLocaleString()} registered sales
            </p>
          </CardContent>
        </Card>

        <Card className="glass-card border-0 animate-fade-in-up">
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium text-emerald-600 dark:text-emerald-400">
              Avg Gross Yield
            </CardTitle>
            <TrendingUp className="h-4 w-4 text-emerald-600 dark:text-emerald-400" />
          </CardHeader>
          <CardContent>
            <div className="text-3xl font-bold text-emerald-600 dark:text-emerald-400 tabular-nums">
              {scored.length ? `${avgYield.toFixed(1)}%` : "n/a"}
            </div>
            <p className="text-xs text-muted-foreground mt-1">
              {scored.length} of {communities.length} communities have rent data
            </p>
          </CardContent>
        </Card>

        <Card className="glass-card border-0 animate-fade-in-up">
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium text-primary">
              Avg Score
            </CardTitle>
            <MapPin className="h-4 w-4 text-primary" />
          </CardHeader>
          <CardContent>
            <div className="text-3xl font-bold text-primary tabular-nums">
              {scored.length ? avgScore.toFixed(0) : "—"}<span className="text-lg text-muted-foreground">/100</span>
            </div>
            <p className="text-xs text-muted-foreground mt-1">
              Investment composite
            </p>
          </CardContent>
        </Card>

        <Card className="glass-card border-0 animate-fade-in-up">
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              Recommendations
            </CardTitle>
            <DollarSign className="h-4 w-4 text-accent" />
          </CardHeader>
          <CardContent>
            <div className="flex flex-wrap gap-2">
              <Badge className="bg-emerald-500/20 text-emerald-600 dark:text-emerald-400 border-emerald-500/30">
                {investCount} Invest
              </Badge>
              <Badge className="bg-amber-500/20 text-amber-600 dark:text-amber-400 border-amber-500/30">
                {holdCount} Hold
              </Badge>
              <Badge className="bg-red-500/20 text-red-600 dark:text-red-400 border-red-500/30">
                {avoidCount} Avoid
              </Badge>
              {communities.length - scored.length > 0 && (
                <Badge className="bg-muted text-muted-foreground border-border">
                  {communities.length - scored.length} Not enough data
                </Badge>
              )}
            </div>
          </CardContent>
        </Card>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Card className="glass-card border-0 animate-fade-in-up" style={{ animationDelay: "200ms" }}>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 font-[family-name:var(--font-cinzel)]">
              <TrendingUp size={18} className="text-primary" />
              Top Communities by Score
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-1 stagger-children">
              {communities.slice(0, 8).map((c, i) => (
                <div
                  key={c.community}
                  className="flex items-center justify-between p-3 rounded-lg list-item-hover group cursor-default"
                >
                  <div className="flex items-center gap-3">
                    <span className="text-xs font-mono text-muted-foreground w-5 tabular-nums">
                      {i + 1}.
                    </span>
                    <div>
                      <div className="font-medium text-sm group-hover:text-foreground transition-colors duration-200">
                        {c.community}
                      </div>
                      <div className="text-xs text-muted-foreground">
                        {c.transaction_count.toLocaleString()} ready sales
                      </div>
                    </div>
                  </div>
                  <div className="text-right">
                    <div className="font-bold text-sm tabular-nums">
                      {c.composite_score === null ? "—" : c.composite_score.toFixed(0)}
                      <span className="text-muted-foreground text-xs">/100</span>
                    </div>
                    {c.avg_roi_pct === null ? (
                      <div className="text-xs text-muted-foreground">no rent data</div>
                    ) : (
                      <div className="flex items-center gap-1 text-xs justify-end">
                        {c.avg_roi_pct >= 7 ? (
                          <ArrowUpRight className="h-3 w-3 text-emerald-500" />
                        ) : (
                          <ArrowDownRight className="h-3 w-3 text-red-500" />
                        )}
                        <span
                          className={
                            c.avg_roi_pct >= 7
                              ? "text-emerald-600 dark:text-emerald-400"
                              : "text-red-500"
                          }
                        >
                          {c.avg_roi_pct.toFixed(1)}% gross
                        </span>
                      </div>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>

        <Card className="glass-card border-0 animate-fade-in-up" style={{ animationDelay: "300ms" }}>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 font-[family-name:var(--font-cinzel)]">
              <Building2 size={18} className="text-accent" />
              Latest Registered Sales
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-1 stagger-children">
              {transactions.slice(0, 8).map((t) => (
                <div
                  key={t.transaction_id}
                  className="flex items-center justify-between p-3 rounded-lg list-item-hover group cursor-default"
                >
                  <div>
                    <div className="font-medium text-sm group-hover:text-foreground transition-colors duration-200">
                      {formatBedrooms(t.bedrooms)} {getPropertyType(t.property_type)} — {getCommunityName(t.community)}
                    </div>
                    <div className="text-xs text-muted-foreground">
                      {t.size_sqft != null ? t.size_sqft.toLocaleString() : "—"} sqft • {t.transaction_date}
                      {t.project ? ` • ${t.project}` : ""}
                    </div>
                  </div>
                  <div className="text-right">
                    <div className="font-bold text-sm tabular-nums">
                      AED {((t.price_aed ?? 0) / 1000000).toFixed(2)}M
                    </div>
                    <div className="text-xs text-emerald-600 dark:text-emerald-400 tabular-nums">
                      {t.roi_pct != null ? `${t.roi_pct.toFixed(1)}% est. yield` : t.handover_status}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
