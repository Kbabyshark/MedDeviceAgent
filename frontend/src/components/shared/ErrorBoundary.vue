<script setup lang="ts">
import { NResult, NButton } from "naive-ui";

defineProps<{
  message?: string;
  onRetry?: () => void;
}>();

const emit = defineEmits<{ retry: [] }>();
</script>

<template>
  <n-result
    status="error"
    title="出错了"
    :description="message || '未知错误'"
  >
    <template #footer>
      <n-button type="primary" @click="emit('retry')">重试</n-button>
    </template>
  </n-result>
</template>
