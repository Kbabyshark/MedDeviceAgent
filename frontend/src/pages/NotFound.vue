<script setup lang="ts">
import { NResult, NButton } from "naive-ui";
import { useRouter } from "vue-router";
const router = useRouter();
</script>

<template>
  <div class="min-h-screen flex items-center justify-center">
    <n-result status="404" title="页面不存在" description="请检查 URL 是否正确">
      <template #footer>
        <n-button type="primary" @click="router.push('/chat')">返回首页</n-button>
      </template>
    </n-result>
  </div>
</template>
