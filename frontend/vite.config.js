import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import tailwindcss from '@tailwindcss/vite';
import path from 'path';
import { fileURLToPath } from 'url';

const __dirname = fileURLToPath(new URL('.', import.meta.url));

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  build: {
    rollupOptions: {
      output: {
        // optimize_Plan.html §1.2 — split heavy/rarely-changed vendor code
        // into its own chunk so it's cached separately from app code (which
        // changes every deploy) and from each other (loaded only on the
        // routes that actually use them, per main.jsx's lazy() boundaries).
        //
        // Function form, NOT the object-map form — this project's Vite 8
        // bundles via Rolldown (not classic Rollup), which only accepts
        // `manualChunks(id)` as a function; the `{ chunkName: [...] }` map
        // shape throws "manualChunks is not a function" at build time.
        manualChunks(id) {
          if (!id.includes('node_modules')) return undefined;
          if (id.includes('@monaco-editor')) return 'vendor-monaco';
          if (id.includes('@react-sigma') || id.includes('graphology')) return 'vendor-graph';
          if (id.includes('recharts')) return 'vendor-charts';
          if (id.includes('framer-motion')) return 'vendor-motion';
          if (
            id.includes('/react/') ||
            id.includes('/react-dom/') ||
            id.includes('react-router-dom') ||
            id.includes('zustand')
          ) {
            return 'vendor-react';
          }
          return undefined;
        },
      },
    },
  },
  server: {
    port: 5173,
    proxy: {
      // Forward API calls to the FastAPI backend during development.
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
});
