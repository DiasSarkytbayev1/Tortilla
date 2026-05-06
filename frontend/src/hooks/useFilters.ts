import { parseAsString, useQueryState } from "nuqs";
import { defaultRange } from "@/lib/periods";

/**
 * Global filter state, persisted in the URL (design-doc §10.1).
 *
 *   ?from=2026-04-27&to=2026-05-04&r=1,2,5&cat=mains,drinks
 *
 * - `r` and `cat` are omitted when "all" (per design-doc §8 URL encoding rule).
 * - When the URL is missing/invalid, we fall back to last-7d defaults so the
 *   first navigation never lands on a 400.
 *
 * Filter applicability per page is enforced at the component level — pages
 * either consume `restaurants/categories` or ignore them per the design-doc
 * §8 matrix.
 */
// `shallow: false` routes URL writes through react-router's navigation
// instead of calling `window.history.replaceState` directly. Without this,
// nuqs updates the address bar but react-router's `useLocation()` never
// fires, so `Layout`'s NavLink captures a stale `?search` when the user
// clicks a tab and the filter state silently drops.
const FILTER_OPTS = { shallow: false } as const;

export function useFilters() {
  const def = defaultRange();
  const [from, setFrom] = useQueryState(
    "from",
    parseAsString.withDefault(def.from).withOptions(FILTER_OPTS),
  );
  const [to, setTo] = useQueryState(
    "to",
    parseAsString.withDefault(def.to).withOptions(FILTER_OPTS),
  );
  const [restaurants, setRestaurants] = useQueryState(
    "r",
    parseAsString.withOptions(FILTER_OPTS),
  );
  const [categories, setCategories] = useQueryState(
    "cat",
    parseAsString.withOptions(FILTER_OPTS),
  );

  // CSV → number[]. Empty / null / malformed → null (= "all").
  const restaurantIds = restaurants
    ? restaurants
        .split(",")
        .map((x) => Number(x))
        .filter((n) => Number.isInteger(n))
    : null;

  const categoryList = categories ? categories.split(",").filter(Boolean) : null;

  return {
    from,
    to,
    setFrom,
    setTo,
    restaurants: restaurantIds,
    categories: categoryList,
    setRestaurants: (ids: number[] | null) =>
      setRestaurants(ids && ids.length ? ids.join(",") : null),
    setCategories: (cats: string[] | null) =>
      setCategories(cats && cats.length ? cats.join(",") : null),
  };
}

// Build the `?from=...&to=...&r=...&cat=...` query object the openapi-fetch
// expects. `restaurants` and `categories` are omitted (not empty) when "all".
export function filtersToQuery(f: ReturnType<typeof useFilters>) {
  return {
    from: f.from,
    to: f.to,
    ...(f.restaurants && f.restaurants.length ? { restaurants: f.restaurants.join(",") } : {}),
    ...(f.categories && f.categories.length ? { categories: f.categories.join(",") } : {}),
  };
}
