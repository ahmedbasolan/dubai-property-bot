"""UAE-specific financial calculators for property investment."""

from dataclasses import dataclass
from typing import Optional


@dataclass
class MortgageResult:
    """Monthly mortgage payment and cost breakdown."""
    property_price: int
    down_payment_pct: float
    down_payment: int
    loan_amount: int
    interest_rate: float
    tenure_years: int
    monthly_payment: float
    total_interest: float
    total_cost: int
    # UAE-specific fees
    dld_transfer_fee: int
    agency_fee: int
    mortgage_reg_fee: int
    admin_fee: int
    total_acquisition_cost: int
    # Monthly breakdown
    monthly_service_charges: float


@dataclass
class STRResult:
    """Short-term rental revenue estimate."""
    community: str
    bedrooms: int
    property_price: int
    avg_daily_rate: float
    occupancy_rate: float
    annual_revenue: float
    gross_yield: float
    # Costs
    dtcm_license: float
    management_fee_pct: float
    management_fee: float
    annual_service_charges: float
    net_revenue: float
    net_yield: float
    # Comparison
    long_term_monthly_rent: float
    long_term_annual: float
    str_premium_pct: float


# --- UAE Mortgage Constants ---
UAE_MORTGAGE = {
    "resident_ltv_first": 0.80,  # 80% LTV for first property <AED 5M
    "resident_ltv_other": 0.70,  # 70% for subsequent properties
    "non_resident_ltv": 0.60,  # 60% for non-residents
    "max_tenure": 25,  # years
    "dld_transfer_pct": 0.04,  # 4% of property price
    "admin_fee": 580,  # AED
    "mortgage_reg_fee": 290,  # AED (per 100K of loan)
    "agency_fee_pct": 0.02,  # 2%
    # Bank rates (indicative, varies by bank)
    "fixed_rates": {
        2: 3.99,
        3: 4.19,
        5: 4.49,
    },
    "variable_rate": 4.99,
}


# --- STR Constants by Community ---
# Based on AirDNA and market data for Dubai
STR_DATA = {
    "Downtown Dubai": {
        "studio": {"adr": 450, "occ": 0.78, "ltm_rent": 7500},
        "1br": {"adr": 650, "occ": 0.75, "ltm_rent": 10000},
        "2br": {"adr": 950, "occ": 0.72, "ltm_rent": 14000},
        "3br": {"adr": 1400, "occ": 0.68, "ltm_rent": 20000},
    },
    "Dubai Marina": {
        "studio": {"adr": 380, "occ": 0.75, "ltm_rent": 6500},
        "1br": {"adr": 550, "occ": 0.73, "ltm_rent": 8500},
        "2br": {"adr": 800, "occ": 0.70, "ltm_rent": 12000},
        "3br": {"adr": 1100, "occ": 0.65, "ltm_rent": 16000},
    },
    "Palm Jumeirah": {
        "studio": {"adr": 500, "occ": 0.70, "ltm_rent": 8000},
        "1br": {"adr": 750, "occ": 0.68, "ltm_rent": 12000},
        "2br": {"adr": 1200, "occ": 0.65, "ltm_rent": 18000},
        "3br": {"adr": 1800, "occ": 0.62, "ltm_rent": 25000},
    },
    "JVC (Jumeirah Village Circle)": {
        "studio": {"adr": 220, "occ": 0.72, "ltm_rent": 4000},
        "1br": {"adr": 320, "occ": 0.70, "ltm_rent": 5500},
        "2br": {"adr": 480, "occ": 0.67, "ltm_rent": 7500},
        "3br": {"adr": 650, "occ": 0.63, "ltm_rent": 9500},
    },
    "Business Bay": {
        "studio": {"adr": 350, "occ": 0.74, "ltm_rent": 6000},
        "1br": {"adr": 500, "occ": 0.72, "ltm_rent": 8000},
        "2br": {"adr": 720, "occ": 0.69, "ltm_rent": 11000},
        "3br": {"adr": 1000, "occ": 0.65, "ltm_rent": 15000},
    },
    "Dubai Hills Estate": {
        "studio": {"adr": 280, "occ": 0.68, "ltm_rent": 5000},
        "1br": {"adr": 400, "occ": 0.66, "ltm_rent": 7000},
        "2br": {"adr": 600, "occ": 0.63, "ltm_rent": 10000},
        "3br": {"adr": 850, "occ": 0.60, "ltm_rent": 14000},
    },
    "Arabian Ranches": {
        "studio": {"adr": 0, "occ": 0, "ltm_rent": 0},  # Villas only
        "1br": {"adr": 0, "occ": 0, "ltm_rent": 0},
        "2br": {"adr": 0, "occ": 0, "ltm_rent": 0},
        "3br": {"adr": 700, "occ": 0.60, "ltm_rent": 12000},
        "4br": {"adr": 1000, "occ": 0.58, "ltm_rent": 16000},
    },
    "Deira": {
        "studio": {"adr": 180, "occ": 0.70, "ltm_rent": 3500},
        "1br": {"adr": 260, "occ": 0.68, "ltm_rent": 5000},
        "2br": {"adr": 380, "occ": 0.65, "ltm_rent": 7000},
    },
    "International City": {
        "studio": {"adr": 150, "occ": 0.68, "ltm_rent": 3000},
        "1br": {"adr": 220, "occ": 0.66, "ltm_rent": 4200},
        "2br": {"adr": 320, "occ": 0.63, "ltm_rent": 5800},
    },
    "Discovery Gardens": {
        "studio": {"adr": 200, "occ": 0.70, "ltm_rent": 3800},
        "1br": {"adr": 300, "occ": 0.68, "ltm_rent": 5500},
        "2br": {"adr": 430, "occ": 0.65, "ltm_rent": 7500},
    },
    "JLT (Jumeirah Lake Towers)": {
        "studio": {"adr": 280, "occ": 0.72, "ltm_rent": 5000},
        "1br": {"adr": 400, "occ": 0.70, "ltm_rent": 7000},
        "2br": {"adr": 580, "occ": 0.67, "ltm_rent": 10000},
    },
    "Bluewaters Island": {
        "studio": {"adr": 0, "occ": 0, "ltm_rent": 0},
        "1br": {"adr": 600, "occ": 0.72, "ltm_rent": 10000},
        "2br": {"adr": 900, "occ": 0.70, "ltm_rent": 15000},
        "3br": {"adr": 1300, "occ": 0.67, "ltm_rent": 22000},
    },
}


def calculate_mortgage(
    property_price: int,
    down_payment_pct: float = 0.20,
    interest_rate: float = 4.5,
    tenure_years: int = 25,
    service_charge_sqft: float = 15.0,
    size_sqft: int = 800,
    is_resident: bool = True,
    is_first_property: bool = True,
) -> MortgageResult:
    """Calculate UAE mortgage costs and total acquisition cost."""
    # Determine max LTV
    if is_resident:
        ltv = UAE_MORTGAGE["resident_ltv_first"] if is_first_property else UAE_MORTGAGE["resident_ltv_other"]
    else:
        ltv = UAE_MORTGAGE["non_resident_ltv"]

    # Clamp down payment to minimum
    min_down = max(0, 1 - ltv)
    down_payment_pct = max(down_payment_pct, min_down)

    down_payment = int(property_price * down_payment_pct)
    loan_amount = property_price - down_payment

    # Monthly payment (amortization formula)
    monthly_rate = interest_rate / 100 / 12
    n_payments = tenure_years * 12
    if monthly_rate > 0:
        monthly_payment = loan_amount * (monthly_rate * (1 + monthly_rate) ** n_payments) / (
            (1 + monthly_rate) ** n_payments - 1
        )
    else:
        monthly_payment = loan_amount / n_payments

    total_interest = (monthly_payment * n_payments) - loan_amount

    # UAE-specific fees
    dld_transfer_fee = int(property_price * UAE_MORTGAGE["dld_transfer_pct"]) + UAE_MORTGAGE["admin_fee"]
    agency_fee = int(property_price * UAE_MORTGAGE["agency_fee_pct"])
    mortgage_reg_fee = int(loan_amount / 100000) * UAE_MORTGAGE["mortgage_reg_fee"]
    admin_fee = UAE_MORTGAGE["admin_fee"]

    total_acquisition_cost = property_price + dld_transfer_fee + agency_fee + mortgage_reg_fee
    monthly_service_charges = size_sqft * service_charge_sqft / 12

    return MortgageResult(
        property_price=property_price,
        down_payment_pct=round(down_payment_pct * 100, 1),
        down_payment=down_payment,
        loan_amount=loan_amount,
        interest_rate=interest_rate,
        tenure_years=tenure_years,
        monthly_payment=round(monthly_payment),
        total_interest=int(total_interest),
        total_cost=int(down_payment + total_interest),
        dld_transfer_fee=dld_transfer_fee,
        agency_fee=agency_fee,
        mortgage_reg_fee=mortgage_reg_fee,
        admin_fee=admin_fee,
        total_acquisition_cost=total_acquisition_cost,
        monthly_service_charges=round(monthly_service_charges),
    )


def calculate_str(
    community: str,
    bedrooms: int,
    property_price: int,
    size_sqft: int,
    service_charge_sqft: float = 15.0,
    management_fee_pct: float = 0.20,
    dtcm_license: float = 2000.0,
) -> Optional[STRResult]:
    """Estimate short-term rental returns for a property."""
    # Get STR data for community
    comm_data = STR_DATA.get(community)
    if not comm_data:
        return None

    # Match bedroom count
    br_key = f"{bedrooms}br" if bedrooms > 0 else "studio"
    if bedrooms >= 4:
        br_key = "3br"  # Use 3BR data for 4BR+

    unit_data = comm_data.get(br_key)
    if not unit_data or unit_data["adr"] == 0:
        return None

    adr = unit_data["adr"]
    occ = unit_data["occ"]
    ltm_monthly = unit_data["ltm_rent"]

    # Revenue calculation
    annual_revenue = adr * 365 * occ

    # Costs
    management_fee = annual_revenue * management_fee_pct
    annual_sc = size_sqft * service_charge_sqft

    net_revenue = annual_revenue - management_fee - dtcm_license - annual_sc
    gross_yield = annual_revenue / property_price * 100
    net_yield = net_revenue / property_price * 100

    # Long-term comparison
    ltm_annual = ltm_monthly * 12
    str_premium = ((annual_revenue - ltm_annual) / ltm_annual * 100) if ltm_annual > 0 else 0

    return STRResult(
        community=community,
        bedrooms=bedrooms,
        property_price=property_price,
        avg_daily_rate=adr,
        occupancy_rate=occ,
        annual_revenue=round(annual_revenue),
        gross_yield=round(gross_yield, 2),
        dtcm_license=dtcm_license,
        management_fee_pct=management_fee_pct,
        management_fee=round(management_fee),
        annual_service_charges=round(annual_sc),
        net_revenue=round(net_revenue),
        net_yield=round(net_yield, 2),
        long_term_monthly_rent=ltm_monthly,
        long_term_annual=ltm_annual,
        str_premium_pct=round(str_premium, 1),
    )
