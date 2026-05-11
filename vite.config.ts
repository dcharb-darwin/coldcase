import path from "node:path";
import { fileURLToPath } from "node:url";
import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

const rootDir = path.dirname(fileURLToPath(import.meta.url));

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, rootDir, "");
  // process.env takes precedence so docker-compose's VITE_PROXY_TARGET wins
  // over a stale .env file value inside the container.
  const backendPort = process.env.BACKEND_PORT || env.BACKEND_PORT || "7787";
  const frontendPort = Number(process.env.FRONTEND_PORT || env.FRONTEND_PORT) || 5178;
  // VITE_PROXY_TARGET wins (docker-compose sets it to http://backend:7787).
  // Falls back to localhost so `npm run dev` from the host still works.
  const backendTarget =
    process.env.VITE_PROXY_TARGET ||
    env.VITE_PROXY_TARGET ||
    `http://localhost:${backendPort}`;

  return {
    resolve: {
      alias: {
        "@": path.resolve(rootDir, "src"),
      },
    },
    plugins: [react(), tailwindcss()],
    server: {
      host: true,
      port: frontendPort,
      proxy: {
        "/launchpad": { target: backendTarget, changeOrigin: true },
        "/live": { target: backendTarget, changeOrigin: true },
        "/ready": { target: backendTarget, changeOrigin: true },
      },
    },
  };
});
