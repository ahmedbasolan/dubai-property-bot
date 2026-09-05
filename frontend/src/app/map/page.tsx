"use client";

import { useEffect, useState } from "react";
import dynamic from "next/dynamic";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { api, type MapFeature } from "@/lib/api";
import { MapPin, TrendingUp, Building2, DollarSign } from "lucide-react";

const LeafletMap = dynamic(
  () => import("@/components/leaflet-map").then((m) => m.LeafletMap),
  { ssr: false, loading: () => <div className="w-full h-full rounded-lg bg-accent/30 animate-pulse" /> }
);

const recColors: Record<string, string> = {
  INVEST: "#10b981",
  HOLD: "#f59e0b",
  AVOID: "#ef4444",
};

const recBg: Record<string, string> = {
  INVEST: "bg-emerald-500/20 text-emerald-400 border-emerald-500/30",
  HOLD: "bg-amber-500/20 text-amber-400 border-amber-500/30",
  AVOID: "bg-red-500/20 text-red-400 border-red-500/30",
};

export default function MapPage() {
  const [features, setFeatures] = useState<MapFeature[]>([]);
  const [loading, setLoading] = useState(true);
  const [selected, setSelected] = useState<MapFeature | null>(null);

  useEffect(() => {
    api.getMapData().then((data) => {
      setFeatures(data.features);
      setLoading(false);
    });
  }, []);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="animate-pulse text-muted-foreground">Loading map...</div>
      </div>
    );
  }

  const invest = features.filter((f) => f.recommendation === "INVEST");
  const hold = features.filter((f) => f.recommendation === "HOLD");
  const avoid = features.filter((f) => f.recommendation === "AVOID");

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Community Map</h1>
          <p className="text-muted-foreground mt-1">
            {features.length} communities — click markers for details
          </p>
        </div>
        <div className="flex items-center gap-4 text-xs">
          <div className="flex items-center gap-1.5">
            <div className="w-2.5 h-2.5 rounded-full bg-emerald-500" />
            <span className="text-muted-foreground">{invest.length} Invest</span>
          </div>
          <div className="flex items-center gap-1.5">
            <div className="w-2.5 h-2.5 rounded-full bg-amber-500" />
            <span className="text-muted-foreground">{hold.length} Hold</span>
          </div>
          <div className="flex items-center gap-1.5">
            <div className="w-2.5 h-2.5 rounded-full bg-red-500" />
            <span className="text-muted-foreground">{avoid.length} Avoid</span>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2">
          <Card className="overflow-hidden border-0">
            <div className="w-full h-[650px] rounded-lg overflow-hidden">
              <LeafletMap
                features={features}
                selected={selected}
                onSelect={setSelected}
              />
            </div>
          </Card>
        </div>

        <div className="space-y-4">
          {selected ? (
            <Card className="border-0 shadow-lg">
              <CardHeader className="pb-3">
                <div className="flex items-start justify-between">
                  <div>
                    <CardTitle className="text-xl">{selected.community}</CardTitle>
                    <p className="text-sm text-muted-foreground mt-1">
                      {selected.district || "Dubai"}
                    </p>
                  </div>
                  <Badge className={recBg[selected.recommendation]}>
                    {selected.recommendation}
                  </Badge>
                </div>
              </CardHeader>
              <CardContent className="space-y-4">
                {/* Score Ring */}
                <div className="flex items-center justify-center py-4">
                  <div className="relative w-28 h-28">
                    <svg viewBox="0 0 100 100" className="w-full h-full -rotate-90">
                      <circle
                        cx="50" cy="50" r="42"
                        fill="none"
                        stroke="#333"
                        strokeWidth="6"
                      />
                      <circle
                        cx="50" cy="50" r="42"
                        fill="none"
                        stroke={recColors[selected.recommendation]}
                        strokeWidth="6"
                        strokeLinecap="round"
                        strokeDasharray={`${(selected.composite_score / 100) * 264} 264`}
                      />
                    </svg>
                    <div className="absolute inset-0 flex flex-col items-center justify-center">
                      <span className="text-3xl font-bold">{selected.composite_score.toFixed(0)}</span>
                      <span className="text-xs text-muted-foreground">/ 100</span>
                    </div>
                  </div>
                </div>

                {/* Stats Grid */}
                <div className="grid grid-cols-2 gap-3">
                  <div className="p-3 rounded-lg bg-accent/50">
                    <div className="flex items-center gap-1.5 text-xs text-muted-foreground mb-1">
                      <TrendingUp size={12} />
                      Net Yield
                    </div>
                    <div className="text-xl font-bold text-emerald-400">
                      {selected.avg_net_yield.toFixed(1)}%
                    </div>
                  </div>
                  <div className="p-3 rounded-lg bg-accent/50">
                    <div className="flex items-center gap-1.5 text-xs text-muted-foreground mb-1">
                      <DollarSign size={12} />
                      Avg Price
                    </div>
                    <div className="text-xl font-bold">
                      {selected.avg_price >= 1000000
                        ? `AED ${(selected.avg_price / 1000000).toFixed(1)}M`
                        : `AED ${(selected.avg_price / 1000).toFixed(0)}K`
                      }
                    </div>
                  </div>
                </div>

                {/* Action Button */}
                <button
                  onClick={() => window.location.href = `/properties?community=${encodeURIComponent(selected.community)}`}
                  className="w-full py-2.5 rounded-lg font-medium text-sm transition-colors"
                  style={{
                    backgroundColor: recColors[selected.recommendation] + "20",
                    color: recColors[selected.recommendation],
                    border: `1px solid ${recColors[selected.recommendation]}40`,
                  }}
                >
                  View Properties in {selected.community}
                </button>
              </CardContent>
            </Card>
          ) : (
            <Card className="border-0">
              <CardContent className="py-12 text-center">
                <MapPin className="h-10 w-10 mx-auto text-muted-foreground/50 mb-3" />
                <p className="text-sm text-muted-foreground">
                  Click a community marker on the map to see investment details
                </p>
              </CardContent>
            </Card>
          )}

          {/* Community List */}
          <Card className="border-0">
            <CardHeader className="pb-2">
              <CardTitle className="text-sm">All Communities</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-1 max-h-[300px] overflow-y-auto">
                {features
                  .sort((a, b) => b.composite_score - a.composite_score)
                  .map((f) => (
                    <button
                      key={f.community}
                      onClick={() => setSelected(f)}
                      className={`w-full flex items-center justify-between px-3 py-2 rounded-lg text-sm transition-colors ${
                        selected?.community === f.community
                          ? "bg-accent"
                          : "hover:bg-accent/50"
                      }`}
                    >
                      <span className="flex items-center gap-2">
                        <div
                          className="w-2 h-2 rounded-full"
                          style={{ backgroundColor: recColors[f.recommendation] }}
                        />
                        {f.community}
                      </span>
                      <span className="font-medium text-muted-foreground">
                        {f.composite_score.toFixed(0)}
                      </span>
                    </button>
                  ))}
              </div>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
