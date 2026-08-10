<script setup lang="ts">
import { ref, onMounted, reactive } from "vue";
import {
  NTable, NButton, NTag, NModal, NForm, NFormItem,
  NInput, NPopconfirm, NPagination, NSelect, useMessage,
} from "naive-ui";
import { useAuthStore } from "@/stores/auth";
import { apiClient } from "@/api/client";

const auth = useAuthStore();
const isSupport = auth.role === "support";

const msg = useMessage();
const rows = ref<any[]>([]);
const loading = ref(false);
const showForm = ref(false);
const saving = ref(false);
const searchSn = ref("");
const filterType = ref("");
const filterUserId = ref("");
const page = ref(1);
const pageSize = 15;
const total = ref(0);
const editing = ref<any>(null);

const form = reactive({
  device_sn: "", device_type: "", version: "", user_id: 0, status: "active" as string,
});
const selectedUserName = ref("");

// ---- 用户选择弹窗 ----
const showUserPicker = ref(false);
const userOptions = ref<any[]>([]);
const userSearch = ref("");
const userLoading = ref(false);

async function loadUsers(query = "") {
  userLoading.value = true;
  try {
    const res = await apiClient.get<any>(`/admin/users?page_size=50${query ? `&username=${encodeURIComponent(query)}` : ""}`);
    if (res.data) userOptions.value = (res.data as any).items || [];
  } finally { userLoading.value = false; }
}

function openUserPicker() { showUserPicker.value = true; userSearch.value = ""; loadUsers(); }
function onUserSearch(val: string) { loadUsers(val); }
function selectUser(u: any) {
  form.user_id = u.user_id;
  selectedUserName.value = u.username;
  showUserPicker.value = false;
}

const statusOptions = [
  { label: "全部", value: "" },
  { label: "使用中", value: "active" },
  { label: "闲置", value: "inactive" },
  { label: "维修中", value: "repairing" },
];

function openCreate() {
  editing.value = null;
  Object.assign(form, { device_sn: "", device_type: "", version: "", user_id: 0, status: "active" });
  selectedUserName.value = "";
  showForm.value = true;
}

function openEdit(row: any) {
  editing.value = row;
  form.device_sn = row.device_sn;
  form.device_type = row.device_type;
  form.version = row.version || "";
  form.user_id = row.user_id;
  form.status = row.status;
  selectedUserName.value = row.username || `用户${row.user_id}`;
  showForm.value = true;
}

async function load() {
  loading.value = true;
  try {
    let url = `/admin/devices?page=${page.value}&page_size=${pageSize}`;
    if (searchSn.value) url += `&device_sn=${encodeURIComponent(searchSn.value)}`;
    if (filterType.value) url += `&device_type=${encodeURIComponent(filterType.value)}`;
    if (filterUserId.value) url += `&user_id=${encodeURIComponent(filterUserId.value)}`;
    const res = await apiClient.get<any>(url);
    if (res.data) {
      rows.value = (res.data as any).items || [];
      total.value = (res.data as any).total || 0;
    }
  } finally {
    loading.value = false;
  }
}

async function handleSave() {
  saving.value = true;
  try {
    const body: any = {
      device_sn: form.device_sn,
      device_type: form.device_type,
      version: form.version || null,
      user_id: form.user_id,
      status: form.status,
    };

    if (editing.value) {
      await apiClient.put(`/admin/devices/${editing.value.id}`, body);
      msg.success("已更新");
    } else {
      await apiClient.post("/admin/devices", body);
      msg.success("已创建");
    }
    showForm.value = false;
    await load();
  } catch (e: any) {
    msg.error("保存失败: " + (e.message || ""));
  } finally {
    saving.value = false;
  }
}

async function handleDelete(id: number) {
  await apiClient.del(`/admin/devices/${id}`);
  msg.success("已删除");
  await load();
}

function handleSearch() {
  page.value = 1; load();
}

onMounted(() => { if (!isSupport) load(); });
</script>

<template>
  <div class="p-6">
    <div class="flex justify-between items-center mb-4">
      <h2 class="text-xl font-semibold">设备查询</h2>
      <n-button v-if="!isSupport" type="primary" @click="openCreate">新增设备</n-button>
    </div>

    <div class="flex gap-3 mb-4 flex-wrap">
      <n-input v-model:value="searchSn" :placeholder="isSupport ? '输入设备SN查询' : '搜索设备SN'" clearable style="width: 200px" @keyup.enter="handleSearch" />
      <n-button type="primary" @click="handleSearch">查询</n-button>
      <template v-if="!isSupport">
        <n-input v-model:value="filterType" placeholder="设备型号筛选" clearable style="width: 160px" @change="load" />
        <n-input v-model:value="filterUserId" placeholder="用户ID" clearable style="width: 100px" @change="load" />
        <n-button @click="load">刷新</n-button>
      </template>
    </div>


    <n-spin :show="loading" size="large">
    <n-table :loading="false">
      <thead>
        <tr>
          <th>ID</th>
          <th>设备SN</th>
          <th>设备型号</th>
          <th>版本</th>
          <th>用户</th>
          <th>状态</th>
          <th v-if="!isSupport">操作</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="r in rows" :key="r.id">
          <td class="text-gray-400 text-xs">{{ r.id }}</td>
          <td class="font-mono text-sm">{{ r.device_sn }}</td>
          <td>{{ r.device_type }}</td>
          <td>{{ r.version || "-" }}</td>
          <td>{{ r.username || `用户${r.user_id}` }}</td>
          <td>
            <n-tag :type="r.status === 'active' ? 'success' : r.status === 'repairing' ? 'warning' : 'default'" size="small">
              {{ r.status === "active" ? "使用中" : r.status === "repairing" ? "维修中" : "闲置" }}
            </n-tag>
          </td>
          <td v-if="!isSupport">
            <div class="flex gap-1">
              <n-button text size="small" @click="openEdit(r)">编辑</n-button>
              <n-popconfirm @positive-click="() => handleDelete(r.id)">
                <template #trigger><n-button text size="small" type="error">删除</n-button></template>
                确认删除？
              </n-popconfirm>
            </div>
          </td>
        </tr>
        <tr v-if="rows.length === 0">
          <td :colspan="isSupport ? 6 : 7" class="text-center py-8 text-gray-400">暂无设备数据</td>
        </tr>
      </tbody>
    </n-table>
    </n-spin>

    <div class="flex justify-center mt-4" v-if="total > pageSize">
      <n-pagination v-model:page="page" :page-size="pageSize" :item-count="total" @update:page="load" />
    </div>

    <!-- 新增/编辑弹窗 -->
    <n-modal v-if="!isSupport" v-model:show="showForm" :title="editing ? '编辑设备' : '新增设备'" preset="card" style="width: 460px">
      <n-form label-placement="left" label-width="80">
        <n-form-item label="设备SN"><n-input v-model:value="form.device_sn" /></n-form-item>
        <n-form-item label="设备型号"><n-input v-model:value="form.device_type" /></n-form-item>
        <n-form-item label="版本"><n-input v-model:value="form.version" placeholder="软件版本，选填" /></n-form-item>
        <n-form-item label="所属用户">
          <div class="flex items-center gap-2">
            <n-button @click="openUserPicker" :type="form.user_id ? 'default' : 'primary'" size="small">
              {{ form.user_id ? selectedUserName : '选择用户' }}
            </n-button>
            <n-button v-if="form.user_id" text size="small" type="error" @click="form.user_id = 0; selectedUserName = ''">清除</n-button>
          </div>
        </n-form-item>
        <n-form-item label="状态">
          <n-select v-model:value="form.status" :options="[
            { label: '使用中', value: 'active' },
            { label: '闲置', value: 'inactive' },
            { label: '维修中', value: 'repairing' },
          ]" />
        </n-form-item>
      </n-form>
      <template #footer>
        <n-button @click="showForm = false">取消</n-button>
        <n-button type="primary" :loading="saving" @click="handleSave">保存</n-button>
      </template>
    </n-modal>

    <!-- 用户选择弹窗 -->
    <n-modal v-model:show="showUserPicker" title="选择用户" preset="card" style="width: 500px">
      <div class="mb-3 flex gap-2">
        <n-input v-model:value="userSearch" placeholder="搜索用户名" clearable @update:value="onUserSearch" />
      </div>
      <n-table :loading="userLoading" :single-line="false" class="max-h-72 overflow-y-auto">
        <thead><tr><th>ID</th><th>用户名</th><th>角色</th><th>操作</th></tr></thead>
        <tbody>
          <tr v-for="u in userOptions" :key="u.user_id" class="hover:bg-gray-50 cursor-pointer" @click="selectUser(u)">
            <td class="text-gray-400 text-xs">{{ u.user_id }}</td>
            <td class="font-medium">{{ u.username }}</td>
            <td>
              <n-tag :type="u.role === 'admin' ? 'error' : u.role === 'support' ? 'success' : 'info'" size="small">
                {{ u.role === 'admin' ? '管理员' : u.role === 'support' ? '客服' : '用户' }}
              </n-tag>
            </td>
            <td><n-button text size="small" type="primary">选择</n-button></td>
          </tr>
          <tr v-if="userOptions.length === 0">
            <td colspan="4" class="text-center py-4 text-gray-400">暂无用户</td>
          </tr>
        </tbody>
      </n-table>
    </n-modal>
  </div>
</template>
