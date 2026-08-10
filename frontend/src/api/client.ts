/**
 * API 客户端 — fetch 封装 + JWT 自动注入 + 统一错误处理。
 */

import { useAuthStore } from "@/stores/auth";
import type { APIResponse } from "@/types";

const BASE_URL = "/api/v1";

class ApiClient {
  private async request<T>(
    path: string,
    options: RequestInit = {},
  ): Promise<APIResponse<T>> {
    const auth = useAuthStore();
    const headers: Record<string, string> = {
      "Content-Type": "application/json",
      ...(options.headers as Record<string, string>),
    };

    if (auth.token) {
      headers["Authorization"] = `Bearer ${auth.token}`;
    }

    const url = path.startsWith("/api") ? path : `${BASE_URL}${path}`;

    const response = await fetch(url, {
      ...options,
      headers,
    });

    if (response.status === 401) {
      auth.logout();
      throw new Error("认证已过期，请重新登录");
    }

    if (response.status === 429) {
      throw new Error("请求过于频繁，请稍后重试");
    }

    const data = await response.json();

    if (!response.ok) {
      const msg = data.detail || data.message || `请求失败 (${response.status})`;
      throw new Error(msg);
    }

    return data as APIResponse<T>;
  }

  // ---- HTTP 方法 ----
  async get<T>(path: string, params?: Record<string, string>): Promise<APIResponse<T>> {
    let url = path;
    if (params) {
      const qs = new URLSearchParams(params).toString();
      url = `${path}?${qs}`;
    }
    return this.request<T>(url, { method: "GET" });
  }

  async post<T>(path: string, body?: unknown): Promise<APIResponse<T>> {
    return this.request<T>(path, {
      method: "POST",
      body: body ? JSON.stringify(body) : undefined,
    });
  }

  async postForm<T>(path: string, formData: FormData): Promise<APIResponse<T>> {
    const auth = useAuthStore();
    const headers: Record<string, string> = {};
    if (auth.token) {
      headers["Authorization"] = `Bearer ${auth.token}`;
    }

    const url = path.startsWith("/api") ? path : `${BASE_URL}${path}`;
    const response = await fetch(url, {
      method: "POST",
      headers,
      body: formData,
    });

    if (response.status === 401) {
      auth.logout();
      throw new Error("认证已过期");
    }

    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.message || "上传失败");
    }
    return data as APIResponse<T>;
  }

  async put<T>(path: string, body?: unknown): Promise<APIResponse<T>> {
    return this.request<T>(path, {
      method: "PUT",
      body: body ? JSON.stringify(body) : undefined,
    });
  }

  async del<T>(path: string): Promise<APIResponse<T>> {
    return this.request<T>(path, { method: "DELETE" });
  }

  /**
   * SSE 流式请求 — 返回 ReadableStream 用于逐条解析事件。
   */
  async stream(path: string, body: unknown): Promise<ReadableStream<Uint8Array>> {
    const auth = useAuthStore();

    const url = path.startsWith("/api") ? path : `${BASE_URL}${path}`;
    const response = await fetch(url, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${auth.token}`,
      },
      body: JSON.stringify(body),
    });

    if (!response.ok) {
      if (response.status === 401) {
        auth.logout();
      }
      throw new Error(`流式请求失败 (${response.status})`);
    }

    return response.body!;
  }
}

export const apiClient = new ApiClient();
