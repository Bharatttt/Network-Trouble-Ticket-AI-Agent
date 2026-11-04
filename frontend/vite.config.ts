import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig(({ mode }) => ({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": loadEnv(mode, process.cwd(), '').NOC_API_TARGET || "http://127.0.0.1:8000",
    },
  },
}));
