import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";

// React frontend dev server: http://localhost:3000
// /api requests are proxied to the Flask backend (default http://127.0.0.1:5000).
// Override the backend with BACKEND_URL in Frontend/.env if needed.
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "");

  return {
    plugins: [react()],
    server: {
      host: true,       // listen on 0.0.0.0 so localhost AND 127.0.0.1 both work
      port: 3000,
      strictPort: true, // fail instead of silently switching to another port
      open: true,      // open the browser on `npm run dev`
      proxy: {
        "/api": {
          target: env.BACKEND_URL || "http://127.0.0.1:5000",
          changeOrigin: true,
        },
      },
    },
    preview: {
      host: true,
      port: 3000,
      strictPort: true,
    },
  };
});
