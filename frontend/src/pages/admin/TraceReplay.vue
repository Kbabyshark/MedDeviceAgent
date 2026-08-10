<script setup lang="ts">
import { ref, onMounted } from "vue";
import { useRoute } from "vue-router";
import { NTimeline, NTimelineItem, NTag, NTable, NCard, NSpin } from "naive-ui";
import { apiClient } from "@/api/client";

const route = useRoute();
const trace = ref<any>({});
const nodes = ref<any[]>([]);
const llmCalls = ref<any[]>([]);
const loading = ref(true);

const NODE_LABELS: Record<string, string> = {
  input_safety_check: "输入安全检测",
  pending_router: "待确认路由",
  intent_classify: "意图分类",
  context_load: "上下文加载",
  query_router: "查询路由",
  query_rewrite: "查询改写",
  rag_retrieve: "RAG 检索",
  rag_rerank: "RAG 重排序",
  rag_answer: "RAG 回答生成",
  fault_code_lookup: "故障码查询",
  tool_execute: "工具执行",
  human_confirm: "人工确认",
  execute_tool: "执行确认工具",
  answer_generate: "回答整合",
  output_safety_check: "输出安全检测",
  memory_update: "记忆更新",
  safe_reply: "安全回复",
};

onMounted(async () => {
  const traceId = route.params.traceId as string;
  try {
    const [tr, llm] = await Promise.all([
      apiClient.get<any>(`/trace/${traceId}`),
      apiClient.get<any>(`/trace/${traceId}/llm`),
    ]);
    if (tr.data) {
      trace.value = tr.data;
      nodes.value = (tr.data as any).nodes || [];
    }
    if (llm.data) llmCalls.value = (llm.data as any).llm_calls || [];
  } finally {
    loading.value = false;
  }
});
</script>

<template>
  <div class="p-6">
    <h2 class="text-xl font-semibold mb-4">Trace 回放</h2>

    <n-spin v-if="loading" class="block py-12" />

    <template v-else>
      <!-- 概要 -->
      <div class="grid grid-cols-4 gap-3 mb-6">
        <n-card size="small"><div class="text-xs text-gray-400">查询</div><div class="font-medium truncate">{{ trace.query }}</div></n-card>
        <n-card size="small"><div class="text-xs text-gray-400">总延迟</div><div class="font-medium">{{ trace.total_latency }}ms</div></n-card>
        <n-card size="small"><div class="text-xs text-gray-400">节点数 / LLM调用</div><div class="font-medium">{{ nodes.length }} / {{ llmCalls.length }}</div></n-card>
        <n-card size="small"><div class="text-xs text-gray-400">Token</div><div class="font-medium">{{ trace.total_tokens }}</div></n-card>
      </div>

      <div class="flex gap-6">
        <!-- 调用链 -->
        <div class="flex-1">
          <h3 class="text-lg font-semibold mb-3">调用链</h3>
          <n-timeline v-if="nodes.length > 0">
            <n-timeline-item
              v-for="n in nodes"
              :key="n.index"
              :title="NODE_LABELS[n.node_name] || n.node_name"
              :time="`${n.latency}ms`"
              :color="n.error ? 'red' : 'blue'"
            >
              <div class="text-xs text-gray-500 space-y-1">
                <div>输入: {{ typeof n.input === 'string' ? n.input : JSON.stringify(n.input).slice(0, 120) }}</div>
                <div>输出: {{ typeof n.output === 'string' ? n.output : JSON.stringify(n.output).slice(0, 120) }}</div>
                <n-tag v-if="n.error" type="error" size="small">{{ n.error }}</n-tag>
              </div>
            </n-timeline-item>
          </n-timeline>
          <p v-else class="text-gray-400 text-sm">暂无节点记录（需要重启后端生效）</p>
        </div>

        <!-- LLM 调用 -->
        <div class="w-80 flex-shrink-0">
          <h3 class="text-lg font-semibold mb-3">LLM 调用</h3>
          <div v-if="llmCalls.length > 0" class="space-y-2">
            <n-card v-for="(l, i) in llmCalls" :key="i" size="small">
              <div class="text-xs space-y-1">
                <div class="flex justify-between">
                  <span class="font-medium">{{ l.task_type || "LLM 调用" }}</span>
                  <span class="text-gray-400">{{ l.latency }}ms</span>
                </div>
                <div class="text-gray-400">{{ l.model_name }}</div>
                <div>输入: {{ l.prompt_tokens }} tokens | 输出: {{ l.completion_tokens }} tokens</div>
                <n-tag v-if="l.error" type="error" size="small">{{ l.error.slice(0, 40) }}</n-tag>
              </div>
            </n-card>
          </div>
          <p v-else class="text-gray-400 text-sm">暂无</p>
        </div>
      </div>
    </template>
  </div>
</template>
