import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";
import { VitePWA } from "vite-plugin-pwa";

declare const process: { env: Record<string, string | undefined> };

const API = process.env.BMU_API_URL ?? "http://localhost:18000";

export default defineConfig({
  plugins: [
    react(),
    tailwindcss(),
    VitePWA({
      registerType: "autoUpdate",
      includeAssets: ["favicon.svg"],
      manifest: {
        name: "BMU Lab",
        short_name: "BMU Lab",
        description: "বিএমইউ ল্যাব — পরীক্ষা বুকিং, অর্ডারের অবস্থা ও রিপোর্ট",
        lang: "bn",
        start_url: "/",
        display: "standalone",
        background_color: "#faf8f3",
        theme_color: "#006a4e",
        icons: [{ src: "/favicon.svg", sizes: "any", type: "image/svg+xml", purpose: "any maskable" }],
      },
      workbox: {
        navigateFallback: "/index.html",
        navigateFallbackDenylist: [/^\/api\//],
        globPatterns: ["**/*.{js,css,html,svg,woff2}"],
      },
    }),
  ],
  server: {
    port: 5173,
    proxy: { "/api": { target: API, changeOrigin: false } },
  },
  preview: { proxy: { "/api": { target: API, changeOrigin: false } } },
  build: { sourcemap: true },
  test: { environment: "jsdom" },
} as import("vite").UserConfig);
