/**
 * Named-type aliases for the auto-generated OpenAPI types.
 *
 * Lives separately from `types.ts` so `make types` can overwrite the generated
 * file without clobbering these aliases.
 */
import type { components } from "./types";

type S = components["schemas"];

export type UserOut = S["UserOut"];
export type Restaurant = S["RestaurantOut"];
export type Category = S["CategoryOut"];
export type BestSeller = S["BestSellerRow"];
export type Kpis = S["KpisOut"];
export type KpisWithDelta = S["KpisWithDelta"];
export type TrendPoint = S["TrendPoint"];
export type TimeSeriesPoint = S["TimeSeriesPoint"];
export type PeakHourCell = S["PeakHourCell"];
export type ComparisonRow = S["ComparisonRow"];
