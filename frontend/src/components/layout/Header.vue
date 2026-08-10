<script setup lang="ts">
defineProps<{ title?: string }>();
</script>

<template>
  <header class="h-16 bg-white border-b flex items-center px-6">
    <h1 class="text-lg font-medium">{{ title || "MedDeviceAgent" }}</h1>
    <slot />
  </header>
</template>
