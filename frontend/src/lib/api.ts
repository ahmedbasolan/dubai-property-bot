const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

async function fetchApi<T>(endpoint: string): Promise<T> {
  const res = await fetch(`${API_BASE}${endpoint}`);
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}

export interface CommunityScore {
  community: string;
  district: string;
  composite_score: number;
  recommendation: "INVEST" | "HOLD" | "AVOID";
  avg_net_yield_pct: number;
  avg_roi_pct: number;
  avg_price_per_sqft: number;
  avg_price: number;
  supply_risk: string;
  pipeline_pct_of_stock: number;
  occupancy_rate: number;
  master_developer: string;
  price_score: number;
  yield_score: number;
  net_yield_score: number;
  rank: number;
}

export interface Transaction {
  transaction_id: string;
  community: string;
  property_type: string;
  bedrooms: number;
  price_aed: number;
  size_sqft: number;
  price_per_sqft: number;
  roi_pct: number;
  net_yield_pct: number;
  floor_level: string;
  view_type: string;
  developer: string;
  handover_status: string;
  service_charge_aed_sqft: number;
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
  overall_grade: string;
  on_time_delivery_pct: number;
  quality_rating: string;
  post_handover_appreciation_pct: number;
  service_charge_efficiency: string;
  project_count: number;
  total_units_delivered: number;
  rera_compliance: boolean;
  recommendation: string;
}

export interface TrendPoint {
  quarter: string;
  avg_price: number;
  transactions: number;
}

export interface MapFeature {
  community: string;
  district: string;
  lat: number;
  lng: number;
  composite_score: number;
  recommendation: string;
  avg_net_yield: number;
  avg_price: number;
}

export interface HealthResponse {
  status: string;
  version: string;
  data_source: string;
  bayut_configured: boolean;
}

export const api = {
  getHealth: () => fetchApi<HealthResponse>("/api/health"),
  getCommunities: () => fetchApi<{ communities: CommunityScore[] }>("/api/communities"),
  getTransactions: (params?: Record<string, string>, useLive = false) => {
    const allParams = { ...(params || {}) };
    if (useLive) allParams.use_live = "true";
    const qs = Object.keys(allParams).length ? "?" + new URLSearchParams(allParams).toString() : "";
    return fetchApi<{ transactions: Transaction[]; source: string }>(`/api/transactions${qs}`);
  },
  getTransaction: (id: string) => fetchApi<{ transaction: Transaction }>(`/api/transactions/${id}`),
  getMortgage: (params: Record<string, string>) =>
    fetchApi<MortgageResult>(`/api/mortgage?${new URLSearchParams(params)}`),
  getSTR: (params: Record<string, string>) =>
    fetchApi<STRResult>(`/api/str?${new URLSearchParams(params)}`),
  getDevelopers: () => fetchApi<{ developers: DeveloperScore[] }>("/api/developers"),
  getTrends: (community?: string) =>
    fetchApi<{ trends: Record<string, TrendPoint[]> }>(
      `/api/trends${community ? `?community=${community}` : ""}`
    ),
  getTopGainers: () => fetchApi<{ gainers: TrendPoint[] }>("/api/trends/top-gainers"),
  getTopVolume: () => fetchApi<{ volume: TrendPoint[] }>("/api/trends/top-volume"),
  getMapData: () => fetchApi<{ features: MapFeature[] }>("/api/map"),
};
