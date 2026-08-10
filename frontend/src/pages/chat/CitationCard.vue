<script setup lang="ts">
import { NCollapse, NCollapseItem, NTag, NIcon } from "naive-ui";
import { DocumentTextOutline } from "@vicons/ionicons5";
import type { Citation } from "@/types";

defineProps<{ citations: Citation[] }>();
</script>

<template>
  <div v-if="citations.length > 0" class="mt-2">
    <n-collapse>
      <n-collapse-item title="📚 参考来源">
        <template #header-extra>
          <span class="text-xs text-gray-400">{{ citations.length }} 条来源</span>
        </template>

        <div class="space-y-2">
          <div
            v-for="(c, i) in citations"
            :key="i"
            class="flex items-start gap-2 p-2 bg-gray-50 rounded text-xs"
          >
            <n-icon size="14" class="mt-0.5 text-blue-500"><DocumentTextOutline /></n-icon>
            <div class="flex-1 min-w-0">
              <div class="flex items-center gap-2 mb-0.5">
                <span class="font-medium truncate">{{ c.source }}</span>
                <n-tag size="tiny" :bordered="false">
                  {{ c.device_type }}
                </n-tag>
                <span class="text-gray-400">v{{ c.version }}</span>
              </div>
              <p class="text-gray-500 line-clamp-2">{{ c.snippet }}</p>
              <span class="text-gray-300">相关度: {{ (c.score * 100).toFixed(0) }}%</span>
            </div>
          </div>
        </div>
      </n-collapse-item>
    </n-collapse>
  </div>
</template>
