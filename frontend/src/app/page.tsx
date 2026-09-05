"use client";

import { useEffect, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { api, type CommunityScore, type Transaction } from "@/lib/api";
import {
  Building2,
  TrendingUp,
  MapPin,
  DollarSign,
  ArrowUpRight,
  ArrowDownRight,
} from "lucide-react";

export default function Dashboard() {
  const [communities, setCommunities] = useState<CommunityScore[]>([]);
  const [transactions, setTransactions] = useState<Transaction[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([api.getCommunities(), api.getTransactions()]).then(
      ([c, t]) => {
        setCommunities(c.communities);
        setTransactions(t.transactions);
        setLoading(false);
      }
    );
  }, []);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="animate-pulse text-muted-foreground">Loading...</div>
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
    communities.length;
  const avgScore =
    communities.reduce((s, c) => s + c.composite_score, 0) /
    communities.length;

  return (
    <div className="p-6 space-y-6">
      <div>
        <h1 className="text-3xl font-bold tracking-tight">Dashboard</h1>
        <p className="text-muted-foreground mt-1">
          Dubai real estate investment overview
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              Total Communities
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

        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              Avg Net Yield
            </CardTitle>
            <TrendingUp className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-3xl font-bold">{avgYield.toFixed(1)}%</div>
            <p className="text-xs text-muted-foreground mt-1">
              Across all communities
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              Avg Score
            </CardTitle>
            <MapPin className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-3xl font-bold">{avgScore.toFixed(0)}/100</div>
            <p className="text-xs text-muted-foreground mt-1">
              Investment composite
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              Recommendations
            </CardTitle>
            <DollarSign className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="flex gap-2">
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
        <Card>
          <CardHeader>
            <CardTitle>Top Communities by Score</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              {communities.slice(0, 8).map((c) => (
                <div
                  key={c.community}
                  className="flex items-center justify-between p-3 rounded-lg bg-accent/50"
                >
                  <div>
                    <div className="font-medium text-sm">{c.community}</div>
                    <div className="text-xs text-muted-foreground">
                      {c.district}
                    </div>
                  </div>
                  <div className="text-right">
                    <div className="font-bold text-sm">
                      {c.composite_score.toFixed(0)}/100
                    </div>
                    <div className="flex items-center gap-1 text-xs">
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

        <Card>
          <CardHeader>
            <CardTitle>Recent Transactions</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              {transactions.slice(0, 8).map((t) => (
                <div
                  key={t.transaction_id}
                  className="flex items-center justify-between p-3 rounded-lg bg-accent/50"
                >
                  <div>
                    <div className="font-medium text-sm">
                      {t.bedrooms}BR {t.property_type} — {t.community}
                    </div>
                    <div className="text-xs text-muted-foreground">
                      {t.size_sqft.toLocaleString()} sqft • {t.developer}
                    </div>
                  </div>
                  <div className="text-right">
                    <div className="font-bold text-sm">
                      AED {(t.price_aed / 1000000).toFixed(2)}M
                    </div>
                    <div className="text-xs text-emerald-400">
                      {t.roi_pct}% ROI
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
