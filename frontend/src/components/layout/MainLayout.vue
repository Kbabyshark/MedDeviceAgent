<script setup lang="ts">
import { ref } from "vue";
import { NButton, NIcon } from "naive-ui";
import { MenuOutline, CloseOutline } from "@vicons/ionicons5";
import Sidebar from "./Sidebar.vue";
import Header from "./Header.vue";

defineProps<{ title?: string }>();

const sidebarOpen = ref(false);
</script>

<template>
  <div class="flex h-screen overflow-hidden">
    <!-- Desktop Sidebar -->
    <div class="hidden md:block">
      <Sidebar />
    </div>

    <!-- Mobile Sidebar Overlay -->
    <transition name="fade">
      <div
        v-if="sidebarOpen"
        class="fixed inset-0 z-40 md:hidden"
        @click="sidebarOpen = false"
      >
        <div class="absolute inset-0 bg-black/50" />
        <div class="absolute left-0 top-0 bottom-0 w-72" @click.stop>
          <Sidebar />
        </div>
      </div>
    </transition>

    <!-- Mobile Hamburger Button -->
    <div class="md:hidden fixed top-3 left-3 z-30">
      <n-button circle size="small" @click="sidebarOpen = !sidebarOpen">
        <template #icon>
          <n-icon><MenuOutline v-if="!sidebarOpen" /><CloseOutline v-else /></n-icon>
        </template>
      </n-button>
    </div>

    <!-- Main -->
    <div class="flex-1 flex flex-col min-w-0">
      <Header :title="title" />
      <main class="flex-1 min-h-0">
        <slot />
      </main>
    </div>
  </div>
</template>
