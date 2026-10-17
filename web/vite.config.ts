import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// /api is proxied to the FastAPI backend so the browser sees a single origin
// and the HttpOnly login cookie works without CORS.
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        rewrite: (path) => path.replace(/^\/api/, ''),
      },
    },
  },
})
