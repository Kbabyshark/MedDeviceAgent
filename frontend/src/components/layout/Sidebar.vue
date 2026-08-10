<script setup lang="ts">
import { computed, h } from "vue";
import { useRouter, useRoute } from "vue-router";
import { useAuthStore } from "@/stores/auth";
import { useChatStore } from "@/stores/chat";
import { NIcon, NTag, NButton, NMenu } from "naive-ui";
import type { MenuOption } from "naive-ui";
import {
  ChatbubblesOutline, ShieldCheckmarkOutline,
  LogOutOutline, HardwareChipOutline,
  DocumentTextOutline, SearchOutline, BarChartOutline,
  PulseOutline, TimerOutline, AlertCircleOutline,
  PeopleOutline, HeadsetOutline,
} from "@vicons/ionicons5";

const router = useRouter();
const route = useRoute();
const auth = useAuthStore();
const chat = useChatStore();

const activeKey = computed(() => {
  const rn = String(route.name || "");
  if (rn.startsWith("admin-")) return rn;
  return rn || (isStaff.value ? "support" : "chat");
});

const adminItems: MenuOption[] = [
  { label: "知识库管理", key: "admin-knowledge", icon: () => h(DocumentTextOutline) },
  { label: "故障码管理", key: "admin-fault-codes", icon: () => h(AlertCircleOutline) },
  { label: "保修记录管理", key: "admin-warranties", icon: () => h(ShieldCheckmarkOutline) },
  { label: "设备管理", key: "admin-devices", icon: () => h(HardwareChipOutline) },
  { label: "用户管理", key: "admin-users", icon: () => h(PeopleOutline) },
  { label: "检索测试", key: "admin-search", icon: () => h(SearchOutline) },
  { label: "Trace 追踪", key: "admin-trace", icon: () => h(TimerOutline) },
  { label: "成本分析", key: "admin-cost", icon: () => h(BarChartOutline) },
  { label: "系统状态", key: "admin-status", icon: () => h(PulseOutline) },
];

const isStaff = computed(() => auth.role === "support" || auth.role === "admin");

const navOptions = computed<MenuOption[]>(() => {
  const items: MenuOption[] = [];
  if (isStaff.value) {
    items.push({
      label: "客服工作台", key: "support-group", icon: () => h(HeadsetOutline),
      children: [
        { label: "待处理队列", key: "support" },
        { label: "我的工单", key: "support-mine" },
        { label: "客服对话", key: "support-chat" },
      ],
    });
    if (auth.role === "support") {
      items.push({ label: "设备查询", key: "admin-devices", icon: () => h(HardwareChipOutline) });
      items.push({ label: "故障码查询", key: "admin-fault-codes", icon: () => h(AlertCircleOutline) });
      items.push({ label: "保修记录查询", key: "admin-warranties", icon: () => h(ShieldCheckmarkOutline) });
    }
  } else {
    items.push({ label: "客服对话", key: "chat", icon: () => h(ChatbubblesOutline) });
    items.push({ label: "我的设备", key: "my-devices", icon: () => h(HardwareChipOutline) });
  }
  if (auth.isAdmin) {
    items.push({ type: "divider", key: "d1" }, ...adminItems);
  }
  return items;
});

function handleNavChange(key: string) {
  if (key.startsWith("admin-")) return router.push({ name: key });
  if (key === "my-devices") return router.push({ name: "my-devices" });
  if (key === "support-mine") return router.push({ name: "support-mine" });
  if (key === "support-chat") return router.push({ name: "support-chat" });
  if (key === "support") return router.push({ name: "support" });
  router.push({ name: "chat" });
}

function handleLogout() {
  auth.logout();
  chat.sessions = [];
  chat.currentSessionId = "";
  chat.messages = [];
  router.push("/login");
}
</script>

<template>
  <aside class="w-56 h-screen bg-white border-r flex flex-col flex-shrink-0">
    <!-- Logo -->
    <div class="h-16 flex items-center px-4 border-b">
      <n-icon size="24" color="#2563eb"><ShieldCheckmarkOutline /></n-icon>
      <span class="ml-2 font-semibold text-lg">MedDeviceAgent</span>
    </div>

    <!-- Nav -->
    <div class="flex-1 py-3">
      <n-menu
        :value="activeKey"
        :options="navOptions"
        :indent="16"
        @update:value="handleNavChange"
      />
    </div>

    <!-- User -->
    <div class="px-3 py-2 border-t text-sm space-y-1">
      <div class="flex items-center justify-between">
        <span class="truncate">{{ auth.username || "用户" }}</span>
        <n-tag :type="auth.role === 'admin' ? 'error' : auth.role === 'support' ? 'success' : 'info'" size="small">
          {{ auth.role === 'admin' ? '管理员' : auth.role === 'support' ? '客服' : '用户' }}
        </n-tag>
      </div>
      <n-button text size="small" @click="handleLogout">
        <template #icon><n-icon><LogOutOutline /></n-icon></template>
        退出登录
      </n-button>
    </div>
  </aside>
</template>
