<script setup lang="ts">
import { NSpin } from "naive-ui";
defineProps<{ text?: string }>();
</script>

<template>
  <div class="flex flex-col items-center justify-center py-20">
    <n-spin size="medium" />
    <p class="mt-3 text-gray-500 text-sm">{{ text || "加载中…" }}</p>
  </div>
</template>
