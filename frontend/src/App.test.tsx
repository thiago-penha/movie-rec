import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";

import App from "./App.tsx";
import { server } from "./test/server.ts";

function renderApp() {
  // A fresh client per test so cached results never leak between tests.
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <App />
    </QueryClientProvider>,
  );
}

describe("App", () => {
  it("shows the title", () => {
    renderApp();
    expect(screen.getByRole("heading", { name: "CineMatch" })).toBeInTheDocument();
  });

  it("shows the TMDB attribution", () => {
    renderApp();
    expect(
      screen.getByText(/uses the TMDB API but is not endorsed or certified by TMDB/),
    ).toBeInTheDocument();
  });

  it("shows ok for both services when they are healthy", async () => {
    renderApp();
    // The status elements exist from the first render (showing "checking…"),
    // so wait for their text to change rather than for them to appear.
    await waitFor(() => {
      expect(screen.getByTestId("status-api")).toHaveTextContent("ok");
      expect(screen.getByTestId("status-recommender")).toHaveTextContent("ok");
    });
  });

  it("shows unreachable when a service fails", async () => {
    server.use(http.get("*/rec/health", () => new HttpResponse(null, { status: 502 })));
    renderApp();
    await waitFor(() => {
      expect(screen.getByTestId("status-recommender")).toHaveTextContent("unreachable");
      // One service failing must not affect the other.
      expect(screen.getByTestId("status-api")).toHaveTextContent("ok");
    });
  });
});
