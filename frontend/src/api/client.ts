import createClient from "openapi-fetch";
import type { paths } from "./types";

// Vite dev server proxies /api → backend. In prod the frontend will be served
// from the same origin as the API, so a relative base works in both modes.
export const api = createClient<paths>({
  baseUrl: "",
  credentials: "include",
});

export class ApiError extends Error {
  constructor(
    public status: number,
    public detail: string,
  ) {
    super(detail);
  }
}

export function unwrap<T>(res: { data?: T; error?: unknown; response: Response }): T {
  if (res.error) {
    const detail =
      typeof res.error === "object" && res.error && "detail" in res.error
        ? String((res.error as { detail: unknown }).detail)
        : `HTTP ${res.response.status}`;
    throw new ApiError(res.response.status, detail);
  }
  return res.data as T;
}
