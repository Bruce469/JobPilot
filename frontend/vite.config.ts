import { fileURLToPath, URL } from 'node:url'
import { defineConfig, loadEnv } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  // 后端默认 127.0.0.1:8000，端口被占自动换端口时可通过环境变量覆盖
  const backendTarget = env.VITE_BACKEND_TARGET || 'http://127.0.0.1:8000'
  return {
    plugins: [vue()],
    resolve: {
      alias: {
        '@': fileURLToPath(new URL('./src', import.meta.url)),
      },
    },
    server: {
      host: '127.0.0.1',
      port: 5173,
      proxy: {
        // 前端所有 /api 请求代理到本地后端，避免跨域
        '/api': {
          target: backendTarget,
          changeOrigin: false,
        },
      },
    },
  }
})
