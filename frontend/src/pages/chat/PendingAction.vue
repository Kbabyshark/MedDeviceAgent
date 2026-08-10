<script setup lang="ts">
import { ref, computed, watch } from "vue";
import { NCard, NButton, NSpace, NTag, useMessage } from "naive-ui";
import { apiClient } from "@/api/client";
import { useAuthStore } from "@/stores/auth";
import { useChatStore } from "@/stores/chat";

const auth = useAuthStore();
const chat = useChatStore();
const msg = useMessage();
const confirming = ref(false);
const resolved = ref(false);
const RESOLVED_KEY = "svagent_resolved_sessions";

// 检测最后一条 system 消息是否包含待确认操作
const pendingMessage = computed(() => {
  return [...chat.messages].reverse().find((m) => m.content?.includes("待确认")) || null;
});

const showConfirm = computed(() => {
  if (resolved.value) return false;
  const pm = pendingMessage.value;
  if (!pm?.content?.includes("待确认")) return false;
  // localStorage 防刷新
  const done = JSON.parse(localStorage.getItem(RESOLVED_KEY) || "[]");
  if (done.includes(chat.currentSessionId)) return false;
  return true;
});

const actionType = computed(() => {
  const content = pendingMessage.value?.content || "";
  if (content.includes("保修")) return "create_warranty";
  if (content.includes("工单")) return "create_ticket";
  if (content.includes("人工")) return "transfer_human";
  return "unknown";
});

// pending 消息后有新消息 → 自动标记已处理
watch(
  () => chat.messages.length,
  () => {
    const pm = pendingMessage.value;
    if (!pm) return;
    const idx = chat.messages.lastIndexOf(pm);
    if (idx >= 0 && idx < chat.messages.length - 1) {
      markResolved();
    }
  },
);

function markResolved() {
  const list = JSON.parse(localStorage.getItem(RESOLVED_KEY) || "[]");
  if (!list.includes(chat.currentSessionId)) {
    list.push(chat.currentSessionId);
    localStorage.setItem(RESOLVED_KEY, JSON.stringify(list.slice(-20))); // 只保留最近20条
  }
  resolved.value = true;
}

function extractDraftInfo(): { device_sn: string; problem_desc: string } {
  const content = pendingMessage.value?.content || "";
  const snMatch = content.match(/设备序列号[：:]\s*(\S+)/);
  const descMatch = content.match(/问题描述[：:]\s*(.+)/);
  return {
    device_sn: snMatch?.[1] || "",
    problem_desc: descMatch?.[1] || "",
  };
}

async function handleConfirm(confirm: boolean) {
  confirming.value = true;
  try {
    const type = actionType.value;

    if (type === "transfer_human") {
      if (confirm) {
        chat.directMode = true;
        localStorage.setItem("svagent_direct", "1");
        await apiClient.post("/support/transfer", {
          user_id: auth.userId, session_id: chat.currentSessionId,
          username: auth.username, query: pendingMessage.value?.content || "用户请求人工客服",
        });
      }
      chat.addMessage("assistant", confirm
        ? "正在为您转接人工客服，已通知在线客服，请稍候…"
        : "好的，已取消转接。请问还有其他需要帮您的吗？"
      );
    } else if (type === "create_warranty") {
      const { device_sn, problem_desc } = extractDraftInfo();
      await apiClient.post("/warranty/confirm", { device_sn, user_id: auth.userId, problem_desc, confirm });
      chat.addMessage("assistant", confirm
        ? `已为您登记设备保修。\n\n设备序列号：${device_sn}\n问题描述：${problem_desc}\n保修生效日：今天\n\n售后工程师后续会跟进处理，请保持电话畅通。`
        : "已取消本次保修登记。如需重新登记，请告诉我设备序列号和问题。"
      );
    } else {
      msg.success(confirm ? "已确认" : "已取消");
    }
  } catch (e) {
    msg.error(e instanceof Error ? e.message : "操作失败，请重试");
  } finally {
    markResolved();
    confirming.value = false;
  }
}
</script>

<template>
  <div v-if="showConfirm" class="px-4 py-2">
    <n-card size="small" :class="actionType === 'transfer_human' ? 'bg-blue-50 border-blue-200' : 'bg-yellow-50 border-yellow-200'">
      <div class="flex items-start gap-3">
        <span class="text-xl mt-0.5">{{ actionType === "transfer_human" ? "👤" : actionType === "create_warranty" ? "🛡️" : "📋" }}</span>
        <div class="flex-1">
          <div class="flex items-center gap-2 mb-1">
            <span class="font-medium text-sm">
              {{ actionType === "create_warranty" ? "确认保修登记" : actionType === "create_ticket" ? "确认创建工单" : "确认转接人工" }}
            </span>
            <n-tag :type="actionType === 'create_warranty' ? 'success' : actionType === 'create_ticket' ? 'warning' : 'info'" size="small">
              待确认
            </n-tag>
          </div>
          <p class="text-sm text-gray-600 mb-3 whitespace-pre-wrap">{{ pendingMessage?.content }}</p>
          <n-space>
            <n-button type="primary" size="small" :loading="confirming" @click="handleConfirm(true)">
              {{ actionType === "create_warranty" ? "✓ 确认登记" : actionType === "create_ticket" ? "✓ 确认创建" : "✓ 确认转接" }}
            </n-button>
            <n-button size="small" :disabled="confirming" @click="handleConfirm(false)">
              取消
            </n-button>
          </n-space>
        </div>
      </div>
    </n-card>
  </div>
</template>
