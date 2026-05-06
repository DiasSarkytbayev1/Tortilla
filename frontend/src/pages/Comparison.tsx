import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { AlertCircle } from "lucide-react";
import { api, ApiError, unwrap } from "@/api/client";
import type { ComparisonRow, TrendPoint } from "@/api/schemas";
import { useFilters, filtersToQuery } from "@/hooks/useFilters";
import { ChartShell } from "@/components/ChartShell";
import { RankedBarChart } from "@/components/RankedBarChart";
import { RevenueLineChart } from "@/components/RevenueLineChart";
import { formatCurrency, formatHour, formatInteger } from "@/lib/format";
import { cn } from "@/lib/utils";

const MAX_RESTAURANTS = 6;

export default function Comparison() {
  const f = useFilters();
  const tooMany = f.restaurants !== null && f.restaurants.length > MAX_RESTAURANTS;

  const q = useQuery<ComparisonRow[], ApiError>({
    enabled: !tooMany,
    queryKey: ["comparison", f.from, f.to, f.restaurants],
    queryFn: async () =>
      unwrap(await api.GET("/api/comparison", { params: { query: filtersToQuery(f) } })) as ComparisonRow[],
  });
  const rows = q.data ?? [];

  // Per-restaurant daily revenue for the trend chart. Reuses /overview/trend
  // by issuing one request per restaurant — fine for ≤6 restaurants.
  const trendQs = useQuery<{ id: number; name: string; trend: TrendPoint[] }[], ApiError>({
    enabled: !tooMany && rows.length > 0,
    queryKey: ["comparison-trends", f.from, f.to, rows.map((r) => r.id).join(",")],
    queryFn: async () => {
      const out: { id: number; name: string; trend: TrendPoint[] }[] = [];
      for (const r of rows) {
        const t = unwrap(
          await api.GET("/api/overview/trend", {
            params: {
              query: { ...filtersToQuery(f), restaurants: String(r.id) },
            },
          }),
        ) as TrendPoint[];
        out.push({ id: r.id, name: r.name, trend: t });
      }
      return out;
    },
  });

  // Merge trends onto a single x-axis (set of all days present anywhere).
  const mergedTrend = useMemo(() => {
    const all = new Set<string>();
    for (const t of trendQs.data ?? []) for (const p of t.trend) all.add(p.day);
    const days = [...all].sort();
    return days.map((d) => {
      const row: Record<string, string | number | null> = { day: d };
      for (const t of trendQs.data ?? []) {
        row[t.name] = t.trend.find((p) => p.day === d)?.revenue ?? null;
      }
      return row;
    });
  }, [trendQs.data]);

  if (tooMany) {
    return (
      <Alert variant="destructive">
        <AlertCircle />
        <AlertTitle>Too many restaurants selected</AlertTitle>
        <AlertDescription>
          Comparison gets unreadable past {MAX_RESTAURANTS} restaurants. Narrow the filter to {MAX_RESTAURANTS} or fewer.
        </AlertDescription>
      </Alert>
    );
  }

  // Highlight extremes per row (design-doc §9.5).
  const numericMaxMin = (key: keyof ComparisonRow) => {
    const values = rows.map((r) => (r[key] as number | null) ?? null).filter((v): v is number => v != null);
    if (values.length < 2) return { max: NaN, min: NaN };
    return { max: Math.max(...values), min: Math.min(...values) };
  };
  const revMM = numericMaxMin("revenue");
  const billsMM = numericMaxMin("bills");
  const aovMM = numericMaxMin("avg_ticket");

  const tint = (val: number | null, mm: { max: number; min: number }) => {
    if (val == null || isNaN(mm.max)) return "";
    if (val === mm.max) return "bg-emerald-500/10 font-medium";
    if (val === mm.min) return "bg-rose-500/10";
    return "";
  };

  return (
    <div className="grid gap-6">
      <Card>
        <CardHeader>
          <CardTitle>Restaurant comparison</CardTitle>
        </CardHeader>
        <CardContent>
          <ChartShell
            isLoading={q.isLoading}
            isError={q.isError}
            isEmpty={!q.isLoading && !q.isError && rows.length === 0}
            onRetry={() => q.refetch()}
            errorMessage={q.error?.detail}
            height={200}
          >
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Restaurant</TableHead>
                  <TableHead>City</TableHead>
                  <TableHead className="text-right">Revenue</TableHead>
                  <TableHead className="text-right">Bills</TableHead>
                  <TableHead className="text-right">Avg ticket</TableHead>
                  <TableHead>Top item</TableHead>
                  <TableHead className="text-right">Peak hour</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {rows.map((r) => (
                  <TableRow key={r.id}>
                    <TableCell className="font-medium">{r.name}</TableCell>
                    <TableCell className="text-muted-foreground">{r.city}</TableCell>
                    <TableCell className={cn("text-right tabular-nums", tint(r.revenue, revMM))}>
                      {formatCurrency(r.revenue)}
                    </TableCell>
                    <TableCell className={cn("text-right tabular-nums", tint(r.bills, billsMM))}>
                      {formatInteger(r.bills)}
                    </TableCell>
                    <TableCell className={cn("text-right tabular-nums", tint(r.avg_ticket, aovMM))}>
                      {formatCurrency(r.avg_ticket)}
                    </TableCell>
                    <TableCell>{r.top_item ?? "—"}</TableCell>
                    <TableCell className="text-right tabular-nums">{formatHour(r.peak_hour)}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </ChartShell>
        </CardContent>
      </Card>

      {rows.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle>Revenue by restaurant</CardTitle>
          </CardHeader>
          <CardContent>
            <RankedBarChart
              data={[...rows].sort((a, b) => b.revenue - a.revenue).map((r) => ({ name: r.name, value: r.revenue }))}
              labelKey="name"
              valueKey="value"
              formatter={formatCurrency}
              height={Math.max(240, rows.length * 36)}
            />
          </CardContent>
        </Card>
      )}

      {rows.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle>Daily revenue trend (overlaid)</CardTitle>
          </CardHeader>
          <CardContent>
            <ChartShell
              isLoading={trendQs.isLoading}
              isError={trendQs.isError}
              isEmpty={!trendQs.isLoading && !trendQs.isError && mergedTrend.length === 0}
              onRetry={() => trendQs.refetch()}
              errorMessage={trendQs.error?.detail}
              height={320}
            >
              <RevenueLineChart
                data={mergedTrend}
                xKey="day"
                series={(trendQs.data ?? []).map((t) => ({ key: t.name, label: t.name }))}
                yFormat="currency"
                height={320}
              />
            </ChartShell>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
