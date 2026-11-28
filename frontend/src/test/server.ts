import { http, HttpResponse } from "msw";
import { setupServer } from "msw/node";

// Default handlers: every service healthy. Tests override them with server.use().
export const handlers = [
  http.get("*/api/health", () => HttpResponse.json({ status: "ok" })),
  http.get("*/rec/health", () => HttpResponse.json({ status: "ok" })),
];

export const server = setupServer(...handlers);
