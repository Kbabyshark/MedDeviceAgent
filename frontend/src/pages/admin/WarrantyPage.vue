<script setup lang="ts">
import { ref, onMounted, reactive } from "vue";
import {
  NTable, NButton, NTag, NModal, NForm, NFormItem,
  NInput, NPopconfirm, NPagination, NSelect, NDatePicker,
  useMessage,
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
const filterStatus = ref("");
const page = ref(1);
const pageSize = 15;
const total = ref(0);
const editing = ref<any>(null);

const form = reactive({
  device_sn: "", user_id: 1, start_date: null as number | null,
  end_date: null as number | null, problem_desc: "" as string,
  status: "valid" as string,
});

const statusOptions = [
  { label: "全部", value: "" },
  { label: "在保", value: "valid" },
  { label: "已过期", value: "expired" },
];

function openCreate() {
  editing.value = null;
  Object.assign(form, { device_sn: "", user_id: 1, start_date: null, end_date: null, problem_desc: "", status: "valid" });
  showForm.value = true;
}

function openEdit(row: any) {
  editing.value = row;
  form.device_sn = row.device_sn;
  form.user_id = row.user_id;
  form.start_date = row.start_date ? new Date(row.start_date).getTime() : null;
  form.end_date = row.end_date ? new Date(row.end_date).getTime() : null;
  form.problem_desc = row.problem_desc || "";
  form.status = row.status;
  showForm.value = true;
}

async function load() {
  loading.value = true;
  try {
    let url = `/admin/warranties?page=${page.value}&page_size=${pageSize}`;
    if (searchSn.value) url += `&device_sn=${encodeURIComponent(searchSn.value)}`;
    if (filterStatus.value) url += `&status=${encodeURIComponent(filterStatus.value)}`;
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
      user_id: form.user_id,
      problem_desc: form.problem_desc,
      status: form.status,
    };
    if (form.start_date) body.start_date = new Date(form.start_date).toISOString().slice(0, 10);
    if (form.end_date) body.end_date = new Date(form.end_date).toISOString().slice(0, 10);

    if (editing.value) {
      await apiClient.put(`/admin/warranties/${editing.value.id}`, body);
      msg.success("已更新");
    } else {
      await apiClient.post("/admin/warranties", body);
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
  await apiClient.del(`/admin/warranties/${id}`);
  msg.success("已删除");
  await load();
}

function handleSearch() { page.value = 1; load(); }
onMounted(() => { if (!isSupport) load(); });
</script>

<template>
  <div class="p-6">
    <div class="flex justify-between items-center mb-4">
      <h2 class="text-xl font-semibold">保修记录查询</h2>
      <n-button v-if="!isSupport" type="primary" @click="openCreate">新增保修记录</n-button>
    </div>

    <div class="flex gap-3 mb-4">
      <n-input v-model:value="searchSn" :placeholder="isSupport ? '输入设备SN查询' : '搜索设备SN'" clearable style="width: 200px" @keyup.enter="handleSearch" />
      <n-button type="primary" @click="handleSearch">查询</n-button>
      <template v-if="!isSupport">
        <n-select v-model:value="filterStatus" :options="statusOptions" style="width: 110px" @update:value="load" />
        <n-button @click="load">刷新</n-button>
      </template>
    </div>


    <n-table :loading="loading">
      <thead>
        <tr>
          <th>ID</th>
          <th>设备SN</th>
          <th>用户ID</th>
          <th>问题描述</th>
          <th>保修开始</th>
          <th>保修截止</th>
          <th>状态</th>
          <th v-if="!isSupport">操作</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="r in rows" :key="r.id">
          <td class="text-gray-400 text-xs">{{ r.id }}</td>
          <td class="font-mono text-sm">{{ r.device_sn }}</td>
          <td>{{ r.user_id }}</td>
          <td class="max-w-[180px] truncate" :title="r.problem_desc">{{ r.problem_desc || "-" }}</td>
          <td>{{ r.start_date || "-" }}</td>
          <td>{{ r.end_date || "-" }}</td>
          <td>
            <n-tag :type="r.status === 'valid' ? 'success' : 'error'" size="small">
              {{ r.status === "valid" ? "在保" : "已过期" }}
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
          <td :colspan="isSupport ? 7 : 8" class="text-center py-8 text-gray-400">暂无保修记录</td>
        </tr>
      </tbody>
    </n-table>

    <div class="flex justify-center mt-4" v-if="total > pageSize">
      <n-pagination v-model:page="page" :page-size="pageSize" :item-count="total" @update:page="load" />
    </div>

    <!-- 新增/编辑弹窗 -->
    <n-modal v-if="!isSupport" v-model:show="showForm" :title="editing ? '编辑保修记录' : '新增保修记录'" preset="card" style="width: 480px">
      <n-form label-placement="left" label-width="80">
        <n-form-item label="设备SN"><n-input v-model:value="form.device_sn" /></n-form-item>
        <n-form-item label="用户ID"><n-input v-model:value="form.user_id" type="number" /></n-form-item>
        <n-form-item label="问题描述">
          <n-input v-model:value="form.problem_desc" type="textarea" :autosize="{ minRows: 2 }" placeholder="设备故障现象或问题描述" />
        </n-form-item>
        <n-form-item label="保修开始">
          <n-date-picker v-model:value="form.start_date" type="date" style="width: 100%" />
        </n-form-item>
        <n-form-item label="保修截止">
          <n-date-picker v-model:value="form.end_date" type="date" style="width: 100%" />
        </n-form-item>
        <n-form-item label="状态">
          <n-select v-model:value="form.status" :options="[
            { label: '在保', value: 'valid' },
            { label: '已过期', value: 'expired' },
          ]" />
        </n-form-item>
      </n-form>
      <template #footer>
        <n-button @click="showForm = false">取消</n-button>
        <n-button type="primary" :loading="saving" @click="handleSave">保存</n-button>
      </template>
    </n-modal>
  </div>
</template>
