import { defineStore } from "pinia";
import { ref } from "vue";
import type { MessageItem, SessionInfo } from "@/types";
import { apiClient } from "@/api/client";

export const useChatStore = defineStore("chat", () => {
  const sessions = ref<SessionInfo[]>([]);
  const currentSessionId = ref<string>("");
  const messages = ref<MessageItem[]>([]);
  const isLoading = ref(false);
  const currentNode = ref<string>("");       // SSE 推送的当前节点名
  const isStreaming = ref(false);           // 是否正在流式接收
  const directMode = ref(localStorage.getItem("svagent_direct") === "1");
  const readOnly = ref(false);               // 会话完成封存，只读
  const selectedDevice = ref<string>("");   // 当前选中的设备型号
  const deviceOptions = ref<string[]>([]);  // 可选设备列表

  async function createSession(): Promise<string> {
    const res = await apiClient.post<SessionInfo>("/session/create", {});
    const sessionId = res.data?.session_id || "";
    if (sessionId) {
      currentSessionId.value = sessionId;
      messages.value = [];
      directMode.value = false;
      readOnly.value = false;
      localStorage.removeItem("svagent_direct");
      await loadSessions();
    }
    return sessionId;
  }

  async function loadSessions(page = 1): Promise<void> {
    try {
      const res = await apiClient.get<SessionInfo[]>(`/sessions?page=${page}&page_size=50`);
      if (res.data) {
        const items = Array.isArray(res.data) ? res.data : (res.data as any).items || [];
        if (items.length > 0 || sessions.value.length === 0) {
          sessions.value = items;
        }
      }
    } catch { /* 不覆盖已有列表 */ }
  }

  async function loadMessages(sessionId: string, page = 1): Promise<void> {
    const res = await apiClient.get<MessageItem[]>(
      `/session/${sessionId}/messages?page=${page}&page_size=50`
    );
    if (res.data) {
      // @ts-expect-error paginated
      const items = Array.isArray(res.data) ? res.data : (res.data as any).items || [];
      if (page === 1) {
        messages.value = items;
      } else {
        // 向上加载历史：旧消息插入到前面
        messages.value = [...items, ...messages.value];
      }
    }
  }

  function addMessage(role: string, content: string): void {
    messages.value.push({
      role: role as MessageItem["role"],
      content,
      created_at: new Date().toISOString(),
    });
  }

  function updateLastMessage(content: string): void {
    const last = messages.value[messages.value.length - 1];
    if (last && last.role === "assistant") {
      last.content = content;
    }
  }

  function selectSession(sessionId: string): void {
    currentSessionId.value = sessionId;
  }

  async function loadDevices(): Promise<void> {
    try {
      const res = await apiClient.get<{ device_type: string }[]>("/devices");
      if (res.data && Array.isArray(res.data)) {
        deviceOptions.value = (res.data as any).map((d: any) => d.device_type || d);
      }
    } catch { /* 设备列表为空时不报错 */ }
  }

  return {
    sessions, currentSessionId, messages, isLoading, currentNode, isStreaming,
    directMode, readOnly, selectedDevice, deviceOptions,
    createSession, loadSessions, loadMessages, addMessage, updateLastMessage, selectSession,
    loadDevices,
  };
});
