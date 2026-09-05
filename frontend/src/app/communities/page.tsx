"use client";

import { useEffect, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { api, type CommunityScore } from "@/lib/api";
import {
  Trophy,
  TrendingUp,
  TrendingDown,
  ArrowUpRight,
  ArrowDownRight,
} from "lucide-react";

export default function CommunitiesPage() {
  const [communities, setCommunities] = useState<CommunityScore[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.getCommunities().then((data) => {
      setCommunities(data.communities);
      setLoading(false);
    });
  }, []);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="animate-pulse text-muted-foreground">
          Loading leaderboard...
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
      <div>
        <h1 className="text-3xl font-bold tracking-tight">
          Investment Leaderboard
        </h1>
        <p className="text-muted-foreground mt-1">
          Communities ranked by 7-factor investment score
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {communities.map((c, i) => (
          <Card
            key={c.community}
            className={`relative overflow-hidden ${
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
                  <p className="text-sm text-muted-foreground">{c.district}</p>
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
                    {c.composite_score.toFixed(0)}
                  </div>
                  <div className="text-xs text-muted-foreground">
                    Score / 100
                  </div>
                </div>
                <div className="h-12 w-px bg-border" />
                <div className="text-center">
                  <div className="text-3xl font-bold text-emerald-400">
                    {c.avg_net_yield_pct.toFixed(1)}%
                  </div>
                  <div className="text-xs text-muted-foreground">
                    Net Yield
                  </div>
                </div>
                <div className="h-12 w-px bg-border" />
                <div className="text-center">
                  <div className="text-3xl font-bold">
                    {(c.avg_price_per_sqft / 1000).toFixed(1)}K
                  </div>
                  <div className="text-xs text-muted-foreground">
                    AED / sqft
                  </div>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-2 text-xs">
                <div className="flex items-center justify-between p-2 rounded bg-accent/50">
                  <span className="text-muted-foreground">Price Score</span>
                  <span className="font-medium">{c.price_score}/100</span>
                </div>
                <div className="flex items-center justify-between p-2 rounded bg-accent/50">
                  <span className="text-muted-foreground">Yield Score</span>
                  <span className="font-medium">{c.yield_score}/100</span>
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
                    {c.supply_risk}
                  </span>
                </div>
                <div className="flex items-center justify-between p-2 rounded bg-accent/50">
                  <span className="text-muted-foreground">Pipeline</span>
                  <span className="font-medium">
                    {c.pipeline_pct_of_stock}%
                  </span>
                </div>
                <div className="flex items-center justify-between p-2 rounded bg-accent/50">
                  <span className="text-muted-foreground">Developer</span>
                  <span className="font-medium">{c.master_developer}</span>
                </div>
                <div className="flex items-center justify-between p-2 rounded bg-accent/50">
                  <span className="text-muted-foreground">Occupancy</span>
                  <span className="font-medium">{c.occupancy_rate}%</span>
                </div>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  );
}
