<script setup lang="ts">
import { ref, onMounted, computed } from "vue";
import { NTable, NTag, NButton, useMessage } from "naive-ui";
import { useRouter, useRoute } from "vue-router";
import MainLayout from "@/components/layout/MainLayout.vue";
import { apiClient } from "@/api/client";

const msg = useMessage();
const router = useRouter();
const route = useRoute();
const queue = ref<any[]>([]);
const myTickets = ref<any[]>([]);
const loading = ref(false);
const isMine = computed(() => route.name === "support-mine");

async function loadQueue() {
  loading.value = true;
  try {
    const [qRes, myRes, doneRes] = await Promise.all([
      apiClient.get<any>("/support/queue?status=pending"),
      apiClient.get<any>("/support/my"),
      apiClient.get<any>("/support/queue?status=completed"),
    ]);
    if (qRes.data) queue.value = (qRes.data as any).items || [];
    if (myRes.data) myTickets.value = (myRes.data as any).items || [];
    if (doneRes.data) {
      const doneItems = (doneRes.data as any).items || [];
      if (doneItems.length > 0) myTickets.value.push(...doneItems);
    }
  } finally {
    loading.value = false;
  }
}

async function claim(ticketId: number) {
  try {
    const res = await apiClient.post<any>(`/support/claim/${ticketId}`);
    msg.success("已认领");
    const sessionId = res.data?.session_id;
    if (sessionId) {
      router.push({ name: "support-chat", query: { session: sessionId } });
    }
    await loadQueue();
  } catch (e: any) {
    msg.error(e.message || "操作失败");
  }
}

function enterTicket(t: any) {
  if (t.session_id) {
    router.push({ name: "support-chat", query: { session: t.session_id } });
  }
}

async function complete(ticketId: number) {
  try {
    await apiClient.post(`/support/complete/${ticketId}`);
    msg.success("已完成");
    await loadQueue();
  } catch (e: any) {
    msg.error(e.message || "操作失败");
  }
}

const statusMap: Record<string, { label: string; type: "warning" | "info" | "success" | "default" }> = {
  pending: { label: "待处理", type: "warning" },
  claimed: { label: "已认领", type: "info" },
  processing: { label: "处理中", type: "info" },
  completed: { label: "已完成", type: "success" },
  cancelled: { label: "已取消", type: "default" },
};

onMounted(loadQueue);
</script>

<template>
  <MainLayout :title="isMine ? '我的工单' : '待处理队列'">
    <div class="p-6">
      <div class="flex justify-between items-center mb-4">
        <h2 class="text-lg font-semibold">{{ isMine ? "我的工单" : "待处理队列" }}</h2>
        <n-button @click="loadQueue" :loading="loading" size="small">刷新</n-button>
      </div>

      <!-- 待处理队列 -->
      <template v-if="!isMine">
        <n-table :loading="loading" :single-line="false">
          <thead><tr><th>ID</th><th>用户</th><th>问题</th><th>状态</th><th>时间</th><th>操作</th></tr></thead>
          <tbody>
            <tr v-for="t in queue" :key="t.id">
              <td class="text-xs text-gray-400">#{{ t.id }}</td>
              <td class="font-medium">{{ t.username }}</td>
              <td class="max-w-[200px] truncate">{{ t.query }}</td>
              <td><n-tag :type="statusMap[t.status]?.type || 'default'" size="small">{{ statusMap[t.status]?.label || t.status }}</n-tag></td>
              <td class="text-xs text-gray-400">{{ t.created_at?.slice(0, 16) }}</td>
              <td><n-button text size="small" type="primary" @click="claim(t.id)">进入</n-button></td>
            </tr>
            <tr v-if="queue.length === 0"><td colspan="6" class="text-center py-12 text-gray-400">暂无待处理请求</td></tr>
          </tbody>
        </n-table>
      </template>

      <!-- 我的工单 -->
      <template v-else>
        <n-table :loading="loading" :single-line="false">
          <thead><tr><th>ID</th><th>用户</th><th>问题</th><th>状态</th><th>时间</th><th>操作</th></tr></thead>
          <tbody>
            <tr v-for="t in myTickets" :key="t.id">
              <td class="text-xs text-gray-400">#{{ t.id }}</td>
              <td class="font-medium">{{ t.username }}</td>
              <td class="max-w-[200px] truncate">{{ t.query }}</td>
              <td><n-tag :type="statusMap[t.status]?.type || 'default'" size="small">{{ statusMap[t.status]?.label || t.status }}</n-tag></td>
              <td class="text-xs text-gray-400">{{ t.created_at?.slice(0, 16) }}</td>
              <td>
                <div class="flex gap-1">
                  <n-button text size="small" type="primary" @click="enterTicket(t)">进入</n-button>
                  <n-button text size="small" type="success" @click="complete(t.id)">完成</n-button>
                </div>
              </td>
            </tr>
            <tr v-if="myTickets.length === 0"><td colspan="6" class="text-center py-12 text-gray-400">暂无工单</td></tr>
          </tbody>
        </n-table>
      </template>
    </div>
  </MainLayout>
</template>
