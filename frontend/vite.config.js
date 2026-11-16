import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [react()],
  // in dev, /api goes to the local FastAPI app; on Vercel a rewrite does the same job
  server: { proxy: { "/api": "http://127.0.0.1:8000" } },
});
