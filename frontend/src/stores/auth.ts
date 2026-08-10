import { defineStore } from "pinia";
import { ref, computed } from "vue";
import { apiClient } from "@/api/client";
import type { LoginRequest, LoginResponse } from "@/types";

const TOKEN_KEY = "svagent_token";
const USER_KEY = "svagent_user";
const ROLE_KEY = "svagent_role";
const NAME_KEY = "svagent_name";

export const useAuthStore = defineStore("auth", () => {
  const token = ref<string>(localStorage.getItem(TOKEN_KEY) || "");
  const userId = ref<number>(Number(localStorage.getItem(USER_KEY)) || 0);
  const role = ref<string>(localStorage.getItem(ROLE_KEY) || "");
  const username = ref<string>(localStorage.getItem(NAME_KEY) || "");

  const isLoggedIn = computed(() => !!token.value);
  const isAdmin = computed(() => role.value === "admin");

  async function login(credentials: LoginRequest): Promise<void> {
    const res = await apiClient.post<LoginResponse>("/auth/login", credentials);
    if (!res.data) throw new Error("登录失败：服务端无响应");

    token.value = res.data.access_token;
    userId.value = res.data.user_id;
    role.value = res.data.role;
    username.value = res.data.username;

    localStorage.setItem(TOKEN_KEY, token.value);
    localStorage.setItem(USER_KEY, String(userId.value));
    localStorage.setItem(ROLE_KEY, role.value);
    localStorage.setItem(NAME_KEY, username.value);
  }

  function logout(): void {
    token.value = "";
    userId.value = 0;
    role.value = "";
    username.value = "";
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(USER_KEY);
    localStorage.removeItem(ROLE_KEY);
    localStorage.removeItem(NAME_KEY);
  }

  return { token, userId, role, username, isLoggedIn, isAdmin, login, logout };
});
