import type { ReactNode } from "react";
import { AlertCircle, Inbox } from "lucide-react";
import { Skeleton } from "@/components/ui/skeleton";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";

type Props = {
  title?: string;
  isLoading: boolean;
  isError: boolean;
  isEmpty: boolean;
  onRetry?: () => void;
  errorMessage?: string;
  children: ReactNode;
  height?: number;
};

/**
 * Wraps any chart/table with the design-doc §10.2 contract:
 *   loading → skeleton, never a spinner-only screen
 *   error   → in-place error state with retry, no whole-page crash
 *   empty   → "No data" message + hint
 */
export function ChartShell({
  title,
  isLoading,
  isError,
  isEmpty,
  onRetry,
  errorMessage,
  children,
  height = 240,
}: Props) {
  if (isLoading) {
    return <Skeleton className="w-full" style={{ height }} />;
  }
  if (isError) {
    return (
      <Alert variant="destructive">
        <AlertCircle />
        <AlertTitle>Couldn't load{title ? ` ${title}` : ""}</AlertTitle>
        <AlertDescription>
          <div>{errorMessage ?? "Something went wrong fetching data."}</div>
          {onRetry && (
            <div className="mt-2">
              <Button size="sm" variant="outline" onClick={onRetry}>
                Retry
              </Button>
            </div>
          )}
        </AlertDescription>
      </Alert>
    );
  }
  if (isEmpty) {
    return (
      <div className="flex flex-col items-center justify-center gap-2 rounded-lg border border-dashed py-12 text-muted-foreground" style={{ minHeight: height }}>
        <Inbox className="h-6 w-6" />
        <div className="text-sm">No data in this range.</div>
        <div className="text-xs">Try widening the date range or selecting different restaurants.</div>
      </div>
    );
  }
  return <>{children}</>;
}
