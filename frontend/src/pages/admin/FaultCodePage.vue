<script setup lang="ts">
import { ref, onMounted, reactive } from "vue";
import {
  NTable, NButton, NTag, NModal, NForm, NFormItem, NInput, NPopconfirm, NUpload, NPagination, useMessage,
} from "naive-ui";
import { useAuthStore } from "@/stores/auth";
import { apiClient } from "@/api/client";

const auth = useAuthStore();
const isSupport = auth.role === "support";
const msg = useMessage();
const rows = ref<any[]>([]);
const loading = ref(false);
const showForm = ref(false);
const showImport = ref(false);
const saving = ref(false);
const uploading = ref(false);
const search = ref("");
const filterModel = ref("");
const page = ref(1);
const pageSize = 15;
const total = ref(0);
const editing = ref<any>(null);

const form = reactive({ device_name: "", device_model: "", fault_code: "", fault_symptom: "", fault_cause: "", solution: "" });

function openCreate() { editing.value = null; Object.assign(form, { device_name: "", device_model: "", fault_code: "", fault_symptom: "", fault_cause: "", solution: "" }); showForm.value = true; }
function openEdit(row: any) { editing.value = row; Object.assign(form, row); showForm.value = true; }

async function load() {
  loading.value = true;
  try {
    let url = `/admin/fault-codes?page=${page.value}&page_size=${pageSize}`;
    if (search.value) url += `&search=${encodeURIComponent(search.value)}`;
    if (filterModel.value) url += `&device_model=${encodeURIComponent(filterModel.value)}`;
    const res = await apiClient.get<any>(url);
    if (res.data) { rows.value = (res.data as any).items || []; total.value = (res.data as any).total || 0; }
  } finally { loading.value = false; }
}

async function handleSave() {
  saving.value = true;
  try {
    if (editing.value) {
      await apiClient.put(`/admin/fault-codes/${editing.value.id}`, form);
      msg.success("已更新");
    } else {
      await apiClient.post("/admin/fault-codes", form);
      msg.success("已创建");
    }
    showForm.value = false;
    await load();
  } catch (e: any) { msg.error("保存失败: " + (e.message || "")); }
  finally { saving.value = false; }
}

async function handleDelete(id: number) {
  await apiClient.del(`/admin/fault-codes/${id}`);
  msg.success("已删除");
  await load();
}

async function handleImport({ file }: any) {
  uploading.value = true;
  try {
    const fd = new FormData();
    fd.append("file", file.file);
    const res = await apiClient.postForm<any>("/admin/fault-codes/import", fd);
    msg.success(res.message || "导入成功");
    showImport.value = false;
    await load();
  } catch (e: any) { msg.error("导入失败: " + (e.message || "")); }
  finally { uploading.value = false; }
}

onMounted(load);
</script>

<template>
  <div class="p-6">
    <div class="flex justify-between items-center mb-4">
      <h2 class="text-xl font-semibold">故障码管理</h2>
      <div v-if="!isSupport" class="flex gap-2">
        <n-button @click="showImport = true">导入 Excel</n-button>
        <n-button type="primary" @click="openCreate">新增故障码</n-button>
      </div>
    </div>

    <div class="flex gap-3 mb-4">
      <n-input v-model:value="search" placeholder="搜索（故障码/设备名称/现象）" clearable style="width: 260px" @change="load" />
      <n-input v-model:value="filterModel" placeholder="设备型号筛选" clearable style="width: 180px" @change="load" />
      <n-button @click="load">刷新</n-button>
    </div>

    <n-table :loading="loading">
      <thead><tr>
        <th>设备名称</th><th>设备型号</th><th>故障码</th><th>故障现象</th><th>故障原因</th><th>解决方法</th><th v-if="!isSupport">操作</th>
      </tr></thead>
      <tbody>
        <tr v-for="r in rows" :key="r.id">
          <td>{{ r.device_name }}</td>
          <td>{{ r.device_model }}</td>
          <td><n-tag type="error" size="small">{{ r.fault_code }}</n-tag></td>
          <td class="max-w-[150px] truncate" :title="r.fault_symptom">{{ r.fault_symptom }}</td>
          <td class="max-w-[150px] truncate" :title="r.fault_cause">{{ r.fault_cause }}</td>
          <td class="max-w-[150px] truncate" :title="r.solution">{{ r.solution }}</td>
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
      </tbody>
    </n-table>

    <div class="flex justify-center mt-4" v-if="total > pageSize">
      <n-pagination v-model:page="page" :page-size="pageSize" :item-count="total" @update:page="load" />
    </div>

    <!-- 新增/编辑弹窗 -->
    <n-modal v-if="!isSupport" v-model:show="showForm" :title="editing ? '编辑故障码' : '新增故障码'" preset="card" style="width: 560px">
      <n-form label-placement="left" label-width="80">
        <n-form-item label="设备名称"><n-input v-model:value="form.device_name" /></n-form-item>
        <n-form-item label="设备型号"><n-input v-model:value="form.device_model" /></n-form-item>
        <n-form-item label="故障码"><n-input v-model:value="form.fault_code" /></n-form-item>
        <n-form-item label="故障现象"><n-input v-model:value="form.fault_symptom" type="textarea" :autosize="{ minRows: 2 }" /></n-form-item>
        <n-form-item label="故障原因"><n-input v-model:value="form.fault_cause" type="textarea" :autosize="{ minRows: 2 }" /></n-form-item>
        <n-form-item label="解决方法"><n-input v-model:value="form.solution" type="textarea" :autosize="{ minRows: 2 }" /></n-form-item>
      </n-form>
      <template #footer>
        <n-button @click="showForm = false">取消</n-button>
        <n-button type="primary" :loading="saving" @click="handleSave">保存</n-button>
      </template>
    </n-modal>

    <!-- 导入弹窗 -->
    <n-modal v-if="!isSupport" v-model:show="showImport" title="导入故障码 Excel" preset="card" style="width: 420px">
      <p class="text-sm text-gray-500 mb-4">
        Excel 格式：设备名称, 设备型号, 故障码, 故障现象, 故障原因, 解决方法（第一行为表头）
      </p>
      <n-upload :max="1" accept=".xlsx,.xls" :default-upload="false" @update:file-list="(files: any[]) => { if (files[0]) handleImport({ file: files[0] }) }">
        <n-button :loading="uploading">选择 Excel 文件</n-button>
      </n-upload>
    </n-modal>
  </div>
</template>
