"use client";

import { useEffect, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { api, type MortgageResult, type STRResult } from "@/lib/api";
import { Calculator, TrendingUp, DollarSign, Home } from "lucide-react";

export default function CalculatorPage() {
  const [price, setPrice] = useState("1500000");
  const [downPayment, setDownPayment] = useState("20");
  const [rate, setRate] = useState("4.5");
  const [tenure, setTenure] = useState("25");
  const [mortgage, setMortgage] = useState<MortgageResult | null>(null);
  const [loading, setLoading] = useState(false);

  const calculate = () => {
    setLoading(true);
    api
      .getMortgage({
        property_price: price,
        down_payment_pct: downPayment,
        interest_rate: rate,
        tenure_years: tenure,
        size_sqft: "800",
        service_charge_sqft: "15",
      })
      .then((data) => {
        setMortgage(data);
        setLoading(false);
      });
  };

  useEffect(() => {
    calculate();
  }, []);

  return (
    <div className="p-6 space-y-6">
      <div>
        <h1 className="text-3xl font-bold tracking-tight">
          Mortgage Calculator
        </h1>
        <p className="text-muted-foreground mt-1">
          UAE-specific mortgage calculation with DLD fees
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Calculator size={18} />
              Parameters
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-2">
              <Label>Property Price (AED)</Label>
              <Input
                type="number"
                value={price}
                onChange={(e) => setPrice(e.target.value)}
                onBlur={calculate}
              />
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label>Down Payment %</Label>
                <Input
                  type="number"
                  value={downPayment}
                  onChange={(e) => setDownPayment(e.target.value)}
                  onBlur={calculate}
                />
              </div>
              <div className="space-y-2">
                <Label>Interest Rate %</Label>
                <Input
                  type="number"
                  value={rate}
                  onChange={(e) => setRate(e.target.value)}
                  onBlur={calculate}
                />
              </div>
            </div>
            <div className="space-y-2">
              <Label>Tenure (years)</Label>
              <Input
                type="number"
                value={tenure}
                onChange={(e) => setTenure(e.target.value)}
                onBlur={calculate}
              />
            </div>
            <button
              onClick={calculate}
              className="w-full bg-primary text-primary-foreground py-2 rounded-lg font-medium hover:bg-primary/90 transition-colors"
            >
              Calculate
            </button>
          </CardContent>
        </Card>

        {mortgage && (
          <div className="space-y-4">
            <Card>
              <CardHeader className="flex flex-row items-center justify-between pb-2">
                <CardTitle className="text-sm font-medium text-muted-foreground">
                  Monthly Payment
                </CardTitle>
                <DollarSign className="h-4 w-4 text-muted-foreground" />
              </CardHeader>
              <CardContent>
                <div className="text-4xl font-bold text-emerald-400">
                  AED {mortgage.monthly_payment.toLocaleString()}
                </div>
                <p className="text-xs text-muted-foreground mt-1">
                  Loan: AED {mortgage.loan_amount.toLocaleString()}
                </p>
              </CardContent>
            </Card>

            <div className="grid grid-cols-2 gap-4">
              <Card>
                <CardHeader className="flex flex-row items-center justify-between pb-2">
                  <CardTitle className="text-sm font-medium text-muted-foreground">
                    DLD Transfer Fee
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="text-2xl font-bold">
                    AED {mortgage.dld_transfer_fee.toLocaleString()}
                  </div>
                </CardContent>
              </Card>
              <Card>
                <CardHeader className="flex flex-row items-center justify-between pb-2">
                  <CardTitle className="text-sm font-medium text-muted-foreground">
                    Total Interest
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="text-2xl font-bold">
                    AED {mortgage.total_interest.toLocaleString()}
                  </div>
                </CardContent>
              </Card>
            </div>

            <Card>
              <CardHeader className="flex flex-row items-center justify-between pb-2">
                <CardTitle className="text-sm font-medium text-muted-foreground">
                  Total Acquisition Cost
                </CardTitle>
                <Home className="h-4 w-4 text-muted-foreground" />
              </CardHeader>
              <CardContent>
                <div className="text-3xl font-bold">
                  AED {mortgage.total_acquisition_cost.toLocaleString()}
                </div>
                <p className="text-xs text-muted-foreground mt-1">
                  Includes DLD 4% + Agency 2%
                </p>
              </CardContent>
            </Card>

            <div className="grid grid-cols-2 gap-4">
              <Card>
                <CardHeader className="flex flex-row items-center justify-between pb-2">
                  <CardTitle className="text-sm font-medium text-muted-foreground">
                    Down Payment
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="text-2xl font-bold">
                    AED {(mortgage.down_payment ?? 0).toLocaleString()}
                  </div>
                </CardContent>
              </Card>
              <Card>
                <CardHeader className="flex flex-row items-center justify-between pb-2">
                  <CardTitle className="text-sm font-medium text-muted-foreground">
                    Monthly Service Charges
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="text-2xl font-bold">
                    AED {(mortgage.monthly_service_charges ?? 0).toLocaleString()}
                  </div>
                </CardContent>
              </Card>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
