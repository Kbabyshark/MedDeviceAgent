<script setup lang="ts">
import { onMounted, onUnmounted, watch } from "vue";
import { useRoute } from "vue-router";
import MainLayout from "@/components/layout/MainLayout.vue";
import MessageList from "./MessageList.vue";
import ChatInput from "./ChatInput.vue";
import PendingAction from "./PendingAction.vue";
import SessionPanel from "./SessionPanel.vue";
import { useChatStore } from "@/stores/chat";
import { apiClient } from "@/api/client";
import { useChatWS } from "@/composables/useChatWS";

const route = useRoute();
const chat = useChatStore();
const { connect, disconnect } = useChatWS();

async function loadTargetSession(sessionId: string) {
  chat.currentSessionId = sessionId;
  if (!chat.sessions.find((s) => s.session_id === sessionId)) {
    await chat.loadSessions();
  }
  chat.selectSession(sessionId);
  await chat.loadMessages(sessionId);
  // 检测是否为人工客服会话
  await checkSupportMode(sessionId);
}

async function checkSupportMode(sid?: string) {
  const sessionId = sid || chat.currentSessionId;
  if (!sessionId) return;
  try {
    const res = await apiClient.get<any>(`/session/${sessionId}/support-status`);
    chat.directMode = res.data?.is_support === true || res.data?.is_support === 1;
    chat.readOnly = res.data?.is_completed === true; // 只有已完成才封存
  } catch { chat.directMode = false; chat.readOnly = false; }
}

// 切换会话时重连 WebSocket
watch(() => chat.currentSessionId, (sid) => {
  disconnect();
  if (sid) { connect(sid); checkSupportMode(); }
});

onMounted(async () => {
  const sid = route.query.session as string;
  if (sid) {
    await loadTargetSession(sid);
  } else {
    await chat.loadSessions();
  }
  if (chat.currentSessionId) {
    await checkSupportMode();
    connect(chat.currentSessionId);
  }
});

onUnmounted(() => {
  disconnect();
});
</script>

<template>
  <MainLayout title="智能客服对话">
    <div class="flex h-full">
      <!-- 会话列表 -->
      <div class="w-56 border-r bg-gray-50 flex-shrink-0 hidden md:block">
        <SessionPanel />
      </div>

      <!-- 对话区 -->
      <div class="flex-1 flex flex-col min-w-0">
        <MessageList class="flex-1 min-h-0" />
        <PendingAction />
        <ChatInput />
      </div>
    </div>
  </MainLayout>
</template>
