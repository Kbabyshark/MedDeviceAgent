<script setup lang="ts">
import { ref, onMounted, reactive } from "vue";
import {
  NTable, NButton, NTag, NModal, NForm, NFormItem, NSelect, NInput, NPopconfirm, NUploadDragger, NUpload, NPagination, useMessage,
} from "naive-ui";
import { apiClient } from "@/api/client";
import type { KnowledgeDocument } from "@/types";

const msg = useMessage();
const docs = ref<KnowledgeDocument[]>([]);
const loading = ref(false);
const showUpload = ref(false);
const showEdit = ref(false);
const uploading = ref(false);
const saving = ref(false);

const page = ref(1);
const pageSize = 15;
const total = ref(0);
const filterDeviceType = ref("");
const filterDocType = ref("");

const selectedFile = ref<File | null>(null);
const uploadForm = ref({ device_type: "", doc_type: "manual", version: "v1", permission: "public" });
const editForm = reactive({ document_id: "", device_type: "", doc_type: "", version: "", permission: "" });

const docTypeOptions = [
  { label: "产品说明书", value: "manual" },
  { label: "FAQ", value: "faq" },
  { label: "故障码", value: "fault_code" },
  { label: "售后政策", value: "policy" },
];

async function loadDocs() {
  loading.value = true;
  try {
    let url = `/admin/knowledge?page=${page.value}&page_size=${pageSize}`;
    if (filterDeviceType.value) url += `&device_type=${filterDeviceType.value}`;
    if (filterDocType.value) url += `&doc_type=${filterDocType.value}`;
    const res = await apiClient.get<KnowledgeDocument[]>(url);
    if (res.data) { docs.value = (res.data as any).items || []; total.value = (res.data as any).total || 0; }
  } finally { loading.value = false; }
}

async function handleUploadConfirm() {
  if (!uploadForm.value.device_type) {
    msg.warning("请填写设备类型");
    return;
  }
  if (!selectedFile.value) {
    msg.warning("请选择文件");
    return;
  }
  uploading.value = true;
  try {
    const fd = new FormData();
    fd.append("file", selectedFile.value);
    fd.append("device_type", uploadForm.value.device_type);
    fd.append("doc_type", uploadForm.value.doc_type);
    fd.append("version", uploadForm.value.version);
    fd.append("permission", uploadForm.value.permission);
    await apiClient.postForm("/admin/knowledge/upload", fd);
    msg.success("上传成功");
    showUpload.value = false;
    selectedFile.value = null;
    uploadForm.value = { device_type: "", doc_type: "manual", version: "v1", permission: "public" };
    await loadDocs();
  } catch (e: any) {
    msg.error("上传失败: " + (e.message || ""));
  } finally { uploading.value = false; }
}

function openEdit(doc: KnowledgeDocument) {
  editForm.document_id = doc.document_id;
  editForm.device_type = doc.device_type || "";
  editForm.doc_type = doc.doc_type || "manual";
  editForm.version = doc.version || "v1";
  editForm.permission = doc.permission || "public";
  showEdit.value = true;
}

async function handleEditConfirm() {
  saving.value = true;
  try {
    await apiClient.put(`/admin/knowledge/${editForm.document_id}`, {
      device_type: editForm.device_type,
      doc_type: editForm.doc_type,
      version: editForm.version,
      permission: editForm.permission,
    });
    msg.success("已更新");
    showEdit.value = false;
    await loadDocs();
  } catch (e: any) {
    msg.error("更新失败: " + (e.message || ""));
  } finally { saving.value = false; }
}

async function handleDelete(docId: string) {
  await apiClient.del(`/admin/knowledge/${docId}`);
  msg.success("已删除");
  await loadDocs();
}

function onFileChange(files: any[]) {
  selectedFile.value = files[0]?.file || null;
}

const docTypeLabel = (t: string) => docTypeOptions.find((o) => o.value === t)?.label || t;

const permLabel = (p: string) => p === "public" ? "公开" : p === "internal" ? "内部" : p;

onMounted(loadDocs);
</script>

<template>
  <div class="p-6">
    <div class="flex justify-between items-center mb-4">
      <h2 class="text-xl font-semibold">知识库文档管理</h2>
      <n-button type="primary" @click="showUpload = true">上传文档</n-button>
    </div>

    <div class="flex gap-3 mb-4">
      <n-input v-model:value="filterDeviceType" placeholder="设备型号筛选" clearable style="width: 180px" @change="loadDocs" />
      <n-select v-model:value="filterDocType" :options="[{label:'全部类型',value:''},...docTypeOptions]" style="width: 150px" @update:value="loadDocs" />
      <n-button @click="loadDocs">刷新</n-button>
    </div>

    <n-table :loading="loading">
      <thead><tr><th>文档名称</th><th>设备型号</th><th>类型</th><th>版本</th><th>权限</th><th>分块数</th><th>状态</th><th>操作</th></tr></thead>
      <tbody>
        <tr v-for="d in docs" :key="d.document_id">
          <td class="max-w-[200px] truncate" :title="d.name">{{ d.name }}</td>
          <td>{{ d.device_type }}</td>
          <td><n-tag size="small">{{ docTypeLabel(d.doc_type) }}</n-tag></td>
          <td>{{ d.version }}</td>
          <td>{{ permLabel(d.permission) }}</td>
          <td>{{ d.chunk_count }}</td>
          <td>
            <n-tag :type="d.status === 'ready' ? 'success' : d.status === 'processing' ? 'warning' : 'default'" size="small">
              {{ d.status === 'ready' ? '就绪' : d.status === 'processing' ? '处理中' : d.status }}
            </n-tag>
          </td>
          <td>
            <div class="flex gap-1">
              <n-button text size="small" @click="openEdit(d)">编辑</n-button>
              <n-popconfirm @positive-click="() => handleDelete(d.document_id)">
                <template #trigger><n-button text size="small" type="error">删除</n-button></template>
                确认删除？
              </n-popconfirm>
            </div>
          </td>
        </tr>
      </tbody>
    </n-table>

    <div class="flex justify-center mt-4" v-if="total > pageSize">
      <n-pagination v-model:page="page" :page-size="pageSize" :item-count="total" @update:page="loadDocs" />
    </div>

    <!-- 上传弹窗 -->
    <n-modal v-model:show="showUpload" title="上传知识库文档" preset="card" style="width: 520px">
      <n-form :model="uploadForm" label-placement="left" label-width="80">
        <n-form-item label="设备类型">
          <n-input v-model:value="uploadForm.device_type" placeholder="如 Monitor-X1 (必填)" />
        </n-form-item>
        <n-form-item label="文档类型">
          <n-select v-model:value="uploadForm.doc_type" :options="docTypeOptions" />
        </n-form-item>
        <n-form-item label="版本号">
          <n-input v-model:value="uploadForm.version" placeholder="v1" />
        </n-form-item>
        <n-form-item label="权限">
          <n-select v-model:value="uploadForm.permission" :options="[{label:'公开',value:'public'},{label:'内部',value:'internal'}]" />
        </n-form-item>
        <n-upload
          :show-file-list="true" :max="1" accept=".pdf,.docx,.doc,.md,.txt" :default-upload="false"
          @update:file-list="onFileChange"
        >
          <n-upload-dragger>点击或拖拽文件到此处</n-upload-dragger>
        </n-upload>
      </n-form>
      <template #footer>
        <div class="flex justify-end gap-2">
          <n-button @click="showUpload = false">取消</n-button>
          <n-button type="primary" :loading="uploading" @click="handleUploadConfirm">确认上传</n-button>
        </div>
      </template>
    </n-modal>

    <!-- 编辑弹窗 -->
    <n-modal v-model:show="showEdit" title="编辑文档" preset="card" style="width: 420px">
      <n-form label-placement="left" label-width="80">
        <n-form-item label="设备类型">
          <n-input v-model:value="editForm.device_type" />
        </n-form-item>
        <n-form-item label="文档类型">
          <n-select v-model:value="editForm.doc_type" :options="docTypeOptions" />
        </n-form-item>
        <n-form-item label="版本号">
          <n-input v-model:value="editForm.version" />
        </n-form-item>
        <n-form-item label="权限">
          <n-select v-model:value="editForm.permission" :options="[{label:'公开',value:'public'},{label:'内部',value:'internal'}]" />
        </n-form-item>
      </n-form>
      <template #footer>
        <div class="flex justify-end gap-2">
          <n-button @click="showEdit = false">取消</n-button>
          <n-button type="primary" :loading="saving" @click="handleEditConfirm">保存</n-button>
        </div>
      </template>
    </n-modal>
  </div>
</template>
