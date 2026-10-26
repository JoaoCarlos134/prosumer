import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// npm run dev: the page on :5173, its /api calls sent to the FastAPI server on :8080 (prosumer_site.cmd dev, or uvicorn)
export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: { proxy: { "/api": "http://127.0.0.1:8080" } },
  build: {
    chunkSizeWarningLimit: 1600,
    rollupOptions: {
      output: { manualChunks: { echarts: ["echarts"], leaflet: ["leaflet"] } },
    },
  },
});
