/// <reference types="vitest/config" />
import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";
import { VitePWA } from "vite-plugin-pwa";

// Dans Docker, l'API s'appelle « api » ; hors Docker, elle est sur localhost.
const apiTarget = process.env.VITE_API_PROXY ?? "http://localhost:8000";

export default defineConfig({
  plugins: [
    react(),
    tailwindcss(),
    // Rend l'application installable sur mobile (PWA) et utilisable hors ligne.
    VitePWA({
      registerType: "autoUpdate",
      includeAssets: ["icon.svg"],
      manifest: {
        name: "SuperTracker",
        short_name: "SuperTracker",
        description: "Suivez vos séries, animes, films, livres et jeux vidéo.",
        lang: "fr",
        theme_color: "#0b0d12",
        background_color: "#0b0d12",
        display: "standalone",
        start_url: "/",
        icons: [
          { src: "icon.svg", sizes: "any", type: "image/svg+xml", purpose: "any" },
          { src: "icon.svg", sizes: "any", type: "image/svg+xml", purpose: "maskable" },
        ],
      },
    }),
  ],
  server: {
    host: true, // accessible depuis l'extérieur du conteneur
    port: 5173,
    // Sous Windows + Docker, la détection des modifications nécessite la scrutation.
    watch: { usePolling: true },
    // Les appels à /api sont transmis au backend : même origine, donc pas de CORS.
    proxy: { "/api": apiTarget },
  },
  test: {
    environment: "jsdom",
    setupFiles: ["./src/test/setup.ts"],
    testTimeout: 15_000, // machine chargée (Docker sous Windows, CI) : marge confortable
  },
});
