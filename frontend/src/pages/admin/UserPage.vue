<script setup lang="ts">
import { ref, onMounted } from "vue";
import {
  NTable, NButton, NTag, NSelect, NPopconfirm, NSpace,
  NPagination, NPageHeader, useMessage,
} from "naive-ui";
import { apiClient } from "@/api/client";
import type { UserInfo } from "@/types";

const message = useMessage();

const users = ref<UserInfo[]>([]);
const total = ref(0);
const page = ref(1);
const pageSize = 20;
const statusFilter = ref<number | null>(null);
const loading = ref(false);

const roleOptions = [
  { label: "管理员", value: "admin" },
  { label: "普通用户", value: "user" },
  { label: "人工客服", value: "support" },
];

const statusOptions = [
  { label: "全部", value: null },
  { label: "正常", value: 1 },
  { label: "已禁用", value: 0 },
];

const roleTagColors: Record<string, string> = {
  admin: "error",
  user: "info",
  support: "success",
};

const roleLabels: Record<string, string> = {
  admin: "管理员",
  user: "用户",
  support: "客服",
};

async function loadUsers() {
  loading.value = true;
  try {
    const params: Record<string, string> = {
      page: String(page.value),
      page_size: String(pageSize),
    };
    if (statusFilter.value !== null) {
      params.status = String(statusFilter.value);
    }
    const res = await apiClient.get<{ items: UserInfo[]; total: number }>("/admin/users", params);
    if (res.data) {
      users.value = res.data.items;
      total.value = res.data.total;
    }
  } catch (e) {
    message.error(e instanceof Error ? e.message : "加载失败");
  } finally {
    loading.value = false;
  }
}

async function handleUpdateRole(user: UserInfo, newRole: string) {
  try {
    await apiClient.put(`/admin/user/${user.user_id}`, { role: newRole });
    user.role = newRole;
    message.success(`已将 ${user.username} 角色改为 ${roleLabels[newRole]}`);
  } catch (e) {
    message.error(e instanceof Error ? e.message : "操作失败");
  }
}

async function handleToggleStatus(user: UserInfo) {
  const newStatus = user.status === 1 ? 0 : 1;
  const action = newStatus === 0 ? "禁用" : "启用";
  try {
    await apiClient.put(`/admin/user/${user.user_id}`, { status: newStatus });
    user.status = newStatus;
    message.success(`已${action} ${user.username}`);
  } catch (e) {
    message.error(e instanceof Error ? e.message : "操作失败");
  }
}

function handleFilterChange() {
  page.value = 1;
  loadUsers();
}

function handlePageChange(p: number) {
  page.value = p;
  loadUsers();
}

// ---- 重置密码 ----
const showPassword = ref(false);
const resetTarget = ref<any>(null);
const newPassword = ref("");

function openResetPassword(u: any) {
  resetTarget.value = u;
  newPassword.value = "";
  showPassword.value = true;
}

async function handleResetPassword() {
  if (!newPassword.value || newPassword.value.length < 6) {
    message.warning("密码至少 6 位");
    return;
  }
  try {
    await apiClient.put(`/admin/user/${resetTarget.value.user_id}/password`, {
      password: newPassword.value,
    });
    message.success(`已重置 ${resetTarget.value.username} 的密码`);
    showPassword.value = false;
  } catch (e) {
    message.error(e instanceof Error ? e.message : "重置失败");
  }
}

onMounted(() => loadUsers());
</script>

<template>
  <div class="p-6">
    <n-page-header title="用户管理" subtitle="管理平台用户账号与角色">
      <template #extra>
        <n-space align="center">
          <n-select
            v-model:value="statusFilter"
            :options="statusOptions"
            style="width: 100px"
            @update:value="handleFilterChange"
          />
        </n-space>
      </template>
    </n-page-header>

    <n-table :bordered="false" :single-line="false" class="mt-4">
      <thead>
        <tr>
          <th>ID</th>
          <th>用户名</th>
          <th>角色</th>
          <th>手机号</th>
          <th>邮箱</th>
          <th>状态</th>
          <th>注册时间</th>
          <th>操作</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="u in users" :key="u.user_id">
          <td class="text-gray-400 text-xs">{{ u.user_id }}</td>
          <td>
            <span class="font-medium">{{ u.username }}</span>
          </td>
          <td>
            <n-select
              :value="u.role"
              :options="roleOptions"
              size="small"
              style="width: 100px"
              @update:value="(v: string) => handleUpdateRole(u, v)"
            />
          </td>
          <td>{{ u.phone || "-" }}</td>
          <td>{{ u.email || "-" }}</td>
          <td>
            <n-tag :type="u.status === 1 ? 'success' : 'error'" size="small">
              {{ u.status === 1 ? "正常" : "已禁用" }}
            </n-tag>
          </td>
          <td class="text-gray-400 text-xs">{{ u.created_at || "-" }}</td>
          <td>
            <div class="flex gap-1">
              <n-popconfirm
                @positive-click="() => handleToggleStatus(u)"
              >
                <template #trigger>
                  <n-button
                    text
                    size="small"
                    :type="u.status === 1 ? 'warning' : 'success'"
                  >
                    {{ u.status === 1 ? "禁用" : "启用" }}
                  </n-button>
                </template>
                {{ u.status === 1 ? `确认禁用 ${u.username}？` : `确认启用 ${u.username}？` }}
              </n-popconfirm>
              <n-button text size="small" type="primary" @click="openResetPassword(u)">
                重置密码
              </n-button>
            </div>
          </td>
        </tr>
        <tr v-if="users.length === 0">
          <td colspan="8" class="text-center py-8 text-gray-400">
            暂无用户数据
          </td>
        </tr>
      </tbody>
    </n-table>

    <div class="flex justify-end mt-4">
      <n-pagination
        :page="page"
        :page-size="pageSize"
        :item-count="total"
        @update:page="handlePageChange"
      />
    </div>

    <!-- 重置密码弹窗 -->
    <n-modal v-model:show="showPassword" title="重置密码" preset="card" style="width: 380px">
      <p class="mb-3 text-sm text-gray-600">
        为用户 <span class="font-semibold">{{ resetTarget?.username }}</span> 设置新密码
      </p>
      <n-input
        v-model:value="newPassword"
        type="password"
        placeholder="输入新密码（至少6位）"
        maxlength="64"
        @keyup.enter="handleResetPassword"
      />
      <template #footer>
        <n-button @click="showPassword = false">取消</n-button>
        <n-button type="primary" @click="handleResetPassword">确认重置</n-button>
      </template>
    </n-modal>
  </div>
</template>
