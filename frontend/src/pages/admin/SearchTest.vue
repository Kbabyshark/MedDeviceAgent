<script setup lang="ts">
/**
 * 知识检索测试面板 — 输入 query 直接搜索 Qdrant，查看结果和相似度。
 */
import { ref } from "vue";
import { NInput, NButton, NSelect, NCard, NTag, NSpace, NSkeleton, useMessage } from "naive-ui";
import { apiClient } from "@/api/client";
import type { KnowledgeSearchResult } from "@/types";

const msg = useMessage();
const query = ref("");
const deviceType = ref("");
const docType = ref("");
const topK = ref(5);
const results = ref<KnowledgeSearchResult[]>([]);
const searching = ref(false);

async function search() {
  if (!query.value.trim()) return;
  searching.value = true;

  try {
    const formData = new FormData();
    formData.append("query", query.value.trim());
    if (deviceType.value) formData.append("device_type", deviceType.value);
    if (docType.value) formData.append("doc_type", docType.value);
    formData.append("top_k", String(topK.value));

    const res = await apiClient.postForm<{ results: KnowledgeSearchResult[]; count: number }>(
      "/knowledge/search",
      formData
    );
    if (res.data) {
      results.value = res.data.results || [];
    }
  } catch (e) {
    msg.error(e instanceof Error ? e.message : "检索失败");
  } finally {
    searching.value = false;
  }
}

function highlightScore(score: number): string {
  if (score >= 0.8) return "success";
  if (score >= 0.5) return "warning";
  return "default";
}
</script>

<template>
  <div class="p-6">
    <h2 class="text-xl font-semibold mb-4">知识检索测试</h2>

    <!-- Search Bar -->
    <n-space class="mb-4" align="end">
      <n-input v-model:value="query" placeholder="输入测试查询…" style="width: 400px" @keyup.enter="search" />
      <n-input v-model:value="deviceType" placeholder="设备型号 (可选)" style="width: 160px" />
      <n-select v-model:value="docType" :options="[
        {label:'全部',value:''},{label:'说明书',value:'manual'},{label:'FAQ',value:'faq'},{label:'故障码',value:'fault_code'}
      ]" style="width: 120px" />
      <n-select v-model:value="topK" :options="[3,5,10,20].map(n=>({label:`Top-${n}`,value:n}))" style="width: 100px" />
      <n-button type="primary" :loading="searching" @click="search">检索</n-button>
    </n-space>

    <!-- Results -->
    <div v-if="results.length > 0" class="space-y-3">
      <p class="text-sm text-gray-500">{{ results.length }} 条结果</p>

      <n-card v-for="(r, i) in results" :key="i" size="small">
        <template #header>
          <n-space align="center">
            <span class="text-sm font-medium">#{{ i + 1 }}</span>
            <n-tag :type="highlightScore(r.score)" size="small">
              相关度: {{ (r.score * 100).toFixed(1) }}%
            </n-tag>
            <n-tag size="tiny" :bordered="false">
              {{ r.metadata?.device_type || '-' }}
            </n-tag>
            <span class="text-xs text-gray-400">{{ r.metadata?.name || r.metadata?.doc_type }}</span>
          </n-space>
        </template>
        <p class="text-sm whitespace-pre-wrap leading-relaxed">{{ r.content }}</p>
        <template v-if="r.metadata?.version" #footer>
          <span class="text-xs text-gray-400">版本: {{ r.metadata.version }}</span>
        </template>
      </n-card>
    </div>

    <!-- Empty -->
    <n-skeleton v-if="searching" :repeat="3" text />
    <div v-else-if="results.length === 0 && query" class="text-center py-10 text-gray-400">
      无检索结果，请尝试调整查询或放宽筛选条件
    </div>
  </div>
</template>
