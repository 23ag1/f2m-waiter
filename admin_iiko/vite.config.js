import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  base: '/iiko-admin/',
  plugins: [react(), tailwindcss()],
  server: {
    port: 3000,
    proxy: {
      '/iiko': {
        target: 'https://api-ru.iiko.services',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/iiko/, ''),
        secure: true,
      }
    }
  }
})
