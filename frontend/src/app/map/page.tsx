"use client";

import { useEffect, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { api, type MapFeature } from "@/lib/api";
import { MapPin } from "lucide-react";

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

  const center = { lat: 25.2048, lng: 55.2708 };

  const recColors: Record<string, string> = {
    INVEST: "#10b981",
    HOLD: "#f59e0b",
    AVOID: "#ef4444",
  };

  return (
    <div className="p-6 space-y-6">
      <div>
        <h1 className="text-3xl font-bold tracking-tight">Community Map</h1>
        <p className="text-muted-foreground mt-1">
          {features.length} communities with investment scores
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2">
          <Card className="overflow-hidden">
            <div className="relative w-full h-[600px] bg-accent/30 rounded-lg">
              <svg viewBox="0 0 800 600" className="w-full h-full">
                <defs>
                  <radialGradient id="glow" cx="50%" cy="50%" r="50%">
                    <stop offset="0%" stopColor="#10b981" stopOpacity="0.2" />
                    <stop offset="100%" stopColor="#10b981" stopOpacity="0" />
                  </radialGradient>
                </defs>

                <rect width="800" height="600" fill="url(#glow)" />

                <text
                  x="400"
                  y="300"
                  textAnchor="middle"
                  fill="#555"
                  fontSize="14"
                >
                  Dubai Map View
                </text>

                {features.map((f, i) => {
                  const x = 100 + ((i * 267) % 600);
                  const y = 80 + ((i * 173) % 440);
                  const color = recColors[f.recommendation] || "#888";
                  const radius = 6 + (f.composite_score / 100) * 10;

                  return (
                    <g
                      key={f.community}
                      onClick={() => setSelected(f)}
                      className="cursor-pointer"
                    >
                      <circle
                        cx={x}
                        cy={y}
                        r={radius + 4}
                        fill={color}
                        opacity={0.2}
                      />
                      <circle
                        cx={x}
                        cy={y}
                        r={radius}
                        fill={color}
                        opacity={0.8}
                        stroke="#fff"
                        strokeWidth={1}
                      />
                      <text
                        x={x}
                        y={y - radius - 6}
                        textAnchor="middle"
                        fill="#ccc"
                        fontSize="10"
                        fontWeight="bold"
                      >
                        {f.community.length > 15
                          ? f.community.slice(0, 15) + "..."
                          : f.community}
                      </text>
                      <text
                        x={x}
                        y={y + 3}
                        textAnchor="middle"
                        fill="#fff"
                        fontSize="9"
                        fontWeight="bold"
                      >
                        {f.composite_score.toFixed(0)}
                      </text>
                    </g>
                  );
                })}
              </svg>
            </div>
          </Card>
        </div>

        <div className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle className="text-sm">Legend</CardTitle>
            </CardHeader>
            <CardContent className="space-y-2">
              <div className="flex items-center gap-2 text-sm">
                <div className="w-3 h-3 rounded-full bg-emerald-500" />
                <span>INVEST</span>
              </div>
              <div className="flex items-center gap-2 text-sm">
                <div className="w-3 h-3 rounded-full bg-amber-500" />
                <span>HOLD</span>
              </div>
              <div className="flex items-center gap-2 text-sm">
                <div className="w-3 h-3 rounded-full bg-red-500" />
                <span>AVOID</span>
              </div>
              <p className="text-xs text-muted-foreground mt-2">
                Circle size = composite score
              </p>
            </CardContent>
          </Card>

          {selected && (
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <MapPin size={16} />
                  {selected.community}
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                <div className="grid grid-cols-2 gap-2 text-sm">
                  <div>
                    <p className="text-muted-foreground">Score</p>
                    <p className="font-bold text-xl">
                      {selected.composite_score.toFixed(0)}/100
                    </p>
                  </div>
                  <div>
                    <p className="text-muted-foreground">Net Yield</p>
                    <p className="font-bold text-xl text-emerald-400">
                      {selected.avg_net_yield.toFixed(1)}%
                    </p>
                  </div>
                  <div>
                    <p className="text-muted-foreground">Avg Price</p>
                    <p className="font-bold">
                      AED {(selected.avg_price / 1000000).toFixed(2)}M
                    </p>
                  </div>
                  <div>
                    <p className="text-muted-foreground">District</p>
                    <p className="font-bold">{selected.district}</p>
                  </div>
                </div>
                <div
                  className="text-center py-2 rounded-lg font-bold"
                  style={{
                    backgroundColor: recColors[selected.recommendation] + "20",
                    color: recColors[selected.recommendation],
                  }}
                >
                  {selected.recommendation}
                </div>
              </CardContent>
            </Card>
          )}

          {!selected && (
            <Card>
              <CardContent className="py-8 text-center text-muted-foreground text-sm">
                Click a community on the map to see details
              </CardContent>
            </Card>
          )}
        </div>
      </div>
    </div>
  );
}
