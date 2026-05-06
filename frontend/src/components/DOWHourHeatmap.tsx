import { useMemo } from "react";
import type { PeakHourCell } from "@/api/schemas";
import { dowLabel, DOW_ORDER_MON_FIRST, formatCurrency, formatInteger } from "@/lib/format";

type Props = {
  data: PeakHourCell[];
  metric: "bills" | "revenue";
};

/**
 * 7×24 SVG heatmap. Recharts has no native heatmap, so we hand-draw it.
 * Mon-first row order (design-doc §10 open question 2).
 */
export function DOWHourHeatmap({ data, metric }: Props) {
  const { matrix, max } = useMemo(() => {
    const m: Record<number, Record<number, number>> = {};
    let mx = 0;
    for (let d = 0; d < 7; d++) m[d] = {};
    for (const c of data) {
      const v = metric === "bills" ? c.bills : c.revenue;
      m[c.dow][c.hour] = v;
      if (v > mx) mx = v;
    }
    return { matrix: m, max: mx };
  }, [data, metric]);

  const fmt = metric === "bills" ? formatInteger : formatCurrency;
  const cellW = 32;
  const cellH = 28;
  const labelW = 44;
  const headerH = 22;

  const colour = (v: number) => {
    if (max === 0) return "var(--color-muted)";
    const t = v / max;
    // OKLCH chroma tween between muted and chart-1.
    const lightness = 0.95 - t * 0.55;
    const chroma = t * 0.18;
    const hue = 41;
    return `oklch(${lightness} ${chroma} ${hue})`;
  };

  return (
    <div className="overflow-x-auto rounded-md border bg-card p-3">
      <svg
        width={labelW + 24 * cellW}
        height={headerH + 7 * cellH + 28}
        role="img"
        aria-label="Day of week by hour heatmap"
      >
        {/* hour headers */}
        {Array.from({ length: 24 }, (_, h) => (
          <text
            key={h}
            x={labelW + h * cellW + cellW / 2}
            y={headerH - 6}
            textAnchor="middle"
            fontSize={10}
            fill="var(--color-muted-foreground)"
          >
            {h.toString().padStart(2, "0")}
          </text>
        ))}
        {/* rows */}
        {DOW_ORDER_MON_FIRST.map((dow, rowIdx) => (
          <g key={dow}>
            <text
              x={labelW - 6}
              y={headerH + rowIdx * cellH + cellH / 2 + 4}
              textAnchor="end"
              fontSize={11}
              fill="var(--color-foreground)"
            >
              {dowLabel(dow)}
            </text>
            {Array.from({ length: 24 }, (_, h) => {
              const v = matrix[dow]?.[h] ?? 0;
              return (
                <rect
                  key={h}
                  x={labelW + h * cellW}
                  y={headerH + rowIdx * cellH}
                  width={cellW - 2}
                  height={cellH - 2}
                  rx={3}
                  fill={colour(v)}
                  stroke="var(--color-border)"
                  strokeWidth={0.5}
                >
                  <title>{`${dowLabel(dow)} ${h.toString().padStart(2, "0")}:00 — ${fmt(v)}`}</title>
                </rect>
              );
            })}
          </g>
        ))}
        {/* legend */}
        <text
          x={labelW}
          y={headerH + 7 * cellH + 22}
          fontSize={10}
          fill="var(--color-muted-foreground)"
        >
          low
        </text>
        {Array.from({ length: 6 }, (_, i) => (
          <rect
            key={i}
            x={labelW + 32 + i * 18}
            y={headerH + 7 * cellH + 12}
            width={16}
            height={10}
            fill={colour((max * (i + 1)) / 6)}
          />
        ))}
        <text
          x={labelW + 32 + 6 * 18 + 6}
          y={headerH + 7 * cellH + 22}
          fontSize={10}
          fill="var(--color-muted-foreground)"
        >
          peak
        </text>
      </svg>
    </div>
  );
}
