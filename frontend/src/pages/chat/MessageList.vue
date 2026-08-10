<script setup lang="ts">
import { ref, watch, nextTick, computed } from "vue";
import { NButton, NIcon } from "naive-ui";
import { ChevronDownOutline } from "@vicons/ionicons5";
import { useChatStore } from "@/stores/chat";
import MessageBubble from "./MessageBubble.vue";

defineProps<{ isSupport?: boolean }>();

const chat = useChatStore();
const listRef = ref<HTMLElement>();
const isLoadingMore = ref(false);
const hasMore = ref(true);
const page = ref(1);

// 是否在底部
const isAtBottom = ref(true);

function checkAtBottom() {
  const el = listRef.value;
  if (!el) return;
  isAtBottom.value = el.scrollHeight - el.scrollTop - el.clientHeight < 60;
}

// 新消息自动滚到底部
watch(
  () => chat.messages.length,
  async () => {
    await nextTick();
    if (isAtBottom.value) {
      listRef.value?.scrollTo({ top: listRef.value.scrollHeight, behavior: "smooth" });
    }
  },
);

// 流式内容更新时保持滚动
watch(
  () => chat.messages[chat.messages.length - 1]?.content,
  async () => {
    await nextTick();
    if (isAtBottom.value) {
      listRef.value?.scrollTo({ top: listRef.value.scrollHeight, behavior: "auto" });
    }
  },
);

// 上滑加载更多
async function handleScroll() {
  checkAtBottom();

  const el = listRef.value;
  if (!el || isLoadingMore.value || !hasMore.value) return;

  // 距顶部 < 40px 时触发加载
  if (el.scrollTop < 40) {
    isLoadingMore.value = true;
    const prevHeight = el.scrollHeight;

    try {
      page.value += 1;
      const prevCount = chat.messages.length;
      await chat.loadMessages(chat.currentSessionId, page.value);
      if (chat.messages.length === prevCount) {
        hasMore.value = false;
      }

      await nextTick();
      // 保持滚动位置
      el.scrollTop = el.scrollHeight - prevHeight;
    } catch {
      page.value -= 1;
    } finally {
      isLoadingMore.value = false;
    }
  }
}

function scrollToBottom() {
  listRef.value?.scrollTo({ top: listRef.value.scrollHeight, behavior: "smooth" });
}

const showScrollButton = computed(() => !isAtBottom.value && chat.messages.length > 3);
</script>

<template>
  <div class="relative flex-1">
    <div
      ref="listRef"
      class="absolute inset-0 overflow-y-auto px-4 py-4 space-y-4 overscroll-contain"
      @scroll="handleScroll"
    >
      <!-- 加载更多 -->
      <div v-if="isLoadingMore" class="text-center py-2">
        <span class="text-xs text-gray-400">加载中…</span>
      </div>

      <!-- 空状态 -->
      <div v-if="chat.messages.length === 0" class="text-center text-gray-400 mt-20">
        <p class="text-3xl mb-3">👋</p>
        <p class="text-lg">您好！我是医疗设备智能客服助手</p>
        <p class="text-sm mt-2">可以问我设备故障、保修查询、操作说明等问题</p>

        <div class="mt-6 grid grid-cols-2 gap-2 max-w-sm mx-auto">
          <div
            v-for="q in ['设备显示E101是什么故障', '如何查询设备保修期限', '帮我创建维修工单']"
            :key="q"
            class="px-3 py-2 bg-gray-100 rounded text-xs cursor-pointer hover:bg-blue-50 hover:text-blue-600 transition-colors"
            @click="chat.addMessage('user', q)"
          >
            {{ q }}
          </div>
        </div>
      </div>

      <!-- 消息列表 -->
      <MessageBubble
        v-for="(msg, i) in chat.messages"
        :key="i"
        :message="msg"
        :is-streaming="i === chat.messages.length - 1 && chat.isStreaming"
        :is-support="isSupport"
      />

      <!-- Agent 状态指示 -->
      <div v-if="chat.isStreaming && chat.currentNode" class="flex items-center gap-2 px-4 py-1">
        <span class="w-2 h-2 bg-blue-500 rounded-full animate-pulse" />
        <span class="text-xs text-gray-400">
          {{
            chat.currentNode === "intent_classify" ? "正在理解您的问题…"
            : chat.currentNode === "query_rewrite" ? "正在优化检索…"
            : chat.currentNode === "rag_retrieve" ? "正在检索知识库…"
            : chat.currentNode === "rag_rerank" ? "正在排序结果…"
            : chat.currentNode === "rag_answer" ? "正在生成回答…"
            : chat.currentNode === "tool_execute" ? "正在查询…"
            : chat.currentNode === "output_safety_check" ? "正在检查回答安全性…"
            : `处理中: ${chat.currentNode}`
          }}
        </span>
      </div>
    </div>

    <!-- 回到底部 -->
    <transition name="fade">
      <div
        v-if="showScrollButton"
        class="absolute bottom-2 left-1/2 -translate-x-1/2"
      >
        <n-button circle size="small" @click="scrollToBottom">
          <template #icon><n-icon><ChevronDownOutline /></n-icon></template>
        </n-button>
      </div>
    </transition>
  </div>
</template>
