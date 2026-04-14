import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port: 5307,
    host: "0.0.0.0",
    allowedHosts: ["callisto.works", "www.callisto.works"],
    hmr: {
      clientPort: 443,
      protocol: "wss",
    },
  },
});
