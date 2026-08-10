<script setup lang="ts">
import { ref, onMounted, computed } from "vue";
import { NCard, NStatistic, NTable, NSpin, NSelect } from "naive-ui";
import { apiClient } from "@/api/client";
import type { CostSummary, DailyCost } from "@/types";

const summary = ref<CostSummary | null>(null);
const loading = ref(true);
const days = ref(30);

async function load(d: number) {
  days.value = d;
  loading.value = true;
  try {
    const res = await apiClient.get<CostSummary>(`/admin/cost?days=${d}`);
    summary.value = res.data;
  } finally { loading.value = false; }
}

onMounted(() => load(30));

// 图表数据（最大柱状条高度）
const maxTokens = computed(() => {
  if (!summary.value) return 1;
  return Math.max(...summary.value.daily_breakdown.map((d) => d.prompt_tokens + d.completion_tokens), 1);
});

function barHeight(tokens: number): string {
  return `${Math.round((tokens / maxTokens.value) * 120)}px`;
}

function dayLabel(date: string): string {
  return date.slice(5); // MM-DD
}
</script>

<template>
  <div class="p-6">
    <div class="flex justify-between items-center mb-4">
      <h2 class="text-xl font-semibold">成本分析</h2>
      <n-select
        v-model:value="days"
        :options="[{label:'7天',value:7},{label:'14天',value:14},{label:'30天',value:30},{label:'90天',value:90}]"
        style="width: 100px"
        @update:value="(v:number) => load(v)"
      />
    </div>

    <n-spin v-if="loading" />

    <template v-else-if="summary">
      <!-- 统计卡片 -->
      <div class="grid grid-cols-4 gap-4 mb-6">
        <n-card><n-statistic label="总调用次数" :value="summary.total_calls" /></n-card>
        <n-card><n-statistic label="输入 Token" :value="summary.total_prompt_tokens.toLocaleString()" /></n-card>
        <n-card><n-statistic label="输出 Token" :value="summary.total_completion_tokens.toLocaleString()" /></n-card>
        <n-card>
          <n-statistic label="费用估算">
            <span class="text-2xl font-semibold text-blue-600">¥{{ summary.estimated_cost_cny.toFixed(2) }}</span>
          </n-statistic>
        </n-card>
      </div>

      <!-- Token 柱状图 -->
      <n-card title="Token 消耗趋势" class="mb-6">
        <div class="flex items-end gap-1 h-36 py-2">
          <div
            v-for="d in summary.daily_breakdown"
            :key="d.date"
            class="flex-1 flex flex-col items-center gap-1 min-w-0"
            :title="`${d.date}: 输入 ${d.prompt_tokens.toLocaleString()} / 输出 ${d.completion_tokens.toLocaleString()}`"
          >
            <div class="flex flex-col items-center gap-0.5 w-full">
              <div class="w-full bg-blue-400 rounded-t hover:bg-blue-500 transition-colors" :style="{ height: barHeight(d.completion_tokens) }" />
              <div class="w-full bg-blue-200 hover:bg-blue-300 transition-colors" :style="{ height: barHeight(d.prompt_tokens) }" />
            </div>
            <span class="text-[10px] text-gray-400 truncate w-full text-center">{{ dayLabel(d.date) }}</span>
          </div>
        </div>
        <div class="flex justify-center gap-4 mt-2 text-xs text-gray-500">
          <span>■ 输入 Token</span><span>■ 输出 Token</span>
        </div>
      </n-card>

      <!-- 每日明细 -->
      <n-card title="每日明细">
        <n-table>
          <thead><tr><th>日期</th><th>调用次数</th><th>输入 Token</th><th>输出 Token</th><th>合计</th></tr></thead>
          <tbody>
            <tr v-for="d in summary.daily_breakdown" :key="d.date">
              <td>{{ d.date }}</td>
              <td>{{ d.calls }}</td>
              <td>{{ d.prompt_tokens.toLocaleString() }}</td>
              <td>{{ d.completion_tokens.toLocaleString() }}</td>
              <td>{{ (d.prompt_tokens + d.completion_tokens).toLocaleString() }}</td>
            </tr>
          </tbody>
        </n-table>
      </n-card>
    </template>
  </div>
</template>
