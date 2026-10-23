"use client";

import { useEffect, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { api, type Transaction } from "@/lib/api";
import { useDataSource } from "@/components/data-source-provider";
import { Search, Bed, Radio, Calendar } from "lucide-react";

const PAGE_SIZE = 60;

function getCommunityName(community: unknown): string {
  if (typeof community === "string") return community;
  if (community && typeof community === "object") {
    const c = community as Record<string, unknown>;
    return (c.name || c.name_l1 || c.name_l2 || c.name_l3) as string || "Unknown";
  }
  return "Unknown";
}

export default function PropertiesPage() {
  const [transactions, setTransactions] = useState<Transaction[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [community, setCommunity] = useState<string>("all");
  const [bedrooms, setBedrooms] = useState<string>("all");
  const [sortBy, setSortBy] = useState<string>("latest");
  const { useLive } = useDataSource();
  const [dataSource, setDataSource] = useState("dld");
  // The page number belongs to one set of filters: changing a filter starts
  // again at page 0 without resetting state inside an effect.
  const queryKey = `${useLive}|${community}|${bedrooms}`;
  const [pageState, setPageState] = useState({ key: queryKey, n: 0 });
  const page = pageState.key === queryKey ? pageState.n : 0;
  const [communityOptions, setCommunityOptions] = useState<string[]>([]);

  // The full list of communities, not just those in the loaded page of sales.
  useEffect(() => {
    api
      .getCommunities()
      .then((data) => setCommunityOptions(data.communities.map((c) => c.community).sort()))
      .catch(() => setCommunityOptions([]));
  }, []);

  useEffect(() => {
    let stale = false;
    const params: Record<string, string> = {
      limit: String(PAGE_SIZE),
      offset: String(page * PAGE_SIZE),
    };
    if (community !== "all") params.community = community;
    if (bedrooms !== "all") params.bedrooms = bedrooms;

    api
      .getTransactions(params, useLive)
      .then((data) => {
        if (stale) return;
        setTransactions((prev) => (page === 0 ? data.transactions : [...prev, ...data.transactions]));
        setTotal(data.total ?? data.transactions.length);
        setDataSource(data.source);
        setError(null);
      })
      .catch((err: unknown) => {
        if (stale) return;
        setTransactions([]);
        setError(err instanceof Error ? err.message : "Failed to load properties");
      })
      .finally(() => {
        if (!stale) setLoading(false);
      });
    return () => {
      stale = true;
    };
  }, [useLive, community, bedrooms, page]);

  let filtered = transactions;

  if (search) {
    const q = search.toLowerCase();
    filtered = filtered.filter(
      (t) =>
        getCommunityName(t.community).toLowerCase().includes(q) ||
        t.transaction_id.toLowerCase().includes(q) ||
        (typeof t.project === "string" && t.project.toLowerCase().includes(q))
    );
  }

  if (community !== "all") {
    filtered = filtered.filter((t) => getCommunityName(t.community) === community);
  }

  if (bedrooms !== "all") {
    filtered = filtered.filter(
      (t) => t.bedrooms === parseInt(bedrooms, 10)
    );
  }

  if (sortBy === "latest") {
    filtered = [...filtered].sort((a, b) => b.transaction_date.localeCompare(a.transaction_date));
  } else if (sortBy === "yield") {
    filtered = [...filtered].sort(
      (a, b) => (b.net_yield_pct ?? 0) - (a.net_yield_pct ?? 0)
    );
  } else if (sortBy === "price") {
    filtered = [...filtered].sort(
      (a, b) => (a.price_aed ?? 0) - (b.price_aed ?? 0)
    );
  } else if (sortBy === "sqft") {
    filtered = [...filtered].sort(
      (a, b) => (b.size_sqft ?? 0) - (a.size_sqft ?? 0)
    );
  }

  const communities = communityOptions.length
    ? communityOptions
    : [...new Set(transactions.map((t) => getCommunityName(t.community)))].sort();

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="flex flex-col items-center gap-4">
          <div className="relative w-10 h-10">
            <div className="absolute inset-0 rounded-full border-2 border-muted" />
            <div className="absolute inset-0 rounded-full border-2 border-primary border-t-transparent animate-spin" />
          </div>
          <span className="text-sm text-muted-foreground animate-fade-in">Loading properties...</span>
        </div>
      </div>
    );
  }

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between animate-fade-in">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Properties</h1>
          <p className="text-muted-foreground mt-1">
            Showing {filtered.length.toLocaleString()} of {total.toLocaleString()} registered sales
            {search && " (search applies to loaded sales)"}
          </p>
        </div>
        <div className="flex items-center gap-2 text-xs">
          <Radio size={14} className={dataSource === "bayut" ? "text-emerald-400" : "text-muted-foreground"} />
          <span className={dataSource === "bayut" ? "text-emerald-400" : "text-muted-foreground"}>
            {dataSource === "bayut" ? "Live listings (Bayut)" : "DLD registered sales, Jan–Sep 2026"}
          </span>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <div className="relative">
          <Search className="absolute left-3 top-3 h-4 w-4 text-muted-foreground" />
          <Input
            placeholder="Search community, ID, project..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="pl-9"
          />
        </div>

        <Select value={community} onValueChange={(value: string | null) => setCommunity(value ?? "all")}>
          <SelectTrigger>
            <SelectValue placeholder="Community" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All Communities</SelectItem>
            {communities.map((c) => (
              <SelectItem key={c} value={c}>
                {c}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>

        <Select value={bedrooms} onValueChange={(value: string | null) => setBedrooms(value ?? "all")}>
          <SelectTrigger>
            <SelectValue placeholder="Bedrooms" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All Bedrooms</SelectItem>
            <SelectItem value="0">Studio</SelectItem>
            <SelectItem value="1">1 BR</SelectItem>
            <SelectItem value="2">2 BR</SelectItem>
            <SelectItem value="3">3 BR</SelectItem>
          </SelectContent>
        </Select>

        <Select value={sortBy} onValueChange={(value: string | null) => setSortBy(value ?? "latest")}>
          <SelectTrigger>
            <SelectValue placeholder="Sort by" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="latest">Latest</SelectItem>
            <SelectItem value="yield">Highest Est. Yield</SelectItem>
            <SelectItem value="price">Lowest Price</SelectItem>
            <SelectItem value="sqft">Largest Size</SelectItem>
          </SelectContent>
        </Select>
      </div>

      {error && (
        <div className="p-3 rounded-lg bg-red-500/10 border border-red-500/20 text-sm text-red-400">
          Could not load properties: {error}
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 stagger-children">
        {filtered.map((t) => (
          <Card key={t.transaction_id} className="card-hover animate-fade-in-up">
            <CardHeader className="pb-3">
              <div className="flex items-start justify-between">
                <div>
                  <CardTitle className="text-lg">
                    {t.bedrooms === null
                      ? "Apartment"
                      : t.bedrooms === 0
                      ? "Studio"
                      : `${t.bedrooms} Bedroom`}
                  </CardTitle>
                  <p className="text-sm text-muted-foreground">
                    {getCommunityName(t.community)}
                  </p>
                </div>
                <Badge
                  variant={
                    t.handover_status?.toUpperCase() === "READY"
                      ? "default"
                      : "secondary"
                  }
                >
                  {t.handover_status ?? "—"}
                </Badge>
              </div>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid grid-cols-2 gap-3 text-sm">
                <div>
                  <p className="text-muted-foreground">Price</p>
                  <p className="font-bold text-lg">
                    AED {((t.price_aed ?? 0) / 1000000).toFixed(2)}M
                  </p>
                </div>
                <div>
                  <p className="text-muted-foreground">Size</p>
                  <p className="font-bold text-lg">
                    {t.size_sqft != null ? t.size_sqft.toLocaleString() : "—"} sqft
                  </p>
                </div>
                <div>
                  <p className="text-muted-foreground">Est. Gross Yield</p>
                  <p className="font-bold text-lg text-emerald-400">
                    {t.roi_pct != null ? `${t.roi_pct.toFixed(1)}%` : "n/a"}
                  </p>
                </div>
                <div>
                  <p className="text-muted-foreground">AED / sqft</p>
                  <p className="font-bold text-lg">
                    {t.price_per_sqft != null ? Math.round(t.price_per_sqft).toLocaleString() : "—"}
                  </p>
                </div>
              </div>

              <div className="flex items-center gap-4 text-xs text-muted-foreground pt-2 border-t">
                <span className="flex items-center gap-1">
                  <Bed size={12} />
                  {t.bedrooms === null ? "—" : t.bedrooms === 0 ? "Studio" : `${t.bedrooms}BR`}
                </span>
                <span className="flex items-center gap-1">
                  <Calendar size={12} />
                  {t.transaction_date}
                </span>
                <span className="truncate">{t.project ?? "—"}</span>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>

      {transactions.length < total && !useLive && (
        <div className="flex justify-center">
          <button
            onClick={() => setPageState({ key: queryKey, n: page + 1 })}
            className="px-4 py-2 text-sm rounded-lg border hover:bg-accent"
          >
            Load {Math.min(PAGE_SIZE, total - transactions.length)} more
          </button>
        </div>
      )}
      <p className="text-xs text-muted-foreground">
        Source: Dubai Land Department open data. Estimated yields apply the median new Ejari rent
        per m² in the unit&apos;s project (or its community) to its size; n/a where there are too
        few rent contracts.
      </p>
    </div>
  );
}
