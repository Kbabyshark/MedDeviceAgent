/**
 * WebSocket 实时聊天 Composable（单例模式）。
 * 连接 ws://host/api/v1/ws/chat/{sessionId}?token=xxx
 */

import { ref } from "vue";
import { useAuthStore } from "@/stores/auth";
import { useChatStore } from "@/stores/chat";

// 单例状态
let ws: WebSocket | null = null;
let reconnectTimer: ReturnType<typeof setTimeout> | null = null;
const isConnected = ref(false);

function getWsUrl(sessionId: string, token: string): string {
  const proto = location.protocol === "https:" ? "wss" : "ws";
  return `${proto}://${location.host}/api/v1/ws/support-chat/${sessionId}?token=${token}`;
}

export function useChatWS() {
  const auth = useAuthStore();
  const chat = useChatStore();

  function connect(sessionId: string) {
    if (!sessionId || !auth.token) return;
    if (ws && ws.readyState === WebSocket.OPEN) return;

    ws = new WebSocket(getWsUrl(sessionId, auth.token));

    ws.onopen = () => { isConnected.value = true; };

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        console.log("[WS] received:", data.type, data.content?.slice(0, 30));
        if (data.type === "message") {
          chat.addMessage(data.role, data.content);
        } else if (data.type === "completed") {
          chat.directMode = false;
          chat.readOnly = true;
          localStorage.removeItem("svagent_direct");
          chat.addMessage("system", data.content || "客服已结束本次服务");
        }
      } catch { /* ignore */ }
    };

    ws.onclose = () => {
      isConnected.value = false;
      ws = null;
      if (chat.currentSessionId === sessionId) {
        reconnectTimer = setTimeout(() => connect(sessionId), 3000);
      }
    };

    ws.onerror = () => { ws?.close(); };
  }

  function disconnect() {
    if (reconnectTimer) { clearTimeout(reconnectTimer); reconnectTimer = null; }
    if (ws) { ws.close(); ws = null; }
    isConnected.value = false;
  }

  function send(role: string, content: string) {
    console.log("[WS] send attempt, readyState:", ws?.readyState, "OPEN=", WebSocket.OPEN);
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ type: "message", role, content }));
      console.log("[WS] sent:", content.slice(0, 30));
    } else {
      console.warn("[WS] NOT sent - ws is null or not OPEN");
    }
  }

  return { isConnected, connect, disconnect, send };
}
