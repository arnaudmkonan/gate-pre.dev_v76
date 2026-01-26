import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Detect if running inside Docker (the 'api' hostname will resolve)
// In Docker: proxy to http://api:8000
// Local dev: proxy to http://localhost:8000
const isDocker = process.env.DOCKER_ENV === 'true'
const apiTarget = isDocker ? 'http://api:8000' : 'http://localhost:8000'

export default defineConfig({
  plugins: [react()],
  server: {
    host: '0.0.0.0',
    port: 3000,
    allowedHosts: ['gate-pre-dev-6abf.pre.dev', 'localhost', '127.0.0.1'],
    watch: {
      usePolling: true, // Required for Docker volume mounts
    },
    proxy: {
      '/api': {
        target: apiTarget,
        changeOrigin: true,
        rewrite: (path) => path,
      },
      '/agents': {
        target: apiTarget,
        changeOrigin: true,
        rewrite: (path) => path,
      },
      '/batch': {
        target: apiTarget,
        changeOrigin: true,
        rewrite: (path) => path,
      },
    },
  },
})

