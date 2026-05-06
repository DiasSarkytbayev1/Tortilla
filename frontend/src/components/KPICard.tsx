import { ArrowDownRight, ArrowRight, ArrowUpRight, HelpCircle } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { cn } from "@/lib/utils";

type Props = {
  label: string;
  value: React.ReactNode;
  sub?: React.ReactNode;
  delta?: { pct: number | null; direction: "up" | "down" | "flat" | "unknown" };
  positiveIsGood?: boolean;
};

export function KPICard({ label, value, sub, delta, positiveIsGood = true }: Props) {
  const dir = delta?.direction;
  const colour =
    dir === "up"
      ? positiveIsGood ? "text-emerald-600 dark:text-emerald-400" : "text-rose-600 dark:text-rose-400"
      : dir === "down"
        ? positiveIsGood ? "text-rose-600 dark:text-rose-400" : "text-emerald-600 dark:text-emerald-400"
        : "text-muted-foreground";
  const Icon = dir === "up" ? ArrowUpRight : dir === "down" ? ArrowDownRight : dir === "flat" ? ArrowRight : HelpCircle;

  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-xs font-medium uppercase tracking-wide text-muted-foreground">{label}</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="text-2xl font-semibold tracking-tight">{value}</div>
        {sub && <div className="mt-1 text-xs text-muted-foreground">{sub}</div>}
        {delta && (
          <div className={cn("mt-2 flex items-center gap-1 text-xs", colour)} title="vs previous period of equal length">
            <Icon className="h-3 w-3" />
            {delta.pct == null ? "—" : `${delta.pct >= 0 ? "+" : ""}${delta.pct.toFixed(1)}%`}
            <span className="text-muted-foreground"> vs prev</span>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
