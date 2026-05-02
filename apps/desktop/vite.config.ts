import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

// Vite dev server proxies /api → 127.0.0.1:4001 so the React app can
// fetch without CORS. Production builds (Tauri shell in v0.4c) will
// be served same-origin and won't need the proxy.
export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    host: "127.0.0.1",
    port: 5173,
    proxy: {
      "/api": {
        target: "http://127.0.0.1:4001",
        changeOrigin: true,
      },
    },
  },
});
