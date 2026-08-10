<script setup lang="ts">
import { ref, computed } from "vue";
import { NInput, NButton, NIcon, NSelect, useMessage } from "naive-ui";
import { SendOutline } from "@vicons/ionicons5";
import { useChatStore } from "@/stores/chat";
import { apiClient } from "@/api/client";
import { useSSE } from "@/composables/useSSE";
import { useChatWS } from "@/composables/useChatWS";

const props = defineProps<{ isSupport?: boolean }>();
const chat = useChatStore();
const { isStreaming, sendMessage } = useSSE();
const { send: wsSend } = useChatWS();

const toast = useMessage();

const inputText = ref("");
const inputRef = ref<InstanceType<typeof NInput>>();

// 有未处理的确认操作时禁用输入（待确认消息是最后一条才禁，客服端不受限）
const hasPending = computed(() => {
  if (props.isSupport) return false;
  const last = chat.messages[chat.messages.length - 1];
  return last?.content?.includes("待确认") || false;
});

// ---- 文本 ----
async function handleSend() {
  const text = inputText.value.trim();
  if (!text || isStreaming.value || hasPending.value) return;
  inputText.value = "";

  if (!chat.currentSessionId) {
    try { await chat.createSession(); } catch { toast.error("创建会话失败"); return; }
  }

  // 客服模式 或 转人工后直连模式：WebSocket 实时发送
  if (props.isSupport || chat.directMode) {
    const role = props.isSupport ? "assistant" : "user";
    chat.addMessage(role, text);
    wsSend(role, text);
    return;
  }

  // 普通模式：SSE Agent 流式回复
  chat.addMessage("user", text);
  sendMessage({ session_id: chat.currentSessionId, message: text, device_type: chat.selectedDevice || undefined });
}

function handleKeydown(e: KeyboardEvent) {
  if (e.key === "Enter" && !e.shiftKey && document.activeElement === inputRef.value) {
    e.preventDefault();
    handleSend();
  }
}
</script>

<template>
  <div v-if="chat.readOnly" class="border-t bg-gray-50 px-4 py-3 text-center text-sm text-gray-400">
    此会话已结束，对话已封存
  </div>
  <div v-else class="border-t bg-white px-4 py-3">
    <div class="flex items-end gap-2 max-w-4xl mx-auto">
      <n-select
        v-model:value="chat.selectedDevice"
        :options="[{ label: '全部设备', value: '' }, ...chat.deviceOptions.map(d => ({ label: d, value: d }))]"
        placeholder="设备型号"
        style="width: 150px"
        size="small"
        clearable
      />

      <n-input
        ref="inputRef"
        v-model:value="inputText"
        type="textarea"
        placeholder="输入消息… (Enter 发送)"
        :autosize="{ minRows: 1, maxRows: 5 }"
        :disabled="isStreaming || hasPending"
        @keydown="handleKeydown"
      />

      <n-button type="primary" :disabled="!inputText.trim() || isStreaming || hasPending" :loading="isStreaming" @click="handleSend">
        <template #icon><n-icon><SendOutline /></n-icon></template>
      </n-button>
    </div>
    <p class="text-xs text-gray-400 mt-1 text-center">
      按住 <kbd class="px-1 border rounded text-[10px]">T</kbd> 键说话 · Enter 发送 · 回答仅供参考
    </p>
  </div>
</template>
