<script setup lang="ts">
import { NButton, NIcon, NPopconfirm, useMessage } from "naive-ui";
import { AddCircleOutline, TrashOutline } from "@vicons/ionicons5";
import { useChatStore } from "@/stores/chat";
import { sessionApi } from "@/api/session";
import { apiClient } from "@/api/client";

const chat = useChatStore();
const msg = useMessage();

async function handleNewChat() {
  try {
    const res = await sessionApi.create();
    const sessionId = res.data?.session_id || "";
    if (sessionId) {
      chat.currentSessionId = sessionId;
      chat.messages = [];
      await chat.loadSessions();
      msg.success("新会话已创建");
    } else {
      msg.error("创建会话失败");
    }
  } catch (e: any) {
    msg.error("创建会话失败: " + (e.message || "网络错误"));
  }
}

async function handleSelectSession(id: string) {
  chat.selectSession(id);
  chat.messages = [];
  await chat.loadMessages(id);
}

async function handleDeleteSession(id: string) {
  try {
    await apiClient.del(`/session/${id}`);
    chat.sessions = chat.sessions.filter((s) => s.session_id !== id);
    if (chat.currentSessionId === id) {
      chat.currentSessionId = "";
      chat.messages = [];
    }
    msg.success("已删除");
  } catch {
    msg.error("删除失败");
  }
}
</script>

<template>
  <div class="flex flex-col h-full">
    <!-- New Chat -->
    <div class="p-2">
      <n-button type="primary" block size="small" @click="handleNewChat">
        <template #icon><n-icon size="16"><AddCircleOutline /></n-icon></template>
        新对话
      </n-button>
    </div>

    <!-- Session List -->
    <div class="flex-1 overflow-y-auto px-1">
      <p class="px-2 py-1 text-[11px] text-gray-400 font-medium uppercase">最近会话</p>
      <div v-if="chat.sessions.length === 0" class="px-2 py-3 text-gray-400 text-xs text-center">
        暂无会话
      </div>

      <div
        v-for="s in chat.sessions.slice(0, 20)"
        :key="s.session_id"
        class="group flex items-center px-2 py-1.5 cursor-pointer rounded hover:bg-gray-100 text-xs"
        :class="{ 'bg-blue-50': s.session_id === chat.currentSessionId }"
        @click="handleSelectSession(s.session_id)"
      >
        <span class="flex-1 truncate">
          {{ s.title || `会话 ${s.session_id.slice(-6)}` }}
        </span>

        <n-popconfirm @positive-click="handleDeleteSession(s.session_id)">
          <template #trigger>
            <n-button
              text size="tiny"
              class="opacity-0 group-hover:opacity-100 transition-opacity"
              @click.stop
            >
              <template #icon><n-icon size="12"><TrashOutline /></n-icon></template>
            </n-button>
          </template>
          确认删除？
        </n-popconfirm>
      </div>
    </div>
  </div>
</template>
