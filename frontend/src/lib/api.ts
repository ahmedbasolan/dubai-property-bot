const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

async function fetchApi<T>(endpoint: string): Promise<T> {
  const res = await fetch(`${API_BASE}${endpoint}`);
  if (!res.ok) {
    let detail = `API error: ${res.status}`;
    try {
      const body = await res.json();
      if (body?.detail) detail = String(body.detail);
      else if (body?.answer) return body as T; // chat fallback payloads
    } catch {
      /* keep status-only message */
    }
    throw new Error(detail);
  }
  return res.json();
}

export type Grade = "A" | "B" | "C" | "D" | "F";

export type Recommendation = "INVEST" | "HOLD" | "AVOID" | "INSUFFICIENT DATA";

// Source: Dubai Land Department open data (registered apartment sales Jan-Sep
// 2026, Ejari rents). Yield fields are null when a community has fewer than
// 30 rent contracts; such communities have no score.
export interface CommunityScore {
  community: string;
  transaction_count: number; // ready sales
  avg_price_per_sqft: number; // median, ready
  avg_price: number; // median, ready
  avg_roi_pct: number | null; // gross yield
  avg_net_yield_pct: number | null; // after management + vacancy, before service charges
  rent_basis: "new contracts" | "all contracts" | null;
  rent_contracts: number | null;
  price_momentum_pct: number | null; // same-project change Q1 -> Q3
  paired_projects: number | null;
  offplan_sales: number;
  pipeline_ratio: number; // off-plan sales per ready sale
  units_completed_2026: number;
  supply_risk: "LOW" | "MEDIUM" | "HIGH";
  yield_score: Grade | null;
  supply_risk_score: Grade;
  momentum_score: Grade | null;
  liquidity_score: Grade;
  composite_score: number | null;
  recommendation: Recommendation;
}

export interface Transaction {
  transaction_id: string;
  community: string;
  property_type: string;
  bedrooms: number | null; // 0 = studio
  price_aed: number;
  size_sqft: number;
  transaction_date: string;
  price_per_sqft: number;
  roi_pct: number | null; // estimated: community rent per m2 x unit size
  net_yield_pct: number | null;
  estimated_annual_rent: number | null;
  project: string | null;
  developer: string | null;
  handover_status: "Ready" | "Off-Plan" | string;
}

export interface MortgageResult {
  loan_amount: number;
  monthly_payment: number;
  total_interest: number;
  total_acquisition_cost: number;
  dld_transfer_fee: number;
  monthly_service_charges: number;
  down_payment: number;
}

export interface STRResult {
  community: string;
  bedrooms: number;
  avg_daily_rate: number;
  occupancy_rate: number;
  gross_annual_revenue: number;
  net_annual_revenue: number;
  gross_yield: number;
  net_yield_after_fees: number;
  management_fee_rate: number;
  total_fees: number;
  dtcm_license_fee: number;
}

export interface DeveloperScore {
  name: string;
  communities: string[];
  community_count: number;
  transaction_count: number;
  avg_price_per_sqft: number;
  avg_roi_pct: number;
  avg_net_yield_pct: number;
  avg_service_charge: number;
  avg_occupancy_rate: number;
  avg_pipeline_pct: number;
  yield_grade: Grade;
  net_yield_grade: Grade;
  service_charge_grade: Grade;
  supply_grade: Grade;
  occupancy_grade: Grade;
  composite_score: number;
  overall_grade: Grade;
  recommendation: "INVEST" | "HOLD" | "AVOID";
}

export interface TrendPoint {
  quarter: string;
  avg_price: number;
  market_volume: number;
}

export interface MapFeature {
  community: string;
  lat: number;
  lng: number;
  composite_score: number | null;
  recommendation: Recommendation;
  avg_net_yield: number | null;
  avg_price: number;
  avg_price_per_sqft: number;
}

export interface HealthResponse {
  status: string;
  version: string;
  data_source: string;
  default_source: string;
  bayut_configured: boolean;
}

export const api = {
  getHealth: () => fetchApi<HealthResponse>("/api/health"),
  getCommunities: () => fetchApi<{ communities: CommunityScore[] }>("/api/communities"),
  getTransactions: (params?: Record<string, string>, useLive = false) => {
    const allParams = { ...(params || {}) };
    if (useLive) allParams.use_live = "true";
    const qs = Object.keys(allParams).length ? "?" + new URLSearchParams(allParams).toString() : "";
    return fetchApi<{
      transactions: Transaction[];
      total: number;
      source: string;
      limit?: number;
      offset?: number;
    }>(`/api/transactions${qs}`);
  },
  getTransaction: (id: string) => fetchApi<{ transaction: Transaction }>(`/api/transactions/${id}`),
  getMortgage: (params: Record<string, string>) =>
    fetchApi<MortgageResult>(`/api/mortgage?${new URLSearchParams(params)}`),
  getSTR: (params: Record<string, string>) =>
    fetchApi<STRResult>(`/api/str?${new URLSearchParams(params)}`),
  getDevelopers: () =>
    fetchApi<{ developers: DeveloperScore[]; source: string; basis: string }>(
      "/api/developers"
    ),
  getTrends: (community?: string) =>
    fetchApi<{ trends: Record<string, TrendPoint[]>; source: string; basis: string }>(
      `/api/trends${community ? `?community=${community}` : ""}`
    ),
  getTopGainers: () => fetchApi<{ gainers: TrendPoint[] }>("/api/trends/top-gainers"),
  getTopVolume: () => fetchApi<{ volume: TrendPoint[] }>("/api/trends/top-volume"),
  getMapData: () => fetchApi<{ features: MapFeature[] }>("/api/map"),
  // POST, not GET: a key in a query string is written to access logs.
  chat: (q: string, opts?: { provider?: string; apiKey?: string; model?: string }) =>
    fetch(`${API_BASE}/api/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        q,
        provider: opts?.provider,
        api_key: opts?.apiKey,
        model: opts?.model,
      }),
    }).then(async (res) => {
      if (!res.ok) {
        let detail = `API error: ${res.status}`;
        try {
          const body = await res.json();
          if (body?.detail) detail = String(body.detail);
        } catch {
          /* keep status-only message */
        }
        throw new Error(detail);
      }
      return (await res.json()) as {
        answer: string;
        communities: string[];
        transaction_count: number;
      };
    }),
};
