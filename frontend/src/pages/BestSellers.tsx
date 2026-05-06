import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api, ApiError, unwrap } from "@/api/client";
import type { BestSeller } from "@/api/schemas";
import { useFilters, filtersToQuery } from "@/hooks/useFilters";
import { ChartShell } from "@/components/ChartShell";
import { RankedBarChart } from "@/components/RankedBarChart";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { formatCurrency, formatInteger, formatPct } from "@/lib/format";

export default function BestSellers() {
  const f = useFilters();
  const [rankBy, setRankBy] = useState<"quantity" | "revenue">("quantity");
  const [topN, setTopN] = useState(20);

  const q = useQuery<BestSeller[], ApiError>({
    queryKey: ["best-sellers", f.from, f.to, f.restaurants, f.categories, rankBy, topN],
    queryFn: async () =>
      unwrap(
        await api.GET("/api/best-sellers", {
          params: { query: { ...filtersToQuery(f), rank_by: rankBy, top_n: topN } },
        }),
      ) as BestSeller[],
  });

  const rows = q.data ?? [];
  const isEmpty = !q.isLoading && !q.isError && rows.length === 0;

  return (
    <div className="grid gap-6">
      <Card>
        <CardHeader className="flex-row items-center justify-between gap-4">
          <CardTitle>Best Sellers</CardTitle>
          <div className="flex items-center gap-6">
            <RadioGroup value={rankBy} onValueChange={(v) => setRankBy(v as "quantity" | "revenue")} className="flex items-center gap-3">
              <div className="flex items-center gap-1.5">
                <RadioGroupItem value="quantity" id="rb-qty" />
                <Label htmlFor="rb-qty" className="text-sm font-normal">Quantity</Label>
              </div>
              <div className="flex items-center gap-1.5">
                <RadioGroupItem value="revenue" id="rb-rev" />
                <Label htmlFor="rb-rev" className="text-sm font-normal">Revenue</Label>
              </div>
            </RadioGroup>
            <div className="flex items-center gap-2">
              <Label className="text-sm font-normal">Show</Label>
              <Select value={String(topN)} onValueChange={(v) => setTopN(Number(v))}>
                <SelectTrigger className="w-[110px]">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {[10, 20, 50, 100].map((n) => (
                    <SelectItem key={n} value={String(n)}>
                      Top {n}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          <ChartShell
            isLoading={q.isLoading}
            isError={q.isError}
            isEmpty={isEmpty}
            onRetry={() => q.refetch()}
            errorMessage={q.error?.detail}
            height={Math.max(280, rows.length * 26)}
          >
            <RankedBarChart
              data={rows.map((r) => ({ name: r.name, value: rankBy === "quantity" ? r.qty : r.revenue }))}
              labelKey="name"
              valueKey="value"
              formatter={rankBy === "quantity" ? formatInteger : formatCurrency}
              height={Math.max(280, rows.length * 26)}
            />
          </ChartShell>
        </CardContent>
      </Card>

      {!isEmpty && !q.isLoading && !q.isError && (
        <Card>
          <CardContent className="pt-6">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="w-12">#</TableHead>
                  <TableHead>Item</TableHead>
                  <TableHead>Category</TableHead>
                  <TableHead className="text-right">Qty</TableHead>
                  <TableHead className="text-right">Revenue</TableHead>
                  <TableHead className="text-right">% of total</TableHead>
                  <TableHead className="text-right">Bills</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {rows.map((r, i) => (
                  <TableRow key={r.id}>
                    <TableCell className="text-muted-foreground">{i + 1}</TableCell>
                    <TableCell className="font-medium">{r.name}</TableCell>
                    <TableCell className="capitalize text-muted-foreground">{r.category}</TableCell>
                    <TableCell className="text-right tabular-nums">{formatInteger(r.qty)}</TableCell>
                    <TableCell className="text-right tabular-nums">{formatCurrency(r.revenue)}</TableCell>
                    <TableCell className="text-right tabular-nums">{formatPct(r.pct_of_total)}</TableCell>
                    <TableCell className="text-right tabular-nums">{formatInteger(r.bills)}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
