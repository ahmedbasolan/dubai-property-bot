"use client";

import { useEffect, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { api, type CommunityScore } from "@/lib/api";
import {
  Trophy,
} from "lucide-react";

export default function CommunitiesPage() {
  const [communities, setCommunities] = useState<CommunityScore[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let stale = false;
    api
      .getCommunities()
      .then((data) => {
        if (!stale) setCommunities(data.communities);
      })
      .catch((err: unknown) => {
        if (!stale) setError(err instanceof Error ? err.message : "Failed to load communities");
      })
      .finally(() => {
        if (!stale) setLoading(false);
      });
    return () => {
      stale = true;
    };
  }, []);

  if (error) {
    return (
      <div className="flex items-center justify-center h-full">
        <p className="text-sm text-red-400">Could not load communities: {error}</p>
      </div>
    );
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="flex flex-col items-center gap-4">
          <div className="relative w-10 h-10">
            <div className="absolute inset-0 rounded-full border-2 border-muted" />
            <div className="absolute inset-0 rounded-full border-2 border-primary border-t-transparent animate-spin" />
          </div>
          <span className="text-sm text-muted-foreground animate-fade-in">Loading leaderboard...</span>
        </div>
      </div>
    );
  }

  const recColors = {
    INVEST: "bg-emerald-500/20 text-emerald-400 border-emerald-500/30",
    HOLD: "bg-amber-500/20 text-amber-400 border-amber-500/30",
    AVOID: "bg-red-500/20 text-red-400 border-red-500/30",
  };

  return (
    <div className="p-6 space-y-6">
      <div className="animate-fade-in">
        <h1 className="text-3xl font-bold tracking-tight">
          Investment Leaderboard
        </h1>
        <p className="text-muted-foreground mt-1">
          Communities ranked by 5-factor investment score
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 stagger-children">
        {communities.map((c, i) => (
          <Card
            key={c.community}
            className={`relative overflow-hidden card-hover animate-fade-in-up ${
              i === 0
                ? "ring-2 ring-amber-500/50"
                : ""
            }`}
          >
            {i < 3 && (
              <div className="absolute top-3 right-3">
                <Trophy
                  size={20}
                  className={
                    i === 0
                      ? "text-amber-400"
                      : i === 1
                      ? "text-gray-300"
                      : "text-amber-600"
                  }
                />
              </div>
            )}
            <CardHeader className="pb-3">
              <div className="flex items-start justify-between">
                <div>
                  <CardTitle className="text-lg">
                    <span className="text-muted-foreground mr-2">
                      #{i + 1}
                    </span>
                    {c.community}
                  </CardTitle>
                  <p className="text-sm text-muted-foreground">{c.district ?? "Dubai"}</p>
                </div>
                <Badge className={recColors[c.recommendation]}>
                  {c.recommendation}
                </Badge>
              </div>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="flex items-center justify-between">
                <div className="text-center">
                  <div className="text-3xl font-bold">
                    {(c.composite_score ?? 0).toFixed(0)}
                  </div>
                  <div className="text-xs text-muted-foreground">
                    Score / 100
                  </div>
                </div>
                <div className="h-12 w-px bg-border" />
                <div className="text-center">
                  <div className="text-3xl font-bold text-emerald-400">
                    {(c.avg_net_yield_pct ?? 0).toFixed(1)}%
                  </div>
                  <div className="text-xs text-muted-foreground">
                    Net Yield
                  </div>
                </div>
                <div className="h-12 w-px bg-border" />
                <div className="text-center">
                  <div className="text-3xl font-bold">
                    {((c.avg_price_per_sqft ?? 0) / 1000).toFixed(1)}K
                  </div>
                  <div className="text-xs text-muted-foreground">
                    AED / sqft
                  </div>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-2 text-xs">
                <div className="flex items-center justify-between p-2 rounded bg-accent/50">
                  <span className="text-muted-foreground">Price Grade</span>
                  <span className="font-medium">{c.price_score ?? "—"}</span>
                </div>
                <div className="flex items-center justify-between p-2 rounded bg-accent/50">
                  <span className="text-muted-foreground">Yield Grade</span>
                  <span className="font-medium">{c.yield_score ?? "—"}</span>
                </div>
                <div className="flex items-center justify-between p-2 rounded bg-accent/50">
                  <span className="text-muted-foreground">Supply Risk</span>
                  <span
                    className={`font-medium ${
                      c.supply_risk === "LOW"
                        ? "text-emerald-400"
                        : c.supply_risk === "MEDIUM"
                        ? "text-amber-400"
                        : "text-red-400"
                    }`}
                  >
                    {c.supply_risk ?? "—"}
                  </span>
                </div>
                <div className="flex items-center justify-between p-2 rounded bg-accent/50">
                  <span className="text-muted-foreground">Pipeline</span>
                  <span className="font-medium">
                    {c.pipeline_pct_of_stock ?? 0}%
                  </span>
                </div>
                <div className="flex items-center justify-between p-2 rounded bg-accent/50">
                  <span className="text-muted-foreground">Developer</span>
                  <span className="font-medium">{c.master_developer ?? "—"}</span>
                </div>
                <div className="flex items-center justify-between p-2 rounded bg-accent/50">
                  <span className="text-muted-foreground">Occupancy</span>
                  <span className="font-medium">{c.occupancy_rate ?? 0}%</span>
                </div>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  );
}
