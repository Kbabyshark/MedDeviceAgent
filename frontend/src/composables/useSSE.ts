/**
 * SSE 流式接收 Composable。
 *
 * 解析后端 SSE 事件流，逐事件回调。
 */

import { ref } from "vue";
import { apiClient } from "@/api/client";
import type { ChatRequest, StreamEvent } from "@/types";
import { useChatStore } from "@/stores/chat";

export function useSSE() {
  const isStreaming = ref(false);
  const currentNode = ref("");
  const error = ref<string | null>(null);
  const chatStore = useChatStore();

  let onEndCb: ((text: string) => void) | null = null;
  function onEnd(fn: (text: string) => void) { onEndCb = fn; }

  async function sendMessage(req: ChatRequest): Promise<void> {
    isStreaming.value = true;
    error.value = null;
    chatStore.isStreaming = true;

    let answerBuffer = "";
    chatStore.addMessage("assistant", "");

    try {
      const stream = await apiClient.stream("/chat/stream", req);
      const reader = stream.getReader();
      const decoder = new TextDecoder();

      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });

        // 解析 SSE 事件（以 \n\n 分隔）
        const events = buffer.split("\n\n");
        buffer = events.pop() || "";  // 最后一段可能不完整

        for (const eventBlock of events) {
          const event = parseSSEEvent(eventBlock);
          if (!event) continue;
          console.log("[SSE] 事件:", event.event, JSON.stringify(event.data).slice(0, 80));

          switch (event.event) {
            case "start":
              break;

            case "node":
              chatStore.currentNode = event.data["node"] as string;
              break;

            case "token":
              answerBuffer += (event.data["content"] || event.data["text"]) as string;
              chatStore.updateLastMessage(answerBuffer);
              break;

            case "tool_call":
              break;

            case "tool_result":
              break;

            case "human_confirm_required":
              chatStore.addMessage("system", `待确认: ${event.data["message"] || ""}`);
              break;

            case "error":
              error.value = (event.data["detail"] || event.data["message"]) as string;
              break;

            case "done":
              answerBuffer = (event.data["answer"] as string) || answerBuffer;
              chatStore.updateLastMessage(answerBuffer || "处理完成");
              onEndCb?.(answerBuffer);
              break;
          }
        }
      }
    } catch (e) {
      error.value = e instanceof Error ? e.message : "流式连接中断";
      chatStore.updateLastMessage(answerBuffer || "回答生成中断，请重试");
    } finally {
      isStreaming.value = false;
      chatStore.isStreaming = false;
      chatStore.currentNode = "";
    }
  }

  function parseSSEEvent(block: string): StreamEvent | null {
    const lines = block.split("\n");
    let eventType = "";
    let dataStr = "";

    for (const line of lines) {
      if (line.startsWith("event:")) {
        eventType = line.slice(6).trim();
      } else if (line.startsWith("data:")) {
        dataStr = line.slice(5).trim();
      }
    }

    if (!eventType || !dataStr) return null;

    try {
      return {
        event: eventType as StreamEvent["event"],
        data: JSON.parse(dataStr),
      };
    } catch {
      return null;
    }
  }

  return { isStreaming, currentNode, error, sendMessage, onEnd };
}
