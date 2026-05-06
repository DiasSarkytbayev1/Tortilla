import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import { Label } from "@/components/ui/label";
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { api, ApiError, unwrap } from "@/api/client";
import type { PeakHourCell } from "@/api/schemas";
import { useFilters, filtersToQuery } from "@/hooks/useFilters";
import { ChartShell } from "@/components/ChartShell";
import { DOWHourHeatmap } from "@/components/DOWHourHeatmap";
import { formatCurrency, formatInteger } from "@/lib/format";

type Metric = "bills" | "revenue";

export default function PeakHours() {
  const f = useFilters();
  const [metric, setMetric] = useState<Metric>("bills");

  const q = useQuery<PeakHourCell[], ApiError>({
    queryKey: ["peak-hours", f.from, f.to, f.restaurants],
    queryFn: async () =>
      unwrap(await api.GET("/api/peak-hours", { params: { query: filtersToQuery(f) } })) as PeakHourCell[],
  });

  const data = q.data ?? [];

  // Hourly aggregation across all DOWs.
  const hourly = useMemo(() => {
    const out: Record<number, { hour: number; bills: number; revenue: number }> = {};
    for (let h = 0; h < 24; h++) out[h] = { hour: h, bills: 0, revenue: 0 };
    for (const c of data) {
      out[c.hour].bills += c.bills;
      out[c.hour].revenue += c.revenue;
    }
    return Object.values(out);
  }, [data]);

  return (
    <Card>
      <CardHeader className="flex-row items-center justify-between gap-4">
        <CardTitle>Peak hours</CardTitle>
        <RadioGroup value={metric} onValueChange={(v) => setMetric(v as Metric)} className="flex items-center gap-3">
          <div className="flex items-center gap-1.5">
            <RadioGroupItem value="bills" id="ph-bills" />
            <Label htmlFor="ph-bills" className="text-sm font-normal">Bills</Label>
          </div>
          <div className="flex items-center gap-1.5">
            <RadioGroupItem value="revenue" id="ph-rev" />
            <Label htmlFor="ph-rev" className="text-sm font-normal">Revenue</Label>
          </div>
        </RadioGroup>
      </CardHeader>
      <CardContent>
        <Tabs defaultValue="heatmap" className="w-full">
          <TabsList className="mb-4">
            <TabsTrigger value="heatmap">Heatmap</TabsTrigger>
            <TabsTrigger value="hourly">Hourly bars</TabsTrigger>
          </TabsList>
          <TabsContent value="heatmap">
            <ChartShell
              isLoading={q.isLoading}
              isError={q.isError}
              isEmpty={!q.isLoading && !q.isError && data.length === 0}
              onRetry={() => q.refetch()}
              errorMessage={q.error?.detail}
              height={260}
            >
              <DOWHourHeatmap data={data} metric={metric} />
            </ChartShell>
          </TabsContent>
          <TabsContent value="hourly">
            <ChartShell
              isLoading={q.isLoading}
              isError={q.isError}
              isEmpty={!q.isLoading && !q.isError && data.length === 0}
              onRetry={() => q.refetch()}
              errorMessage={q.error?.detail}
              height={300}
            >
              <ResponsiveContainer width="100%" height={300}>
                <BarChart data={hourly} margin={{ top: 8, right: 16, bottom: 0, left: 8 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" />
                  <XAxis dataKey="hour" stroke="var(--color-muted-foreground)" fontSize={12} tickFormatter={(v) => `${String(v).padStart(2, "0")}:00`} />
                  <YAxis
                    stroke="var(--color-muted-foreground)"
                    fontSize={12}
                    tickFormatter={(v) => (metric === "bills" ? formatInteger(v as number) : formatCurrency(v as number))}
                    width={80}
                  />
                  <Tooltip
                    contentStyle={{
                      background: "var(--color-popover)",
                      border: "1px solid var(--color-border)",
                      borderRadius: 8,
                      color: "var(--color-popover-foreground)",
                    }}
                    formatter={(value: unknown) => (metric === "bills" ? formatInteger(Number(value)) : formatCurrency(Number(value)))}
                    labelFormatter={(v) => `${String(v).padStart(2, "0")}:00`}
                  />
                  <Bar dataKey={metric} fill="var(--color-chart-1)" isAnimationActive={false} />
                </BarChart>
              </ResponsiveContainer>
            </ChartShell>
          </TabsContent>
        </Tabs>
      </CardContent>
    </Card>
  );
}
