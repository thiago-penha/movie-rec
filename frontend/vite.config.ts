/// <reference types="vitest/config" />
import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port: 5173,
    // Dev-time stand-in for Caddy: the browser only talks to localhost:5173 and
    // Vite forwards these prefixes to the services. Same URLs as production, and
    // no CORS needed because everything looks same-origin to the browser.
    proxy: {
      // 127.0.0.1, not localhost: the ports are bound to IPv4 only, and Node may
      // resolve localhost to IPv6 (::1) first.
      "/api": "http://127.0.0.1:8000",
      "/rec": "http://127.0.0.1:8001",
    },
  },
  test: {
    environment: "jsdom",
    setupFiles: ["./src/test/setup.ts"],
  },
});
