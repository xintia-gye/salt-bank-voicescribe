import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Frontend builds to ./dist and is served by the FastAPI backend in production.
// During local dev the /api proxy forwards to the FastAPI server on :8000.
export default defineConfig({
  plugins: [react()],
  build: {
    outDir: "dist",
    emptyOutDir: true,
  },
  server: {
    port: 5173,
    proxy: {
      "/api": {
        target: "http://localhost:8000",
        changeOrigin: true,
      },
    },
  },
});
