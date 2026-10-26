import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, ".", "VITE_");
  return {
    plugins: [react(), tailwindcss()],
    server: {
      strictPort: true,
      port: Number(env.VITE_PORT || 5173),
      proxy: {
        "/api": env.VITE_API_PROXY_TARGET || "http://127.0.0.1:8000",
        "/health": env.VITE_API_PROXY_TARGET || "http://127.0.0.1:8000",
      },
    },
  };
});
