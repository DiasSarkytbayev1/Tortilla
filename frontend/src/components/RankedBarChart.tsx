import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

type Props<T extends Record<string, unknown>> = {
  data: T[];
  labelKey: keyof T & string;
  valueKey: keyof T & string;
  formatter?: (v: number) => string;
  height?: number;
};

export function RankedBarChart<T extends Record<string, unknown>>({
  data,
  labelKey,
  valueKey,
  formatter,
  height = 480,
}: Props<T>) {
  return (
    <ResponsiveContainer width="100%" height={height}>
      <BarChart data={data} layout="vertical" margin={{ top: 8, right: 32, bottom: 0, left: 0 }}>
        <CartesianGrid strokeDasharray="3 3" horizontal={false} stroke="var(--color-border)" />
        <XAxis
          type="number"
          stroke="var(--color-muted-foreground)"
          fontSize={12}
          tickFormatter={formatter ? (v) => formatter(v as number) : undefined}
        />
        <YAxis
          type="category"
          dataKey={labelKey}
          stroke="var(--color-muted-foreground)"
          fontSize={12}
          width={180}
        />
        <Tooltip
          contentStyle={{
            background: "var(--color-popover)",
            border: "1px solid var(--color-border)",
            borderRadius: 8,
            color: "var(--color-popover-foreground)",
          }}
          formatter={(value: unknown) => (formatter ? formatter(Number(value)) : String(value))}
        />
        <Bar dataKey={valueKey} fill="var(--color-chart-1)" isAnimationActive={false} />
      </BarChart>
    </ResponsiveContainer>
  );
}
