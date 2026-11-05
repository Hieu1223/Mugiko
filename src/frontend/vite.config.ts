import { fileURLToPath, URL } from 'node:url'
import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'

const source = (path: string) => fileURLToPath(new URL(path, import.meta.url))

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  const target = env.VITE_API_PROXY_TARGET || 'http://localhost:8080'
  const proxy = {
    '/api': { target, changeOrigin: true },
    '/health': { target, changeOrigin: true },
  }

  return {
    plugins: [react()],
    resolve: {
      alias: {
        '@mugiko/common': source('./packages/common/src/index.ts'),
        '@mugiko/subtitle': source('./packages/subtitle/src/index.tsx'),
        '@mugiko/webnovel': source('./packages/webnovel/src/index.tsx'),
        '@mugiko/ai': source('./packages/ai/src/index.tsx'),
      },
    },
    server: {
      port: 5173,
      proxy,
    },
    preview: {
      port: 4173,
      proxy,
    },
  }
})
