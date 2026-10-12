import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// In dev, the API (uvicorn on :8000) serves /ui-api; Vite proxies to it.
export default defineConfig({
  plugins: [react()],
  build: {
    // Monaco is large; keep it in its own long-cached chunk.
    chunkSizeWarningLimit: 3000,
    rollupOptions: { output: { manualChunks: { monaco: ["monaco-editor/esm/vs/editor/editor.api"] } } },
  },
  server: {
    proxy: { "/ui-api": "http://localhost:8000" },
  },
});
