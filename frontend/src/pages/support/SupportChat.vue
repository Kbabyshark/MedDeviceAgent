<script setup lang="ts">
import { ref, onMounted, onUnmounted, computed } from "vue";
import { useRoute, useRouter } from "vue-router";
import { NButton, NTag, NIcon, NDivider, useMessage } from "naive-ui";
import { CheckmarkCircleOutline } from "@vicons/ionicons5";
import MainLayout from "@/components/layout/MainLayout.vue";
import MessageList from "@/pages/chat/MessageList.vue";
import ChatInput from "@/pages/chat/ChatInput.vue";
import { useChatStore } from "@/stores/chat";
import { apiClient } from "@/api/client";
import { useChatWS } from "@/composables/useChatWS";

const route = useRoute();
const router = useRouter();
const msg = useMessage();
const chat = useChatStore();
const { connect, disconnect } = useChatWS();

const tickets = ref<any[]>([]);
const currentTicket = ref<any>(null);
const loading = ref(false);

const pendingTickets = computed(() => tickets.value.filter((t) => t.status === "pending" || t.status === "claimed"));
const doneTickets = computed(() => tickets.value.filter((t) => t.status === "completed"));

async function loadTickets() {
  try {
    const [qRes, myRes, doneRes] = await Promise.all([
      apiClient.get<any>("/support/queue?status=pending&page_size=100"),
      apiClient.get<any>("/support/my"),
      apiClient.get<any>("/support/queue?status=completed&page_size=100"),
    ]);
    const queueItems = (qRes.data as any)?.items || [];
    const myItems = (myRes.data as any)?.items || [];
    const doneItems = (doneRes.data as any)?.items || [];
    tickets.value = [...queueItems, ...myItems, ...doneItems];
  } catch { /* ignore */ }
}

async function selectTicket(t: any) {
  disconnect();
  currentTicket.value = t;
  chat.currentSessionId = t.session_id;
  chat.messages = [];
  try {
    const res = await apiClient.get<any>(`/support/session/${t.session_id}/messages`);
    if (res.data) {
      chat.messages = (res.data as any).items || [];
    }
  } catch { /* 会话可能无消息 */ }
  connect(t.session_id);
}

async function completeTicket(id: number) {
  try {
    await apiClient.post(`/support/complete/${id}`);
    msg.success("已完成");
    const found = tickets.value.find((t) => t.id === id);
    if (found) found.status = "completed";
  } catch (e: any) {
    msg.error(e.message || "操作失败");
  }
}

onMounted(async () => {
  await loadTickets();
  const sid = route.query.session as string;
  if (sid) {
    const t = tickets.value.find((x) => x.session_id === sid);
    if (t) await selectTicket(t);
  }
});

onUnmounted(() => {
  disconnect();
});
</script>

<template>
  <MainLayout title="客服对话">
    <div class="flex h-full">
      <!-- 工单列表 -->
      <div class="w-60 border-r bg-gray-50 flex-shrink-0 flex flex-col">
        <!-- 待处理 -->
        <div class="flex-1 overflow-y-auto">
          <div class="px-3 py-2">
            <p class="text-xs text-orange-500 font-semibold uppercase mb-1">
              ⏳ 待处理 ({{ pendingTickets.length }})
            </p>
            <div
              v-for="t in pendingTickets"
              :key="t.id"
              class="px-2 py-1.5 mb-1 cursor-pointer rounded text-xs"
              :class="[
                currentTicket?.id === t.id ? 'bg-blue-100' : 'bg-orange-50 hover:bg-orange-100',
                'border-l-2',
                currentTicket?.id === t.id ? 'border-blue-400' : 'border-orange-400',
              ]"
              @click="selectTicket(t)"
            >
              <div class="flex justify-between items-center">
                <span class="font-medium truncate flex-1">{{ t.username }}</span>
                <n-tag :type="t.status === 'pending' ? 'warning' : 'info'" size="tiny">
                  {{ t.status === 'pending' ? '待认领' : '已认领' }}
                </n-tag>
              </div>
              <div class="text-gray-500 truncate mt-0.5">{{ t.query?.slice(0, 30) }}</div>
            </div>
            <div v-if="pendingTickets.length === 0" class="text-gray-400 text-xs text-center py-4">
              暂无待处理
            </div>
          </div>

          <n-divider style="margin: 0" />

          <!-- 已完成 -->
          <div class="px-3 py-2">
            <p class="text-xs text-gray-400 font-semibold uppercase mb-1">
              ✓ 已完成 ({{ doneTickets.length }})
            </p>
            <div
              v-for="t in doneTickets"
              :key="t.id"
              class="px-2 py-1 mb-1 rounded text-xs cursor-pointer hover:bg-gray-100"
              :class="{ 'bg-blue-50': currentTicket?.id === t.id }"
              @click="selectTicket(t)"
            >
              <div class="font-medium text-gray-600 truncate">{{ t.username }}</div>
              <div class="text-gray-400 truncate">{{ t.query?.slice(0, 30) }}</div>
            </div>
          </div>
        </div>
      </div>

      <!-- 对话区 -->
      <div class="flex-1 flex flex-col min-w-0">
        <template v-if="currentTicket">
          <!-- 顶部信息条 -->
          <div class="px-4 py-2 border-b bg-white flex items-center justify-between text-sm">
            <div class="flex items-center gap-3">
              <span class="font-medium">{{ currentTicket.username }}</span>
              <n-tag :type="currentTicket.status === 'completed' ? 'success' : 'warning'" size="small">
                {{ currentTicket.status === 'pending' ? '待认领' : currentTicket.status === 'claimed' ? '处理中' : '已完成' }}
              </n-tag>
              <span class="text-gray-400 text-xs">#{{ currentTicket.id }}</span>
            </div>
            <n-button
              v-if="currentTicket.status !== 'completed'"
              size="small"
              type="success"
              @click="completeTicket(currentTicket.id)"
            >
              <template #icon><n-icon><CheckmarkCircleOutline /></n-icon></template>
              完成工单
            </n-button>
          </div>
          <MessageList class="flex-1 min-h-0" :is-support="true" />
          <ChatInput v-if="currentTicket.status !== 'completed'" :is-support="true" />
          <div v-else class="px-4 py-3 text-center text-gray-400 text-sm border-t">
            此工单已完成，对话已关闭
          </div>
        </template>
        <div v-else class="flex-1 flex items-center justify-center text-gray-400">
          选择左侧的工单开始对话
        </div>
      </div>
    </div>
  </MainLayout>
</template>
