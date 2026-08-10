<script setup lang="ts">
import { NConfigProvider, NMessageProvider, NDialogProvider, NButton, NIcon, darkTheme, zhCN } from "naive-ui";
import { useDark, useToggle } from "@vueuse/core";
import { SunnyOutline, MoonOutline } from "@vicons/ionicons5";
import { useNetwork } from "@/composables/useNetwork";

const isDark = useDark();
const toggleDark = useToggle(isDark);
const { showOfflineBanner, dismissBanner } = useNetwork();
</script>

<template>
  <n-config-provider :theme="isDark ? darkTheme : undefined" :locale="zhCN">
    <n-message-provider>
      <n-dialog-provider>
        <!-- 离线提示 -->
        <div
          v-if="showOfflineBanner"
          class="fixed top-0 left-0 right-0 z-50 bg-yellow-500 text-white text-center py-1.5 text-sm font-medium"
        >
          网络连接异常，部分功能不可用
          <n-button text size="tiny" class="ml-2 !text-white underline" @click="dismissBanner">关闭</n-button>
        </div>

        <!-- 暗色模式切换 -->
        <div class="fixed bottom-4 right-4 z-50">
          <n-button circle @click="toggleDark()">
            <template #icon>
              <n-icon><SunnyOutline v-if="isDark" /><MoonOutline v-else /></n-icon>
            </template>
          </n-button>
        </div>

        <router-view />
      </n-dialog-provider>
    </n-message-provider>
  </n-config-provider>
</template>
