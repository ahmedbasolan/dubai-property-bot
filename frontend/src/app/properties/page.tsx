"use client";

import { useEffect, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { api, type Transaction } from "@/lib/api";
import { useDataSource } from "@/components/data-source-provider";
import { Search, Bed, Bath, Radio } from "lucide-react";

export default function PropertiesPage() {
  const [transactions, setTransactions] = useState<Transaction[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [community, setCommunity] = useState<string>("all");
  const [bedrooms, setBedrooms] = useState<string>("all");
  const [sortBy, setSortBy] = useState<string>("yield");
  const { useLive } = useDataSource();
  const [dataSource, setDataSource] = useState("mock");

  useEffect(() => {
    setLoading(true);
    const params: Record<string, string> = {};
    if (community !== "all") params.community = community;
    if (bedrooms !== "all") params.bedrooms = bedrooms;

    api.getTransactions(params, useLive).then((data) => {
      setTransactions(data.transactions);
      setDataSource(data.source);
      setLoading(false);
    });
  }, [useLive, community, bedrooms]);

  let filtered = transactions;

  if (search) {
    const q = search.toLowerCase();
    filtered = filtered.filter(
      (t) =>
        t.community.toLowerCase().includes(q) ||
        t.transaction_id.toLowerCase().includes(q) ||
        t.developer.toLowerCase().includes(q)
    );
  }

  if (community !== "all") {
    filtered = filtered.filter((t) => t.community === community);
  }

  if (bedrooms !== "all") {
    filtered = filtered.filter(
      (t) => t.bedrooms === parseInt(bedrooms)
    );
  }

  if (sortBy === "yield") {
    filtered = [...filtered].sort(
      (a, b) => b.net_yield_pct - a.net_yield_pct
    );
  } else if (sortBy === "price") {
    filtered = [...filtered].sort((a, b) => a.price_aed - b.price_aed);
  } else if (sortBy === "sqft") {
    filtered = [...filtered].sort(
      (a, b) => b.size_sqft - a.size_sqft
    );
  }

  const communities = [...new Set(transactions.map((t) => t.community))].sort();

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
            {filtered.length} properties found
          </p>
        </div>
        <div className="flex items-center gap-2 text-xs">
          <Radio size={14} className={dataSource === "bayut" ? "text-emerald-400" : "text-muted-foreground"} />
          <span className={dataSource === "bayut" ? "text-emerald-400" : "text-muted-foreground"}>
            {dataSource === "bayut" ? "Live DLD Data" : "Mock Data"}
          </span>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <div className="relative">
          <Search className="absolute left-3 top-3 h-4 w-4 text-muted-foreground" />
          <Input
            placeholder="Search community, ID, developer..."
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

        <Select value={sortBy} onValueChange={(value: string | null) => setSortBy(value ?? "yield")}>
          <SelectTrigger>
            <SelectValue placeholder="Sort by" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="yield">Highest Yield</SelectItem>
            <SelectItem value="price">Lowest Price</SelectItem>
            <SelectItem value="sqft">Largest Size</SelectItem>
          </SelectContent>
        </Select>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 stagger-children">
        {filtered.map((t) => (
          <Card key={t.transaction_id} className="card-hover animate-fade-in-up">
            <CardHeader className="pb-3">
              <div className="flex items-start justify-between">
                <div>
                  <CardTitle className="text-lg">
                    {t.bedrooms === 0
                      ? "Studio"
                      : `${t.bedrooms} Bedroom`}
                  </CardTitle>
                  <p className="text-sm text-muted-foreground">
                    {t.community}
                  </p>
                </div>
                <Badge
                  variant={
                    t.handover_status === "READY"
                      ? "default"
                      : "secondary"
                  }
                >
                  {t.handover_status}
                </Badge>
              </div>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid grid-cols-2 gap-3 text-sm">
                <div>
                  <p className="text-muted-foreground">Price</p>
                  <p className="font-bold text-lg">
                    AED {(t.price_aed / 1000000).toFixed(2)}M
                  </p>
                </div>
                <div>
                  <p className="text-muted-foreground">Size</p>
                  <p className="font-bold text-lg">
                    {t.size_sqft.toLocaleString()} sqft
                  </p>
                </div>
                <div>
                  <p className="text-muted-foreground">Net Yield</p>
                  <p className="font-bold text-lg text-emerald-400">
                    {t.net_yield_pct?.toFixed(1) ?? "—"}%
                  </p>
                </div>
                <div>
                  <p className="text-muted-foreground">ROI</p>
                  <p className="font-bold text-lg text-emerald-400">
                    {t.roi_pct ?? "—"}%
                  </p>
                </div>
              </div>

              <div className="flex items-center gap-4 text-xs text-muted-foreground pt-2 border-t">
                <span className="flex items-center gap-1">
                  <Bed size={12} />
                  {t.bedrooms}BR
                </span>
                <span>Floor {t.floor_level}</span>
                <span>{t.view_type} view</span>
                <span>{t.developer}</span>
              </div>

              <div className="text-xs text-muted-foreground">
                <span>
                  AED {t.price_per_sqft.toLocaleString()}/sqft •{" "}
                  {t.service_charge_aed_sqft} AED/sqft service
                </span>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  );
}
