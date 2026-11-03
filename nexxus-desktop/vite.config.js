import { defineConfig } from 'vite';

export default defineConfig({
  root: '.',
  publicDir: false,
  build: {
    outDir: '../src-tauri/gen',
    emptyOutDir: true,
  },
  server: {
    port: 1420,
    strictPort: true,
  },
});
