import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port: 5308,
    allowedHosts: ["callisto.vaughan.codes"],
    hmr: {
      // HMR goes through nginx, not directly to the dev server
      clientPort: 443,
      protocol: "wss",
    },
    proxy: {
      "/api": "http://localhost:5309",
      "/auth/google": "http://localhost:5309",
      "/auth/me": "http://localhost:5309",
    },
  },
});
