import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Checkbox } from "@/components/ui/checkbox";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import { ChartShell } from "@/components/ChartShell";
import { RevenueLineChart } from "@/components/RevenueLineChart";
import { api, ApiError, unwrap } from "@/api/client";
import type { TimeSeriesPoint } from "@/api/schemas";
import { useFilters, filtersToQuery } from "@/hooks/useFilters";
import { parseDate, pickGranularity, previousPeriod, isoDate, rangeDays } from "@/lib/periods";

type Granularity = "hour" | "day" | "week" | "month";
type Metric = "revenue" | "bills" | "avg_ticket";

export default function TimeSeries() {
  const f = useFilters();
  const fromD = parseDate(f.from);
  const toD = parseDate(f.to);
  const days = fromD && toD ? rangeDays(fromD, toD) : 7;
  const [granularity, setGranularity] = useState<Granularity>(pickGranularity(days));
  const [metric, setMetric] = useState<Metric>("revenue");
  const [overlay, setOverlay] = useState(false);

  const currentQ = useQuery<TimeSeriesPoint[], ApiError>({
    queryKey: ["time-series", f.from, f.to, f.restaurants, granularity],
    queryFn: async () =>
      unwrap(
        await api.GET("/api/time-series", {
          params: { query: { ...filtersToQuery(f), granularity } },
        }),
      ) as TimeSeriesPoint[],
  });

  const prev = fromD && toD ? previousPeriod(fromD, toD) : null;
  const previousQ = useQuery<TimeSeriesPoint[], ApiError>({
    enabled: overlay && !!prev,
    queryKey: ["time-series-prev", prev?.from, prev?.to, f.restaurants, granularity],
    queryFn: async () =>
      unwrap(
        await api.GET("/api/time-series", {
          params: {
            query: {
              ...filtersToQuery(f),
              from: isoDate(prev!.from),
              to: isoDate(prev!.to),
              granularity,
            },
          },
        }),
      ) as TimeSeriesPoint[],
  });

  // Align previous series onto current x-axis: take only the first N points
  // from previous and zip them by index with current.
  const merged = (() => {
    const cur = currentQ.data ?? [];
    if (!overlay) return cur.map((p) => ({ ...p, current: p[metric] }));
    const prevData = previousQ.data ?? [];
    return cur.map((p, i) => ({
      ...p,
      current: p[metric],
      prev: prevData[i]?.[metric] ?? null,
    }));
  })();

  const isEmpty = !currentQ.isLoading && !currentQ.isError && merged.length === 0;

  return (
    <Card>
      <CardHeader className="flex-row flex-wrap items-center justify-between gap-4">
        <CardTitle>Time series</CardTitle>
        <div className="flex flex-wrap items-center gap-6">
          <RadioGroup
            value={granularity}
            onValueChange={(v) => setGranularity(v as Granularity)}
            className="flex items-center gap-3"
          >
            {(["hour", "day", "week", "month"] as Granularity[]).map((g) => (
              <div key={g} className="flex items-center gap-1.5">
                <RadioGroupItem value={g} id={`gr-${g}`} />
                <Label htmlFor={`gr-${g}`} className="text-sm font-normal capitalize">
                  {g}
                </Label>
              </div>
            ))}
          </RadioGroup>
          <RadioGroup
            value={metric}
            onValueChange={(v) => setMetric(v as Metric)}
            className="flex items-center gap-3"
          >
            <div className="flex items-center gap-1.5">
              <RadioGroupItem value="revenue" id="m-rev" />
              <Label htmlFor="m-rev" className="text-sm font-normal">Revenue</Label>
            </div>
            <div className="flex items-center gap-1.5">
              <RadioGroupItem value="bills" id="m-bills" />
              <Label htmlFor="m-bills" className="text-sm font-normal">Bills</Label>
            </div>
            <div className="flex items-center gap-1.5">
              <RadioGroupItem value="avg_ticket" id="m-aov" />
              <Label htmlFor="m-aov" className="text-sm font-normal">Avg ticket</Label>
            </div>
          </RadioGroup>
          <label className="flex items-center gap-2 text-sm">
            <Checkbox checked={overlay} onCheckedChange={(c) => setOverlay(Boolean(c))} />
            Show previous period
          </label>
        </div>
      </CardHeader>
      <CardContent>
        <ChartShell
          isLoading={currentQ.isLoading}
          isError={currentQ.isError}
          isEmpty={isEmpty}
          onRetry={() => currentQ.refetch()}
          errorMessage={currentQ.error?.detail}
          height={320}
        >
          <RevenueLineChart
            data={merged}
            xKey="bucket"
            yFormat={metric === "revenue" || metric === "avg_ticket" ? "currency" : "integer"}
            series={[
              { key: "current", label: "This period" },
              ...(overlay ? [{ key: "prev", label: "Previous period", dashed: true } as const] : []),
            ]}
            height={320}
          />
        </ChartShell>
      </CardContent>
    </Card>
  );
}
