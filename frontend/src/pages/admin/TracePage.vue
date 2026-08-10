<script setup lang="ts">
import { ref, onMounted } from "vue";
import { NInput, NButton, NTable, NTag, NPagination } from "naive-ui";
import { useRouter } from "vue-router";
import { apiClient } from "@/api/client";

const router = useRouter();
const traceId = ref("");
const traces = ref<any[]>([]);
const total = ref(0);
const page = ref(1);
const pageSize = 20;
const loading = ref(false);

async function loadList() {
  loading.value = true;
  try {
    const res = await apiClient.get<any>(`/admin/traces?page=${page.value}&page_size=${pageSize}`);
    if (res.data) {
      traces.value = (res.data as any).items || [];
      total.value = (res.data as any).total || 0;
    }
  } finally {
    loading.value = false;
  }
}

async function search() {
  if (!traceId.value.trim()) return;
  loading.value = true;
  try {
    const res = await apiClient.get<any>(`/trace/${traceId.value}`);
    if (res.data) traces.value = [res.data];
    else traces.value = [];
  } catch {
    traces.value = [];
  } finally {
    loading.value = false;
  }
}

function viewReplay(id: string) {
  router.push(`/admin/trace/${id}`);
}

onMounted(loadList);
</script>

<template>
  <div class="p-6">
    <div class="flex justify-between items-center mb-4">
      <h2 class="text-xl font-semibold">Trace 追踪</h2>
      <div class="flex gap-2">
        <n-input v-model:value="traceId" placeholder="搜索 trace_id" style="width: 280px" clearable @keyup.enter="search" />
        <n-button type="primary" :loading="loading" @click="search">查询</n-button>
        <n-button @click="loadList">刷新列表</n-button>
      </div>
    </div>

    <n-table :loading="loading" :single-line="false">
      <thead>
        <tr>
          <th>Trace ID</th>
          <th>用户</th>
          <th>查询内容</th>
          <th>LLM 调用</th>
          <th>Token</th>
          <th>延迟(ms)</th>
          <th>状态</th>
          <th>操作</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="t in traces" :key="t.trace_id">
          <td class="text-xs font-mono">{{ t.trace_id.slice(0, 12) }}…</td>
          <td class="text-xs">{{ t.user_id }}</td>
          <td class="text-sm max-w-[200px] truncate">{{ t.query }}</td>
          <td>{{ t.llm_call_count }}</td>
          <td>{{ t.total_tokens }}</td>
          <td>{{ t.total_latency }}</td>
          <td><n-tag :type="t.status === 'success' ? 'success' : t.status === 'failed' ? 'error' : 'warning'" size="small">{{ t.status }}</n-tag></td>
          <td><n-button text size="small" type="primary" @click="viewReplay(t.trace_id)">回放</n-button></td>
        </tr>
        <tr v-if="traces.length === 0">
          <td colspan="8" class="text-center py-8 text-gray-400">暂无 Trace 记录，发几条消息后再来看</td>
        </tr>
      </tbody>
    </n-table>

    <div class="flex justify-center mt-4" v-if="total > pageSize">
      <n-pagination v-model:page="page" :page-size="pageSize" :item-count="total" @update:page="loadList" />
    </div>
  </div>
</template>
