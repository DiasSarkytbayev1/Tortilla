import { useQuery } from "@tanstack/react-query";
import { api, ApiError, unwrap } from "@/api/client";
import type { KpisWithDelta, TrendPoint } from "@/api/schemas";
import { ChartShell } from "@/components/ChartShell";
import { KPICard } from "@/components/KPICard";
import { RevenueLineChart } from "@/components/RevenueLineChart";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { useFilters, filtersToQuery } from "@/hooks/useFilters";
import { formatCurrency, formatDelta, formatHour, formatInteger } from "@/lib/format";

export default function Overview() {
  const f = useFilters();
  const params = { params: { query: filtersToQuery(f) } };

  const kpisQ = useQuery<KpisWithDelta, ApiError>({
    queryKey: ["overview-kpis", f.from, f.to, f.restaurants],
    queryFn: async () => unwrap(await api.GET("/api/overview/kpis", params)) as KpisWithDelta,
  });
  const trendQ = useQuery<TrendPoint[], ApiError>({
    queryKey: ["overview-trend", f.from, f.to, f.restaurants],
    queryFn: async () => unwrap(await api.GET("/api/overview/trend", params)) as TrendPoint[],
  });

  const cur = kpisQ.data?.current;
  const prev = kpisQ.data?.previous;
  const trend = trendQ.data ?? [];

  return (
    <div className="grid gap-6">
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-5">
        {kpisQ.isLoading || !cur ? (
          <>
            {Array.from({ length: 5 }).map((_, i) => (
              <Card key={i}>
                <CardHeader className="pb-2">
                  <CardTitle className="text-xs font-medium uppercase tracking-wide text-muted-foreground">…</CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="h-7 w-24 animate-pulse rounded-md bg-muted" />
                </CardContent>
              </Card>
            ))}
          </>
        ) : (
          <>
            <KPICard
              label="Revenue"
              value={formatCurrency(cur.revenue)}
              delta={formatDelta(cur.revenue, prev?.revenue ?? null)}
            />
            <KPICard
              label="Bills"
              value={formatInteger(cur.bills)}
              delta={formatDelta(cur.bills, prev?.bills ?? null)}
            />
            <KPICard
              label="Avg ticket"
              value={formatCurrency(cur.avg_ticket)}
              delta={formatDelta(cur.avg_ticket, prev?.avg_ticket ?? null)}
            />
            <KPICard
              label="Top item"
              value={cur.top_item?.name ?? "—"}
              sub={cur.top_item ? `${formatInteger(cur.top_item.qty)} sold` : undefined}
            />
            <KPICard
              label="Peak hour"
              value={formatHour(cur.peak_hour?.hour)}
              sub={cur.peak_hour ? `${formatInteger(cur.peak_hour.bills)} bills` : undefined}
            />
          </>
        )}
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Revenue trend</CardTitle>
        </CardHeader>
        <CardContent>
          <ChartShell
            isLoading={trendQ.isLoading}
            isError={trendQ.isError}
            isEmpty={!trendQ.isLoading && !trendQ.isError && trend.length === 0}
            onRetry={() => trendQ.refetch()}
            errorMessage={trendQ.error?.detail}
            height={280}
          >
            <RevenueLineChart
              data={trend.map((p) => ({ ...p, day: p.day }))}
              xKey="day"
              series={[{ key: "revenue", label: "Revenue" }]}
              yFormat="currency"
            />
          </ChartShell>
        </CardContent>
      </Card>
    </div>
  );
}
