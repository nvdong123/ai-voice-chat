import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  base: '/admin/',
  build: {
    outDir: '../admin-dist',
    emptyOutDir: true,
  },
  server: {
    port: 5173,
    proxy: {
      '/admin/login':  { target: 'http://localhost:8000', changeOrigin: true },
      '/admin/logout': { target: 'http://localhost:8000', changeOrigin: true },
      '/admin/api':    { target: 'http://localhost:8000', changeOrigin: true },
      '/admin/prompt': { target: 'http://localhost:8000', changeOrigin: true },
      '/admin/models': { target: 'http://localhost:8000', changeOrigin: true },
      '/admin/config': { target: 'http://localhost:8000', changeOrigin: true },
      '/admin/reset':  { target: 'http://localhost:8000', changeOrigin: true },
      '/admin/scenes': { target: 'http://localhost:8000', changeOrigin: true },
      '/admin/nodes':  { target: 'http://localhost:8000', changeOrigin: true },
    },
  },
});
