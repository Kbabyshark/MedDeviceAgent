<script setup lang="ts">
import { ref } from "vue";
import { useRouter, useRoute } from "vue-router";
import { NForm, NFormItem, NInput, NButton, NCard, useMessage } from "naive-ui";
import { useAuthStore } from "@/stores/auth";

const router = useRouter();
const route = useRoute();
const auth = useAuthStore();
const message = useMessage();

const form = ref({ username: "", password: "" });
const loading = ref(false);

async function handleLogin() {
  if (!form.value.username || !form.value.password) {
    message.warning("请输入用户名和密码");
    return;
  }

  loading.value = true;
  try {
    await auth.login(form.value);
    message.success("登录成功");
    const redirect = (route.query.redirect as string) || "/chat";
    router.push(redirect);
  } catch (e) {
    message.error(e instanceof Error ? e.message : "登录失败");
  } finally {
    loading.value = false;
  }
}
</script>

<template>
  <div class="min-h-screen bg-gray-50 flex items-center justify-center">
    <n-card title="MedDeviceAgent" style="width: 400px">
      <template #header-extra>
        <span class="text-gray-400 text-sm">医疗设备智能客服</span>
      </template>

      <n-form :model="form" @submit.prevent="handleLogin">
        <n-form-item label="用户名">
          <n-input
            v-model:value="form.username"
            placeholder="输入用户名"
            :disabled="loading"
          />
        </n-form-item>

        <n-form-item label="密码">
          <n-input
            v-model:value="form.password"
            type="password"
            placeholder="输入密码"
            :disabled="loading"
            @keyup.enter="handleLogin"
          />
        </n-form-item>

        <n-button
          type="primary"
          block
          :loading="loading"
          @click="handleLogin"
        >
          登 录
        </n-button>
      </n-form>

      <div class="mt-4 text-center text-sm text-gray-500">
        还没有账号？
        <n-button text type="primary" @click="router.push('/register')">
          去注册
        </n-button>
      </div>
    </n-card>
  </div>
</template>
