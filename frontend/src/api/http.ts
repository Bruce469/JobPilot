// axios 实例：统一注入 X-Auth-Token、统一错误结构解析、401 时重新 boot 刷新 token 并重试一次
import axios from 'axios'
import type { AxiosError, AxiosInstance, AxiosRequestConfig, InternalAxiosRequestConfig } from 'axios'

const TOKEN_KEY = 'job_tracker_token'

let currentToken: string | null = sessionStorage.getItem(TOKEN_KEY)

export function setToken(token: string | null): void {
  currentToken = token
  if (token) sessionStorage.setItem(TOKEN_KEY, token)
  else sessionStorage.removeItem(TOKEN_KEY)
}

export function getToken(): string | null {
  return currentToken
}

export class ApiError extends Error {
  code: string
  status: number
  details?: unknown
  constructor(message: string, code: string, status: number, details?: unknown) {
    super(message)
    this.name = 'ApiError'
    this.code = code
    this.status = status
    this.details = details
  }
}

export interface ApiErrorBody {
  error?: { code?: string; message?: string; details?: unknown }
}

interface RetriedConfig extends AxiosRequestConfig {
  _retried?: boolean
}

const http: AxiosInstance = axios.create({
  baseURL: '/api',
  timeout: 60000,
})

http.interceptors.request.use((config: InternalAxiosRequestConfig) => {
  if (currentToken) {
    config.headers.set('X-Auth-Token', currentToken)
  }
  return config
})

let refreshPromise: Promise<string | null> | null = null

/** 通过 /api/boot 重新获取 token（boot 无鉴权） */
async function refreshToken(): Promise<string | null> {
  if (!refreshPromise) {
    refreshPromise = (async () => {
      const res = await axios.get('/boot', { baseURL: '/api', timeout: 10000 })
      const token: unknown = res.data?.token
      return typeof token === 'string' ? token : null
    })().finally(() => {
      refreshPromise = null
    })
  }
  return refreshPromise
}

http.interceptors.response.use(
  (response) => response,
  async (error: AxiosError<ApiErrorBody>) => {
    const status = error.response?.status ?? 0
    const url = error.config?.url ?? ''
    const data = error.response?.data
    const config = error.config as RetriedConfig | undefined

    // 401 且非 boot：刷新 token 后重试一次（后端重启 token 会变化）
    if (status === 401 && url !== '/boot' && config && !config._retried) {
      config._retried = true
      try {
        const token = await refreshToken()
        if (token) {
          setToken(token)
          return http.request(config)
        }
      } catch {
        // boot 也失败，走下方统一错误
      }
    }

    const message =
      data?.error?.message ?? (status ? `请求失败（HTTP ${status}）` : '无法连接后端服务，请确认后端已启动')
    const code = data?.error?.code ?? (status ? 'HTTP_ERROR' : 'NETWORK_ERROR')
    return Promise.reject(new ApiError(message, code, status, data?.error?.details))
  },
)

export default http
