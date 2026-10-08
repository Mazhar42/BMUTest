import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

declare const process: { env: Record<string, string | undefined> };

const API = process.env.BMU_API_URL ?? "http://localhost:18000";

export default defineConfig({
  base: "/staff/",
  plugins: [react(), tailwindcss()],
  server: {
    port: 5174,
    proxy: { "/api": { target: API, changeOrigin: false } },
  },
  preview: { proxy: { "/api": { target: API, changeOrigin: false } } },
  build: { sourcemap: true },
  test: { environment: "jsdom" },
} as import("vite").UserConfig);
