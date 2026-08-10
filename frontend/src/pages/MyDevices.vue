<script setup lang="ts">
import { ref, onMounted } from "vue";
import { NTable, NTag, NButton, NPageHeader, useMessage } from "naive-ui";
import MainLayout from "@/components/layout/MainLayout.vue";
import { apiClient } from "@/api/client";

const devices = ref<any[]>([]);
const loading = ref(false);
const msg = useMessage();

async function load() {
  loading.value = true;
  try {
    const res = await apiClient.get<any>("/my/devices");
    if (res.data) devices.value = (res.data as any).items || [];
  } finally {
    loading.value = false;
  }
}

const statusMap: Record<string, { label: string; type: "success" | "warning" | "default" }> = {
  active: { label: "使用中", type: "success" },
  inactive: { label: "闲置", type: "default" },
  repairing: { label: "维修中", type: "warning" },
};

onMounted(load);
</script>

<template>
  <MainLayout title="我的设备">
    <div class="p-6">
      <div class="flex justify-between items-center mb-4">
        <h2 class="text-xl font-semibold">我的设备</h2>
        <n-button @click="load">刷新</n-button>
      </div>

      <n-table :loading="loading" :bordered="false" :single-line="false">
        <thead>
          <tr>
            <th>设备SN</th>
            <th>设备型号</th>
            <th>版本</th>
            <th>状态</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="d in devices" :key="d.id">
            <td class="font-mono text-sm">{{ d.device_sn }}</td>
            <td>{{ d.device_type }}</td>
            <td>{{ d.version || "-" }}</td>
            <td>
              <n-tag :type="statusMap[d.status]?.type || 'default'" size="small">
                {{ statusMap[d.status]?.label || d.status }}
              </n-tag>
            </td>
          </tr>
          <tr v-if="devices.length === 0 && !loading">
            <td colspan="4" class="text-center py-12 text-gray-400">
              暂无绑定设备
            </td>
          </tr>
        </tbody>
      </n-table>
    </div>
  </MainLayout>
</template>
