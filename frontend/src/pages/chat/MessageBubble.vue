<script setup lang="ts">
import { computed } from "vue";
import { NButton, NIcon, useMessage } from "naive-ui";
import { CopyOutline } from "@vicons/ionicons5";
import { renderMarkdown } from "@/utils/markdown";
import CitationCard from "./CitationCard.vue";
import type { MessageItem, Citation } from "@/types";

const props = defineProps<{
  message: MessageItem;
  isStreaming?: boolean;
  citations?: Citation[];
  isSupport?: boolean;
}>();

const msg = useMessage();

const renderedContent = computed(() => {
  if (props.message.role === "assistant") {
    return renderMarkdown(props.message.content || "思考中…");
  }
  return "";
});

const displayTime = computed(() => {
  if (!props.message.created_at) return "";
  const d = new Date(props.message.created_at);
  return d.toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit" });
});

function handleCopy() {
  navigator.clipboard.writeText(props.message.content).then(() => {
    msg.success("已复制");
  });
}

const isRiskWarning = computed(() =>
  props.message.role === "system" && props.message.content.includes("风险")
);
</script>

<template>
  <!-- 客服模式：左右对调 -->
  <div :class="['flex gap-2 group', (isSupport ? message.role !== 'user' : message.role === 'user') ? 'justify-end' : 'justify-start']">
    <!-- 非"我"的发言：左边、白色 -->
    <div v-if="(isSupport ? message.role === 'user' : message.role !== 'user')" class="max-w-[80%]">
      <div v-if="isRiskWarning" class="rounded-lg px-4 py-3 bg-yellow-50 border border-yellow-300">
        <div class="flex items-center gap-2 mb-1">
          <span class="text-lg">⚠️</span>
          <span class="font-medium text-yellow-800 text-sm">安全提示</span>
        </div>
        <p class="text-sm text-yellow-700">{{ message.content }}</p>
      </div>

      <div v-else class="rounded-lg px-4 py-3 bg-white border text-sm leading-relaxed">
        <div v-if="message.role === 'assistant'" class="prose prose-sm max-w-none" v-html="renderedContent" />
        <div v-else class="text-sm whitespace-pre-wrap">{{ message.content }}</div>
        <span v-if="isStreaming" class="inline-block w-0.5 h-4 bg-blue-500 animate-pulse ml-0.5 align-text-bottom" />

        <div v-if="!isStreaming && message.content" class="flex items-center gap-1 mt-2 pt-2 border-t border-gray-100 opacity-0 group-hover:opacity-100 transition-opacity">
          <n-button text size="tiny" @click="handleCopy">
            <template #icon><n-icon size="14"><CopyOutline /></n-icon></template>
          </n-button>
        </div>
      </div>

      <CitationCard v-if="citations && citations.length > 0" :citations="citations" />
      <p v-if="displayTime" class="text-xs text-gray-400 mt-0.5 ml-4">{{ displayTime }}</p>
    </div>

    <!-- "我"的发言：右边、蓝色 -->
    <div v-else class="max-w-[75%]">
      <div class="rounded-lg px-4 py-2.5 bg-blue-500 text-white text-sm leading-relaxed whitespace-pre-wrap">
        {{ message.content }}
      </div>
      <p v-if="displayTime" class="text-xs text-gray-400 mt-0.5 text-right mr-1">{{ displayTime }}</p>
    </div>
  </div>
</template>
