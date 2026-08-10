<script setup lang="ts">
import { ref, onMounted, onUnmounted } from "vue";
import { NCard, NTag, NTable, NButton, NSpace, NSpin } from "naive-ui";
import { apiClient } from "@/api/client";
import type { SystemStatus, PathPerf } from "@/types";

const status = ref<SystemStatus | null>(null);
const loading = ref(true);
const refreshing = ref(false);
let timer: ReturnType<typeof setInterval> | null = null;

async function refresh() {
  refreshing.value = true;
  try {
    const res = await apiClient.get<SystemStatus>("/status");
    status.value = res.data;
  } finally {
    loading.value = false;
    refreshing.value = false;
  }
}

onMounted(() => {
  refresh();
  // 30s 自动刷新
  timer = setInterval(refresh, 30_000);
});

onUnmounted(() => {
  if (timer) clearInterval(timer);
});
</script>

<template>
  <div class="p-6">
    <div class="flex justify-between items-center mb-4">
      <h2 class="text-xl font-semibold">系统状态</h2>
      <n-button @click="refresh" :loading="refreshing" size="small">刷新</n-button>
    </div>

    <n-spin v-if="loading" />

    <template v-else-if="status">
      <!-- Alerts -->
      <div v-if="status.alerts_triggered.length > 0" class="mb-4 space-y-2">
        <n-card
          v-for="a in status.alerts_triggered"
          :key="a.name"
          size="small"
          :class="a.level === 'critical' ? 'border-l-4 border-l-red-500' : 'border-l-4 border-l-yellow-500'"
        >
          <n-space align="center">
            <n-tag :type="a.level === 'critical' ? 'error' : 'warning'" size="small" round>
              {{ a.level.toUpperCase() }}
            </n-tag>
            <span class="text-sm">{{ a.description }}</span>
            <span class="text-xs text-gray-500">
              (当前: {{ typeof a.current_value === 'number' ? (a.current_value * 100).toFixed(1) + '%' : a.current_value }}
              / 阈值: {{ typeof a.threshold === 'number' ? (a.threshold * 100).toFixed(1) + '%' : a.threshold }})
            </span>
          </n-space>
        </n-card>
      </div>

      <!-- No alerts -->
      <div v-else class="mb-4">
        <n-card size="small" class="bg-green-50 border-green-200">
          <span class="text-green-700 text-sm">✅ 所有指标正常</span>
        </n-card>
      </div>

      <!-- Performance Table -->
      <n-card title="接口延迟统计" size="small">
        <n-table>
          <thead>
            <tr><th>路径</th><th>请求数</th><th>平均</th><th>P50</th><th>P95</th><th>P99</th><th>慢请求</th></tr>
          </thead>
          <tbody>
            <tr v-for="(p, path) in status.performance" :key="String(path)">
              <td class="text-xs font-mono max-w-[200px] truncate">{{ String(path) }}</td>
              <td>{{ (p as PathPerf).count }}</td>
              <td>{{ (p as PathPerf).avg_ms }}ms</td>
              <td>{{ (p as PathPerf).p50_ms }}ms</td>
              <td>
                <n-tag
                  :type="(p as PathPerf).p95_ms > 5000 ? 'warning' : 'success'"
                  size="small"
                >
                  {{ (p as PathPerf).p95_ms }}ms
                </n-tag>
              </td>
              <td>{{ (p as PathPerf).p99_ms }}ms</td>
              <td>
                <span :class="(p as PathPerf).slow_count > 0 ? 'text-red-500' : 'text-gray-400'">
                  {{ (p as PathPerf).slow_count }}
                </span>
              </td>
            </tr>
          </tbody>
        </n-table>
      </n-card>

      <!-- Alert Rules -->
      <n-card title="告警规则" size="small" class="mt-4">
        <div class="grid grid-cols-2 gap-2">
          <div
            v-for="r in status.alert_rules"
            :key="r.name"
            class="flex items-center gap-2 px-3 py-2 bg-gray-50 rounded text-sm"
          >
            <n-tag :type="r.level === 'critical' ? 'error' : 'warning'" size="tiny" round>
              {{ r.level }}
            </n-tag>
            <span class="flex-1">{{ r.name }}</span>
            <span class="text-gray-400 text-xs">阈值: {{ r.threshold }}</span>
          </div>
        </div>
      </n-card>
    </template>
  </div>
</template>
