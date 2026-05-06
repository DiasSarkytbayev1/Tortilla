import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { formatCurrency, formatInteger } from "@/lib/format";

type Series = { key: string; label: string; color?: string; dashed?: boolean };
type Point = Record<string, string | number | null>;

type Props = {
  data: Point[];
  xKey: string;
  series: Series[];
  yFormat?: "currency" | "integer";
  height?: number;
};

const PALETTE = [
  "var(--color-chart-1)",
  "var(--color-chart-2)",
  "var(--color-chart-3)",
  "var(--color-chart-4)",
  "var(--color-chart-5)",
];

export function RevenueLineChart({ data, xKey, series, yFormat = "currency", height = 280 }: Props) {
  const fmt = yFormat === "currency" ? formatCurrency : formatInteger;
  return (
    <ResponsiveContainer width="100%" height={height}>
      <LineChart data={data} margin={{ top: 8, right: 16, bottom: 0, left: 8 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" />
        <XAxis dataKey={xKey} stroke="var(--color-muted-foreground)" fontSize={12} />
        <YAxis tickFormatter={(v) => fmt(v as number)} stroke="var(--color-muted-foreground)" fontSize={12} width={80} />
        <Tooltip
          contentStyle={{
            background: "var(--color-popover)",
            border: "1px solid var(--color-border)",
            borderRadius: 8,
            color: "var(--color-popover-foreground)",
          }}
          formatter={(value: unknown) => fmt(Number(value))}
        />
        {series.map((s, i) => (
          <Line
            key={s.key}
            type="linear"
            dataKey={s.key}
            stroke={s.color ?? PALETTE[i % PALETTE.length]}
            strokeWidth={2}
            strokeDasharray={s.dashed ? "5 4" : undefined}
            name={s.label}
            dot={false}
            isAnimationActive={false}
          />
        ))}
      </LineChart>
    </ResponsiveContainer>
  );
}
