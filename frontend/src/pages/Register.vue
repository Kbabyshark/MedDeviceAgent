<script setup lang="ts">
import { ref } from "vue";
import { useRouter } from "vue-router";
import { NForm, NFormItem, NInput, NButton, NCard, useMessage } from "naive-ui";
import { apiClient } from "@/api/client";
import type { RegisterRequest, UserInfo } from "@/types";

const router = useRouter();
const message = useMessage();

const form = ref<RegisterRequest>({ username: "", password: "", phone: "", email: "" });
const loading = ref(false);

async function handleRegister() {
  if (!form.value.username || form.value.username.length < 2) {
    message.warning("用户名至少 2 个字符");
    return;
  }
  if (!form.value.password || form.value.password.length < 6) {
    message.warning("密码至少 6 位");
    return;
  }

  loading.value = true;
  try {
    const res = await apiClient.post<UserInfo>("/auth/register", form.value);
    if (res.code === 0) {
      message.success("注册成功，请登录");
      router.push("/login");
    } else {
      message.error(res.message || "注册失败");
    }
  } catch (e) {
    message.error(e instanceof Error ? e.message : "注册失败");
  } finally {
    loading.value = false;
  }
}
</script>

<template>
  <div class="min-h-screen bg-gray-50 flex items-center justify-center">
    <n-card title="注册账号" style="width: 420px">
      <template #header-extra>
        <span class="text-gray-400 text-sm">医疗设备智能客服</span>
      </template>

      <n-form :model="form" @submit.prevent="handleRegister">
        <n-form-item label="用户名">
          <n-input
            v-model:value="form.username"
            placeholder="2-32 个字符"
            :disabled="loading"
            maxlength="32"
          />
        </n-form-item>

        <n-form-item label="密码">
          <n-input
            v-model:value="form.password"
            type="password"
            placeholder="至少 6 位"
            :disabled="loading"
            maxlength="64"
            @keyup.enter="handleRegister"
          />
        </n-form-item>

        <n-form-item label="手机号">
          <n-input
            v-model:value="form.phone"
            placeholder="选填"
            :disabled="loading"
            maxlength="20"
          />
        </n-form-item>

        <n-form-item label="邮箱">
          <n-input
            v-model:value="form.email"
            placeholder="选填"
            :disabled="loading"
            maxlength="128"
          />
        </n-form-item>

        <n-button
          type="primary"
          block
          :loading="loading"
          @click="handleRegister"
        >
          注 册
        </n-button>
      </n-form>

      <div class="mt-4 text-center text-sm text-gray-500">
        已有账号？
        <n-button text type="primary" @click="router.push('/login')">
          去登录
        </n-button>
      </div>
    </n-card>
  </div>
</template>
