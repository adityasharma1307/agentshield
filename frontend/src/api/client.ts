import createClient from "openapi-fetch";

import type { paths } from "./schema";

/** Client generated from `frontend/openapi.json`. Paths come from that file. */
export const api = createClient<paths>({ baseUrl: "/api" });

export function problem(error: unknown, response: Response): string {
  if (error && typeof error === "object" && "detail" in error) {
    const detail = error.detail;
    if (typeof detail === "string" && detail.length > 0) {
      return detail;
    }
  }
  if (response.status === 404) {
    return "That run was not found.";
  }
  return `The service returned ${response.status}.`;
}
