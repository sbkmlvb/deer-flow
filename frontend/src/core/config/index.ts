import { env } from "@/env";

// 默认配置
const DEFAULT_GATEWAY_PORT = 8001;
const DEFAULT_FRONTEND_PORT = 3001;

export function getBackendBaseURL() {
  if (env.NEXT_PUBLIC_BACKEND_BASE_URL) {
    return env.NEXT_PUBLIC_BACKEND_BASE_URL;
  }
  // 默认使用 Gateway 地址
  if (typeof window !== "undefined") {
    const currentPort = window.location.port;
    // 如果前端在 3001 端口，后端在 8001
    if (currentPort === String(DEFAULT_FRONTEND_PORT)) {
      return `http://${window.location.hostname}:${DEFAULT_GATEWAY_PORT}`;
    }
    // 否则使用相同 origin（nginx 代理）
    return window.location.origin;
  }
  // SSR 默认值
  return `http://localhost:${DEFAULT_GATEWAY_PORT}`;
}

export function getLangGraphBaseURL(isMock?: boolean) {
  if (env.NEXT_PUBLIC_LANGGRAPH_BASE_URL) {
    return env.NEXT_PUBLIC_LANGGRAPH_BASE_URL;
  } else if (isMock) {
    if (typeof window !== "undefined") {
      return `${window.location.origin}/mock/api`;
    }
    return `http://localhost:${DEFAULT_FRONTEND_PORT}/mock/api`;
  } else {
    // LangGraph SDK requires a full URL
    if (typeof window !== "undefined") {
      const currentPort = window.location.port;
      // 如果前端在 3001 端口，Gateway 在 8001
      if (currentPort === String(DEFAULT_FRONTEND_PORT)) {
        return `http://${window.location.hostname}:${DEFAULT_GATEWAY_PORT}/api/langgraph`;
      }
      // 否则使用相对路径（nginx 代理）
      return `${window.location.origin}/api/langgraph`;
    }
    // SSR 默认值 - 使用 Gateway 端口
    return `http://localhost:${DEFAULT_GATEWAY_PORT}/api/langgraph`;
  }
}
