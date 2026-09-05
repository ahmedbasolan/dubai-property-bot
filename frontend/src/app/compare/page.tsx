"use client";

import { useEffect, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { api, type Transaction } from "@/lib/api";
import { GitCompare, Plus, X } from "lucide-react";

export default function ComparePage() {
  const [allTransactions, setAllTransactions] = useState<Transaction[]>([]);
  const [selectedIds, setSelectedIds] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.getTransactions().then((data) => {
      setAllTransactions(data.transactions);
      setLoading(false);
    });
  }, []);

  const selected = selectedIds
    .map((id) => allTransactions.find((t) => t.transaction_id === id))
    .filter(Boolean) as Transaction[];

  const addProperty = (id: string) => {
    if (selectedIds.length < 3 && !selectedIds.includes(id)) {
      setSelectedIds([...selectedIds, id]);
    }
  };

  const removeProperty = (id: string) => {
    setSelectedIds(selectedIds.filter((i) => i !== id));
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="animate-pulse text-muted-foreground">
          Loading properties...
        </div>
      </div>
    );
  }

  return (
    <div className="p-6 space-y-6">
      <div>
        <h1 className="text-3xl font-bold tracking-tight">
          Property Comparison
        </h1>
        <p className="text-muted-foreground mt-1">
          Compare up to 3 properties side by side
        </p>
      </div>

      <div className="flex items-center gap-4">
        <Select onValueChange={(value: string | null) => { if (value) addProperty(value); }}>
          <SelectTrigger className="w-[400px]">
            <SelectValue placeholder="Add a property to compare..." />
          </SelectTrigger>
          <SelectContent>
            {allTransactions.map((t) => (
              <SelectItem
                key={t.transaction_id}
                value={t.transaction_id}
                disabled={selectedIds.includes(t.transaction_id)}
              >
                {t.transaction_id} — {t.bedrooms}BR {t.community} — AED{" "}
                {(t.price_aed / 1000000).toFixed(2)}M
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        <span className="text-sm text-muted-foreground">
          {selectedIds.length}/3 selected
        </span>
      </div>

      {selected.length === 0 ? (
        <Card>
          <CardContent className="py-16 text-center">
            <GitCompare className="h-12 w-12 mx-auto text-muted-foreground mb-4" />
            <p className="text-muted-foreground">
              Select properties above to start comparing
            </p>
          </CardContent>
        </Card>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {selected.map((t) => (
            <Card key={t.transaction_id} className="relative">
              <button
                onClick={() => removeProperty(t.transaction_id)}
                className="absolute top-3 right-3 text-muted-foreground hover:text-foreground"
              >
                <X size={16} />
              </button>
              <CardHeader className="pb-3">
                <CardTitle className="text-lg">{t.transaction_id}</CardTitle>
                <p className="text-sm text-muted-foreground">
                  {t.bedrooms === 0
                    ? "Studio"
                    : `${t.bedrooms} Bedroom`}{" "}
                  — {t.community}
                </p>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="space-y-2 text-sm">
                  <div className="flex justify-between p-2 rounded bg-accent/50">
                    <span className="text-muted-foreground">Price</span>
                    <span className="font-bold">
                      AED {(t.price_aed / 1000000).toFixed(2)}M
                    </span>
                  </div>
                  <div className="flex justify-between p-2 rounded bg-accent/50">
                    <span className="text-muted-foreground">Size</span>
                    <span className="font-bold">
                      {t.size_sqft.toLocaleString()} sqft
                    </span>
                  </div>
                  <div className="flex justify-between p-2 rounded bg-accent/50">
                    <span className="text-muted-foreground">Price/sqft</span>
                    <span className="font-bold">
                      AED {t.price_per_sqft.toLocaleString()}
                    </span>
                  </div>
                  <div className="flex justify-between p-2 rounded bg-accent/50">
                    <span className="text-muted-foreground">Net Yield</span>
                    <span className="font-bold text-emerald-400">
                      {t.net_yield_pct?.toFixed(1) ?? "—"}%
                    </span>
                  </div>
                  <div className="flex justify-between p-2 rounded bg-accent/50">
                    <span className="text-muted-foreground">ROI</span>
                    <span className="font-bold text-emerald-400">
                      {t.roi_pct}%
                    </span>
                  </div>
                  <div className="flex justify-between p-2 rounded bg-accent/50">
                    <span className="text-muted-foreground">Floor</span>
                    <span className="font-bold">{t.floor_level}</span>
                  </div>
                  <div className="flex justify-between p-2 rounded bg-accent/50">
                    <span className="text-muted-foreground">View</span>
                    <span className="font-bold">{t.view_type}</span>
                  </div>
                  <div className="flex justify-between p-2 rounded bg-accent/50">
                    <span className="text-muted-foreground">Developer</span>
                    <span className="font-bold">{t.developer}</span>
                  </div>
                  <div className="flex justify-between p-2 rounded bg-accent/50">
                    <span className="text-muted-foreground">Status</span>
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
                  <div className="flex justify-between p-2 rounded bg-accent/50">
                    <span className="text-muted-foreground">
                      Service Charge
                    </span>
                    <span className="font-bold">
                      {t.service_charge_aed_sqft} AED/sqft
                    </span>
                  </div>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
