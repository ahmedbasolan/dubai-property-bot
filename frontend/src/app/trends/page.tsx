"use client";

import { useEffect, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { api, type TrendPoint } from "@/lib/api";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  BarChart,
  Bar,
} from "recharts";
import { TrendingUp, TrendingDown, BarChart3 } from "lucide-react";

export default function TrendsPage() {
  const [trends, setTrends] = useState<Record<string, TrendPoint[]>>({});
  const [basis, setBasis] = useState("");
  const [selected, setSelected] = useState<string>("Dubai Marina");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let stale = false;
    api
      .getTrends()
      .then((data) => {
        if (stale) return;
        setTrends(data.trends);
        setBasis(data.basis ?? "");
        setError(null);
      })
      .catch((err: unknown) => {
        if (!stale) {
          setError(err instanceof Error ? err.message : "Failed to load trends");
        }
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
        <p className="text-sm text-red-400">Could not load trends: {error}</p>
      </div>
    );
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="animate-pulse text-muted-foreground">
          Loading trends...
        </div>
      </div>
    );
  }

  const communities = Object.keys(trends).sort();
  const active = trends[selected] ? selected : communities[0];
  const data = active ? trends[active] : [];

  const latest = data[data.length - 1];
  // Year on year means four quarters back, not the previous quarter.
  const yearAgo = data[data.length - 5];
  const yoyGrowth =
    latest && yearAgo?.avg_price
      ? ((latest.avg_price - yearAgo.avg_price) / yearAgo.avg_price) * 100
      : 0;

  const totalMarketVolume = data.reduce((s, d) => s + (d.transactions ?? 0), 0);

  return (
    <div className="p-6 space-y-6">
      <div>
        <h1 className="text-3xl font-bold tracking-tight">Price Trends</h1>
        <p className="text-muted-foreground mt-1">
          Quarterly price per sqft, anchored to the same average that the
          investment scores use
        </p>
        {basis && (
          <p className="text-xs text-muted-foreground mt-1 max-w-3xl">{basis}</p>
        )}
      </div>

      {communities.length === 0 ? (
        <div className="p-4 rounded-lg border border-border text-sm text-muted-foreground">
          No price history found. Run <code>make setup-db</code> to generate it.
        </div>
      ) : (
        <>
      <Select value={active} onValueChange={(value: string | null) => { if (value) setSelected(value); }}>
        <SelectTrigger className="w-[300px]">
          <SelectValue placeholder="Select community" />
        </SelectTrigger>
        <SelectContent>
          {communities.map((c) => (
            <SelectItem key={c} value={c}>
              {c}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              Current Price / sqft
            </CardTitle>
            <TrendingUp className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-3xl font-bold">
              AED {(latest?.avg_price ?? 0).toLocaleString()}
            </div>
            <div className="flex items-center gap-1 mt-1">
              {yoyGrowth > 0 ? (
                <TrendingUp className="h-4 w-4 text-emerald-400" />
              ) : (
                <TrendingDown className="h-4 w-4 text-red-400" />
              )}
              <span
                className={`text-sm ${
                  yoyGrowth > 0 ? "text-emerald-400" : "text-red-400"
                }`}
              >
                {yoyGrowth > 0 ? "+" : ""}
                {Number.isFinite(yoyGrowth) ? yoyGrowth.toFixed(1) : "0.0"}% YoY
              </span>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              Market Volume (3y)
            </CardTitle>
            <BarChart3 className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-3xl font-bold">{totalMarketVolume.toLocaleString()}</div>
            <p className="text-xs text-muted-foreground mt-1">
              Modelled from stock turnover, not the sampled transactions
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              Price Change
            </CardTitle>
            <TrendingUp className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-3xl font-bold">
              AED{" "}
              {latest && data[0] && latest.avg_price != null && data[0].avg_price != null
                ? (latest.avg_price - data[0].avg_price).toLocaleString()
                : 0}
            </div>
            <p className="text-xs text-muted-foreground mt-1">
              Since {data[0]?.quarter || "N/A"}
            </p>
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Price per sqft Over Time</CardTitle>
        </CardHeader>
        <CardContent>
          <ResponsiveContainer width="100%" height={400}>
            <LineChart data={data}>
              <CartesianGrid strokeDasharray="3 3" stroke="#333" />
              <XAxis dataKey="quarter" stroke="#888" fontSize={12} />
              <YAxis stroke="#888" fontSize={12} />
              <Tooltip
                contentStyle={{
                  backgroundColor: "#1a1a1a",
                  border: "1px solid #333",
                  borderRadius: "8px",
                }}
              />
              <Line
                type="monotone"
                dataKey="avg_price"
                stroke="#10b981"
                strokeWidth={2}
                dot={{ fill: "#10b981", r: 4 }}
                activeDot={{ r: 6 }}
              />
            </LineChart>
          </ResponsiveContainer>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Market Volume (modelled)</CardTitle>
        </CardHeader>
        <CardContent>
          <ResponsiveContainer width="100%" height={300}>
            <BarChart data={data}>
              <CartesianGrid strokeDasharray="3 3" stroke="#333" />
              <XAxis dataKey="quarter" stroke="#888" fontSize={12} />
              <YAxis stroke="#888" fontSize={12} />
              <Tooltip
                contentStyle={{
                  backgroundColor: "#1a1a1a",
                  border: "1px solid #333",
                  borderRadius: "8px",
                }}
              />
              <Bar dataKey="transactions" fill="#3b82f6" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
          <p className="text-xs text-muted-foreground mt-2">
            Derived from existing stock and quarterly turnover, not a count of
            the sampled transactions.
          </p>
        </CardContent>
      </Card>
        </>
      )}
    </div>
  );
}
