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

function formatBedrooms(n: number) {
  return n === 0 ? "Studio" : `${n}BR`;
}

export default function Dashboard() {
  const [communities, setCommunities] = useState<CommunityScore[]>([]);
  const [transactions, setTransactions] = useState<Transaction[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const { useLive } = useDataSource();

  useEffect(() => {
    setLoading(true);
    setError(null);
    Promise.all([api.getCommunities(), api.getTransactions({}, useLive)])
      .then(([c, t]) => {
        setCommunities(c.communities);
        setTransactions(t.transactions);
        setLoading(false);
      })
      .catch((err) => {
        setError(err.message || "Failed to load data");
        setLoading(false);
      });
  }, [useLive]);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="flex flex-col items-center gap-3">
          <div className="w-8 h-8 border-2 border-primary border-t-transparent rounded-full animate-spin" />
          <span className="text-sm text-muted-foreground">Loading dashboard...</span>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex items-center justify-center h-full">
        <Card className="max-w-md">
          <CardContent className="py-8 text-center">
            <AlertCircle className="h-10 w-10 mx-auto text-red-400 mb-3" />
            <p className="font-medium">Failed to load data</p>
            <p className="text-sm text-muted-foreground mt-1">{error}</p>
            <button
              onClick={() => window.location.reload()}
              className="mt-4 px-4 py-2 rounded-lg bg-accent text-sm hover:bg-accent/80"
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
  const avgYield =
    communities.reduce((s, c) => s + c.avg_net_yield_pct, 0) /
    (communities.length || 1);
  const avgScore =
    communities.reduce((s, c) => s + c.composite_score, 0) /
    (communities.length || 1);

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Dashboard</h1>
          <p className="text-muted-foreground mt-1">
            Dubai real estate investment overview
          </p>
        </div>
        <div className="flex items-center gap-2 text-xs">
          <Radio size={14} className={useLive ? "text-emerald-400" : "text-muted-foreground"} />
          <span className={useLive ? "text-emerald-400" : "text-muted-foreground"}>
            {useLive ? "Live DLD Data" : "Mock Data"}
          </span>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <Card className="border-0 bg-gradient-to-br from-card to-card/50">
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              Communities
            </CardTitle>
            <Building2 className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-3xl font-bold">{communities.length}</div>
            <p className="text-xs text-muted-foreground mt-1">
              {transactions.length} transactions
            </p>
          </CardContent>
        </Card>

        <Card className="border-0 bg-gradient-to-br from-emerald-500/10 to-emerald-500/5">
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium text-emerald-400">
              Avg Net Yield
            </CardTitle>
            <TrendingUp className="h-4 w-4 text-emerald-400" />
          </CardHeader>
          <CardContent>
            <div className="text-3xl font-bold text-emerald-400">
              {avgYield.toFixed(1)}%
            </div>
            <p className="text-xs text-muted-foreground mt-1">
              Across all communities
            </p>
          </CardContent>
        </Card>

        <Card className="border-0 bg-gradient-to-br from-blue-500/10 to-blue-500/5">
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium text-blue-400">
              Avg Score
            </CardTitle>
            <MapPin className="h-4 w-4 text-blue-400" />
          </CardHeader>
          <CardContent>
            <div className="text-3xl font-bold text-blue-400">
              {avgScore.toFixed(0)}<span className="text-lg text-muted-foreground">/100</span>
            </div>
            <p className="text-xs text-muted-foreground mt-1">
              Investment composite
            </p>
          </CardContent>
        </Card>

        <Card className="border-0 bg-gradient-to-br from-card to-card/50">
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              Recommendations
            </CardTitle>
            <DollarSign className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="flex flex-wrap gap-2">
              <Badge className="bg-emerald-500/20 text-emerald-400 border-emerald-500/30">
                {investCount} Invest
              </Badge>
              <Badge className="bg-amber-500/20 text-amber-400 border-amber-500/30">
                {holdCount} Hold
              </Badge>
              <Badge className="bg-red-500/20 text-red-400 border-red-500/30">
                {avoidCount} Avoid
              </Badge>
            </div>
          </CardContent>
        </Card>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Card className="border-0">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <TrendingUp size={18} className="text-emerald-400" />
              Top Communities by Score
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-2">
              {communities.slice(0, 8).map((c, i) => (
                <div
                  key={c.community}
                  className="flex items-center justify-between p-3 rounded-lg hover:bg-accent/50 transition-colors group"
                >
                  <div className="flex items-center gap-3">
                    <span className="text-xs font-mono text-muted-foreground w-5">
                      {i + 1}.
                    </span>
                    <div>
                      <div className="font-medium text-sm group-hover:text-foreground transition-colors">
                        {c.community}
                      </div>
                      <div className="text-xs text-muted-foreground">
                        {c.district}
                      </div>
                    </div>
                  </div>
                  <div className="text-right">
                    <div className="font-bold text-sm">
                      {c.composite_score.toFixed(0)}<span className="text-muted-foreground text-xs">/100</span>
                    </div>
                    <div className="flex items-center gap-1 text-xs justify-end">
                      {c.avg_net_yield_pct > 7 ? (
                        <ArrowUpRight className="h-3 w-3 text-emerald-400" />
                      ) : (
                        <ArrowDownRight className="h-3 w-3 text-red-400" />
                      )}
                      <span
                        className={
                          c.avg_net_yield_pct > 7
                            ? "text-emerald-400"
                            : "text-red-400"
                        }
                      >
                        {c.avg_net_yield_pct.toFixed(1)}%
                      </span>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>

        <Card className="border-0">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Building2 size={18} className="text-blue-400" />
              Recent Transactions
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-2">
              {transactions.slice(0, 8).map((t) => (
                <div
                  key={t.transaction_id}
                  className="flex items-center justify-between p-3 rounded-lg hover:bg-accent/50 transition-colors group"
                >
                  <div>
                    <div className="font-medium text-sm group-hover:text-foreground transition-colors">
                      {formatBedrooms(t.bedrooms)} {t.property_type} — {t.community}
                    </div>
                    <div className="text-xs text-muted-foreground">
                      {t.size_sqft.toLocaleString()} sqft
                      {t.developer ? ` • ${t.developer}` : ""}
                    </div>
                  </div>
                  <div className="text-right">
                    <div className="font-bold text-sm">
                      AED {(t.price_aed / 1000000).toFixed(2)}M
                    </div>
                    <div className="text-xs text-emerald-400">
                      {t.roi_pct}% yield
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
