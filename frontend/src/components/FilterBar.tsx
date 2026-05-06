import { format, parseISO } from "date-fns";
import { CalendarIcon, ChevronDown } from "lucide-react";
import { useQuery } from "@tanstack/react-query";
import { Calendar } from "@/components/ui/calendar";
import { Button } from "@/components/ui/button";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { Checkbox } from "@/components/ui/checkbox";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { useFilters } from "@/hooks/useFilters";
import { isoDate, presetRange, type PeriodPreset } from "@/lib/periods";
import { api, unwrap } from "@/api/client";
import type { Restaurant, Category } from "@/api/schemas";
import { cn } from "@/lib/utils";

const PRESETS: { key: PeriodPreset; label: string }[] = [
  { key: "today", label: "Today" },
  { key: "yesterday", label: "Yesterday" },
  { key: "last7d", label: "Last 7 days" },
  { key: "last30d", label: "Last 30 days" },
  { key: "mtd", label: "Month-to-date" },
  { key: "last90d", label: "Last 90 days" },
  { key: "ytd", label: "Year-to-date" },
];

export type FilterApplicability = {
  restaurants?: boolean;
  categories?: boolean;
};

export function FilterBar({ applicability = { restaurants: true, categories: true } }: { applicability?: FilterApplicability }) {
  const f = useFilters();

  const restaurantsQ = useQuery({
    queryKey: ["restaurants"],
    queryFn: async () => unwrap(await api.GET("/api/restaurants")) as Restaurant[],
  });
  const categoriesQ = useQuery({
    queryKey: ["categories"],
    queryFn: async () => unwrap(await api.GET("/api/categories")) as Category[],
  });

  const fromDate = parseISO(f.from);
  const toDate = parseISO(f.to);

  const onPreset = (preset: PeriodPreset) => {
    const { from, to } = presetRange(preset);
    void f.setFrom(isoDate(from));
    void f.setTo(isoDate(to));
  };

  const allRestaurants = (restaurantsQ.data ?? []).map((r) => r.id);
  const selectedRestaurants = f.restaurants ?? allRestaurants;

  return (
    <div className="flex flex-wrap items-center gap-2 border-b bg-card px-6 py-3 shadow-sm">
      {/* Date range */}
      <Popover>
        <PopoverTrigger asChild>
          <Button variant="outline" className="w-[260px] justify-start font-normal">
            <CalendarIcon className="mr-2 h-4 w-4" />
            {format(fromDate, "MMM d, yyyy")} – {format(toDate, "MMM d, yyyy")}
            <ChevronDown className="ml-auto h-4 w-4 opacity-50" />
          </Button>
        </PopoverTrigger>
        <PopoverContent className="w-auto p-0" align="start">
          <div className="flex flex-col gap-1 p-2">
            {PRESETS.map((p) => (
              <Button key={p.key} variant="ghost" size="sm" className="justify-start" onClick={() => onPreset(p.key)}>
                {p.label}
              </Button>
            ))}
          </div>
          <Separator />
          <Calendar
            mode="range"
            defaultMonth={fromDate}
            selected={{ from: fromDate, to: toDate }}
            numberOfMonths={2}
            onSelect={(r) => {
              if (r?.from) void f.setFrom(isoDate(r.from));
              if (r?.to) void f.setTo(isoDate(r.to));
            }}
          />
        </PopoverContent>
      </Popover>

      {/* Restaurants */}
      <Popover>
        <PopoverTrigger asChild>
          <Button
            variant="outline"
            disabled={!applicability.restaurants}
            className={cn("min-w-[180px] justify-start font-normal", !applicability.restaurants && "opacity-50")}
            title={applicability.restaurants ? undefined : "Restaurant filter doesn't apply to this view"}
          >
            <span className="truncate">
              {f.restaurants == null
                ? `All restaurants (${allRestaurants.length})`
                : `${f.restaurants.length} selected`}
            </span>
            <ChevronDown className="ml-auto h-4 w-4 opacity-50" />
          </Button>
        </PopoverTrigger>
        <PopoverContent className="w-72 p-0" align="start">
          <div className="flex items-center justify-between border-b px-3 py-2">
            <span className="text-sm font-medium">Restaurants</span>
            <Button variant="ghost" size="sm" onClick={() => f.setRestaurants(null)}>
              All
            </Button>
          </div>
          <div className="max-h-72 overflow-y-auto p-2">
            {(restaurantsQ.data ?? []).map((r) => {
              const checked = selectedRestaurants.includes(r.id);
              return (
                <label
                  key={r.id}
                  className="flex cursor-pointer items-center gap-2 rounded-sm px-2 py-1.5 hover:bg-accent"
                >
                  <Checkbox
                    checked={checked}
                    onCheckedChange={(c) => {
                      const next = c
                        ? [...selectedRestaurants, r.id]
                        : selectedRestaurants.filter((id) => id !== r.id);
                      // If user manually selected all → store null (= "all").
                      f.setRestaurants(next.length === allRestaurants.length ? null : next);
                    }}
                  />
                  <span className="text-sm">
                    {r.name} <span className="text-muted-foreground">· {r.city}</span>
                  </span>
                </label>
              );
            })}
          </div>
        </PopoverContent>
      </Popover>

      {/* Categories */}
      <Popover>
        <PopoverTrigger asChild>
          <Button
            variant="outline"
            disabled={!applicability.categories}
            className={cn("min-w-[160px] justify-start font-normal", !applicability.categories && "opacity-50")}
            title={applicability.categories ? undefined : "Category filter doesn't apply to this view"}
          >
            <span className="truncate">
              {f.categories == null
                ? `All categories`
                : `${f.categories.length} selected`}
            </span>
            <ChevronDown className="ml-auto h-4 w-4 opacity-50" />
          </Button>
        </PopoverTrigger>
        <PopoverContent className="w-56 p-0" align="start">
          <div className="flex items-center justify-between border-b px-3 py-2">
            <span className="text-sm font-medium">Categories</span>
            <Button variant="ghost" size="sm" onClick={() => f.setCategories(null)}>
              All
            </Button>
          </div>
          <div className="max-h-60 overflow-y-auto p-2">
            {(categoriesQ.data ?? []).map((c) => {
              const checked = (f.categories ?? (categoriesQ.data ?? []).map((x) => x.category)).includes(c.category);
              return (
                <label
                  key={c.category}
                  className="flex cursor-pointer items-center gap-2 rounded-sm px-2 py-1.5 hover:bg-accent"
                >
                  <Checkbox
                    checked={checked}
                    onCheckedChange={(state) => {
                      const all = (categoriesQ.data ?? []).map((x) => x.category);
                      const current = f.categories ?? all;
                      const next = state ? [...current, c.category] : current.filter((x) => x !== c.category);
                      f.setCategories(next.length === all.length ? null : next);
                    }}
                  />
                  <span className="text-sm capitalize">{c.category}</span>
                </label>
              );
            })}
          </div>
        </PopoverContent>
      </Popover>

      <Button
        variant="ghost"
        size="sm"
        onClick={() => {
          const { from, to } = presetRange("last7d");
          void f.setFrom(isoDate(from));
          void f.setTo(isoDate(to));
          f.setRestaurants(null);
          f.setCategories(null);
        }}
      >
        Reset
      </Button>

      <div className="ml-auto flex items-center gap-2 text-xs text-muted-foreground">
        <Badge variant="outline">Europe/Madrid</Badge>
      </div>
    </div>
  );
}
