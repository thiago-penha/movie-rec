import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/react";
import { afterAll, afterEach, beforeAll } from "vitest";

import { server } from "./server.ts";

// MSW intercepts fetch() at the network layer, so components are tested with
// their real data-fetching code and only the HTTP responses are fake.
// "error" makes a test fail if it calls an endpoint that has no mock.
beforeAll(() => server.listen({ onUnhandledFrame: "error" }));
afterEach(() => {
  server.resetHandlers();
  cleanup();
});
afterAll(() => server.close());
