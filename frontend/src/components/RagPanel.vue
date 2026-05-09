<template>
  <section class="rag-panel">
    <!-- Header -->
    <header class="rag-header">
      <div class="header-text">
        <p class="eyebrow">Knowledge Base</p>
        <h2>本地知识库</h2>
        <p class="header-desc">管理模型可以索引的学习资料目录，并查看已进入知识库的文件。</p>
      </div>
      <button class="icon-refresh" :disabled="loading" @click="loadAll" title="刷新">
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <path d="M21 12a9 9 0 0 1-15.4 6.4L3 16" />
          <path d="M3 21v-5h5" />
          <path d="M3 12a9 9 0 0 1 15.4-6.4L21 8" />
          <path d="M16 8h5V3" />
        </svg>
      </button>
    </header>

    <!-- Notice -->
    <div v-if="message.text" :class="['notice-toast', message.type]">
      <span>{{ message.text }}</span>
      <button @click="message.text = ''" title="关闭">×</button>
    </div>

    <!-- Status Grid -->
    <section class="status-grid">
      <article class="status-card">
        <div class="status-icon" :class="ragStatus?.ready ? 'ok' : 'bad'">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/>
            <polyline points="22 4 12 14.01 9 11.01"/>
          </svg>
        </div>
        <div class="status-body">
          <span>状态</span>
          <strong :class="ragStatus?.ready ? 'ok' : 'bad'">
            {{ ragStatus?.ready ? "Ready" : "Not ready" }}
          </strong>
        </div>
      </article>
      <article class="status-card">
        <div class="status-icon teal">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <ellipse cx="12" cy="5" rx="9" ry="3"/>
            <path d="M21 12c0 1.66-4 3-9 3s-9-1.34-9-3"/>
            <path d="M3 5v14c0 1.66 4 3 9 3s9-1.34 9-3V5"/>
          </svg>
        </div>
        <div class="status-body">
          <span>索引</span>
          <strong>{{ ragStatus?.index_backend || "unknown" }}</strong>
        </div>
      </article>
      <article class="status-card">
        <div class="status-icon blue">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <circle cx="11" cy="11" r="8"/>
            <line x1="21" y1="21" x2="16.65" y2="16.65"/>
          </svg>
        </div>
        <div class="status-body">
          <span>查询</span>
          <strong>{{ ragStatus?.query_backend || "unknown" }}</strong>
        </div>
      </article>
      <article class="status-card">
        <div class="status-icon amber">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
            <polyline points="14 2 14 8 20 8"/>
            <line x1="16" y1="13" x2="8" y2="13"/>
            <line x1="16" y1="17" x2="8" y2="17"/>
            <polyline points="10 9 9 9 8 9"/>
          </svg>
        </div>
        <div class="status-body">
          <span>PDF</span>
          <strong>{{ ragStatus?.pdf_parser_command || ragStatus?.pdf_parser || "unknown" }}</strong>
        </div>
      </article>
      <article class="status-card">
        <div class="status-icon" :class="ragStatus?.llm_api_key_configured ? 'ok' : 'bad'">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <path d="M21 2l-2 2m-7.61 7.61a5.5 5.5 0 1 1-7.778 7.778 5.5 5.5 0 0 1 7.777-7.777zm0 0L15.5 7.5m0 0l3 3L22 7l-3-3m-3.5 3.5L19 4"/>
          </svg>
        </div>
        <div class="status-body">
          <span>LLM Key</span>
          <strong :class="ragStatus?.llm_api_key_configured ? 'ok' : 'bad'">
            {{ ragStatus?.llm_api_key_configured ? "Configured" : "Missing" }}
          </strong>
        </div>
      </article>
    </section>

    <section class="content-panel workspace-panel">
      <div class="panel-heading">
        <div class="heading-icon teal-bg">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/>
          </svg>
        </div>
        <div>
          <h3>工作目录</h3>
          <p>设置当前对话使用的本地项目目录。</p>
        </div>
      </div>
      <div class="workspace-config">
        <label class="workspace-field">
          <span>工作目录</span>
          <WorkspaceDirectoryPicker
            v-model="workspaceRootModel"
            placeholder="E:\2026_Spring\Course Notes"
            @error="handleDirectoryPickerError"
          />
        </label>
        <button class="primary" type="button" :disabled="!workspaceRootModel.trim()" @click="saveWorkspaceRoot">
          保存目录
        </button>
      </div>
    </section>

    <!-- Two Column Layout -->
    <main class="rag-layout">
      <!-- Directory Permissions -->
      <section class="content-panel">
        <div class="panel-heading">
          <div class="heading-icon">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/>
            </svg>
          </div>
          <div>
            <h3>目录权限</h3>
            <p>模型只能索引这里授权过的目录，默认目录也必须在授权目录内。</p>
          </div>
        </div>

        <form class="config-form" @submit.prevent="addAllowedRoot">
          <label class="full">
            <span>授权目录</span>
            <input v-model="newRoot" type="text" placeholder="E:\2026_Spring\Course Notes" />
          </label>
          <div class="actions full">
            <WorkspaceDirectoryPicker
              v-model="newRoot"
              button-only
              :disabled="saving"
              @error="handleDirectoryPickerError"
            />
            <button type="submit" class="primary" :disabled="saving || !newRoot.trim()">添加目录</button>
          </div>
        </form>

        <div v-if="settings.allowed_roots.length" class="root-list">
          <article v-for="root in settings.allowed_roots" :key="root" class="root-row">
            <div class="root-info">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/>
              </svg>
              <code>{{ root }}</code>
            </div>
            <div class="root-actions">
              <button class="ghost" @click="makeDefault(root)">设为默认</button>
              <button class="danger" @click="removeAllowedRoot(root)">移除</button>
            </div>
          </article>
        </div>
        <p v-else class="empty-hint">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <circle cx="12" cy="12" r="10"/>
            <line x1="12" y1="8" x2="12" y2="12"/>
            <line x1="12" y1="16" x2="12.01" y2="16"/>
          </svg>
          还没有授权目录。先添加一个课程资料文件夹。
        </p>

        <form class="config-form default-form" @submit.prevent="saveDefaultRoot">
          <label class="full">
            <span>默认 RAG 目录</span>
            <input v-model="defaultRootDraft" type="text" placeholder="必须位于某个授权目录内" list="allowed-root-options" />
            <datalist id="allowed-root-options">
              <option v-for="root in settings.allowed_roots" :key="root" :value="root" />
            </datalist>
          </label>
          <label class="checkbox-field">
            <input v-model="settings.recursive_default" type="checkbox" />
            <span>默认递归索引</span>
          </label>
          <div class="actions">
            <button type="submit" class="primary" :disabled="saving">保存</button>
          </div>
        </form>
      </section>

      <!-- Indexing -->
      <section class="content-panel">
        <div class="panel-heading">
          <div class="heading-icon teal-bg">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <ellipse cx="12" cy="5" rx="9" ry="3"/>
              <path d="M21 12c0 1.66-4 3-9 3s-9-1.34-9-3"/>
              <path d="M3 5v14c0 1.66 4 3 9 3s9-1.34 9-3V5"/>
            </svg>
          </div>
          <div>
            <h3>索引</h3>
            <p>默认索引当前默认目录，也可以填授权目录内的相对路径或绝对子目录。</p>
          </div>
        </div>

        <form class="config-form" @submit.prevent="indexKnowledge">
          <label class="full">
            <span>索引路径</span>
            <input v-model="indexPath" type="text" placeholder="留空或 . 表示默认目录" />
          </label>
          <label class="checkbox-field">
            <input v-model="indexRecursive" type="checkbox" />
            <span>递归索引子目录</span>
          </label>
          <div class="actions">
            <button type="submit" class="primary" :disabled="indexing || !canIndex">
              {{ indexing ? "索引中..." : "开始索引" }}
            </button>
          </div>
        </form>

        <div class="summary-strip">
          <div class="summary-item">
            <span>Sources</span>
            <strong>{{ sources.length }}</strong>
          </div>
          <div class="summary-item ok">
            <span>Indexed</span>
            <strong>{{ sourceCounts.indexed }}</strong>
          </div>
          <div class="summary-item bad">
            <span>Failed</span>
            <strong>{{ sourceCounts.failed }}</strong>
          </div>
          <div class="summary-item">
            <span>Processing</span>
            <strong>{{ sourceCounts.processing }}</strong>
          </div>
        </div>
      </section>
    </main>

    <!-- Query Test -->
    <section class="content-panel full">
      <div class="panel-heading">
        <div class="heading-icon purple-bg">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <circle cx="11" cy="11" r="8"/>
            <line x1="21" y1="21" x2="16.65" y2="16.65"/>
          </svg>
        </div>
        <div>
          <h3>检索测试</h3>
          <p>快速确认资料是否已可被模型回答。</p>
        </div>
      </div>
      <form class="query-row" @submit.prevent="queryKnowledge">
        <div class="search-box">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <circle cx="11" cy="11" r="8"/>
            <line x1="21" y1="21" x2="16.65" y2="16.65"/>
          </svg>
          <input v-model="queryText" type="text" placeholder="例如：根据资料，add/drop deadline 是什么时候？" />
        </div>
        <button type="submit" class="primary" :disabled="querying || !queryText.trim()">
          {{ querying ? "查询中..." : "查询" }}
        </button>
      </form>
      <div v-if="queryResult" class="answer-box">
        <p class="answer-text">{{ queryResult.answer }}</p>
        <div v-if="queryResult.citations?.length" class="citation-list">
          <span class="citation-label">引用来源</span>
          <div class="citation-pills">
            <span v-for="hit in queryResult.citations" :key="hit.chunk_id" class="citation-pill">
              {{ hit.relative_path }} · chunk {{ hit.position }}
            </span>
          </div>
        </div>
      </div>
    </section>

    <!-- Sources -->
    <section class="content-panel full sources-section">
      <div class="panel-heading">
        <div class="heading-icon green-bg">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
            <polyline points="14 2 14 8 20 8"/>
            <line x1="16" y1="13" x2="8" y2="13"/>
            <line x1="16" y1="17" x2="8" y2="17"/>
            <polyline points="10 9 9 9 8 9"/>
          </svg>
        </div>
        <div>
          <h3>已索引来源</h3>
          <p>查看每个文件的状态，失败文件会保留错误原因。</p>
        </div>
        <button class="icon-refresh" :disabled="sourcesLoading" @click="loadSources" title="刷新来源">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <path d="M21 12a9 9 0 0 1-15.4 6.4L3 16" />
            <path d="M3 21v-5h5" />
            <path d="M3 12a9 9 0 0 1 15.4-6.4L21 8" />
            <path d="M16 8h5V3" />
          </svg>
        </button>
      </div>

      <div v-if="sources.length" class="source-table">
        <div class="source-thead">
          <span>文件</span>
          <span>类型</span>
          <span>时间</span>
          <span>状态</span>
          <span></span>
        </div>
        <article v-for="source in sources" :key="source.id" class="source-row">
          <div class="source-file">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
              <polyline points="14 2 14 8 20 8"/>
            </svg>
            <div class="file-info">
              <strong>{{ source.relative_path }}</strong>
              <small v-if="source.error" class="error-text">{{ source.error }}</small>
            </div>
          </div>
          <span class="file-meta">{{ source.extension }}</span>
          <span class="file-meta">{{ formatTime(source.updated_at) }}</span>
          <span :class="['status-pill', source.status]">{{ source.status }}</span>
          <button class="danger" @click="deleteSource(source.id)">删除</button>
        </article>
      </div>
      <p v-else class="empty-hint">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <circle cx="12" cy="12" r="10"/>
          <line x1="12" y1="8" x2="12" y2="12"/>
          <line x1="12" y1="16" x2="12.01" y2="16"/>
        </svg>
        还没有索引来源。
      </p>
    </section>
  </section>
</template>

<script setup>
import { computed, onMounted, reactive, ref, watch } from "vue";
import WorkspaceDirectoryPicker from "./WorkspaceDirectoryPicker.vue";
import { apiClient } from "../api/client";

const props = defineProps({
  workspaceRoot: {
    type: String,
    default: ""
  }
});

const emit = defineEmits(["update:workspaceRoot"]);

const loading = ref(false);
const saving = ref(false);
const indexing = ref(false);
const querying = ref(false);
const sourcesLoading = ref(false);
const newRoot = ref("");
const defaultRootDraft = ref("");
const indexPath = ref(".");
const indexRecursive = ref(true);
const queryText = ref("");
const queryResult = ref(null);
const ragStatus = ref(null);
const sources = ref([]);
const settings = reactive({
  allowed_roots: [],
  default_root: null,
  recursive_default: true
});
const message = reactive({ text: "", type: "info" });

const workspaceRootModel = computed({
  get: () => props.workspaceRoot || "",
  set: (value) => emit("update:workspaceRoot", value)
});

const canIndex = computed(() => Boolean(settings.default_root || indexPath.value.trim()));
const sourceCounts = computed(() => {
  return sources.value.reduce(
    (acc, source) => {
      acc[source.status] = (acc[source.status] || 0) + 1;
      return acc;
    },
    { indexed: 0, failed: 0, processing: 0 }
  );
});

watch(
  () => settings.recursive_default,
  (value) => {
    indexRecursive.value = value;
  }
);

function showMessage(text, type = "info") {
  message.text = text;
  message.type = type;
}

function handleDirectoryPickerError(error) {
  showMessage(`目录选择失败：${error.message}`, "error");
}

function saveWorkspaceRoot() {
  const root = workspaceRootModel.value.trim();
  if (!root) return;
  emit("update:workspaceRoot", root);
  showMessage("工作目录已保存。", "success");
}

function applySettings(payload) {
  settings.allowed_roots = payload?.allowed_roots || [];
  settings.default_root = payload?.default_root || null;
  settings.recursive_default = payload?.recursive_default ?? true;
  defaultRootDraft.value = settings.default_root || "";
  indexRecursive.value = settings.recursive_default;
}

async function loadStatus() {
  const response = await apiClient.get("/rag/status");
  ragStatus.value = response.data?.data || null;
}

async function loadSettings() {
  const response = await apiClient.get("/rag/settings");
  applySettings(response.data?.data || {});
}

async function loadSources() {
  sourcesLoading.value = true;
  try {
    const response = await apiClient.get("/rag/sources");
    sources.value = response.data?.data || [];
  } finally {
    sourcesLoading.value = false;
  }
}

async function loadAll() {
  loading.value = true;
  try {
    await Promise.all([loadStatus(), loadSettings(), loadSources()]);
  } catch (error) {
    showMessage(`加载知识库配置失败：${error.message}`, "error");
  } finally {
    loading.value = false;
  }
}

async function saveSettings(nextSettings = settings) {
  saving.value = true;
  try {
    const response = await apiClient.put("/rag/settings", {
      allowed_roots: [...nextSettings.allowed_roots],
      default_root: nextSettings.default_root || null,
      recursive_default: Boolean(nextSettings.recursive_default)
    });
    applySettings(response.data?.data || {});
    showMessage("RAG 目录设置已保存。", "success");
  } catch (error) {
    showMessage(`保存失败：${error.message}`, "error");
  } finally {
    saving.value = false;
  }
}

async function addAllowedRoot() {
  const root = newRoot.value.trim();
  if (!root) return;
  const nextRoots = [...settings.allowed_roots, root];
  await saveSettings({
    allowed_roots: nextRoots,
    default_root: settings.default_root || root,
    recursive_default: settings.recursive_default
  });
  newRoot.value = "";
}

async function removeAllowedRoot(root) {
  const nextRoots = settings.allowed_roots.filter((item) => item !== root);
  const nextDefault = isInside(settings.default_root, root) ? nextRoots[0] || null : settings.default_root;
  await saveSettings({
    allowed_roots: nextRoots,
    default_root: nextDefault,
    recursive_default: settings.recursive_default
  });
}

async function makeDefault(root) {
  defaultRootDraft.value = root;
  await saveSettings({
    allowed_roots: settings.allowed_roots,
    default_root: root,
    recursive_default: settings.recursive_default
  });
}

async function saveDefaultRoot() {
  await saveSettings({
    allowed_roots: settings.allowed_roots,
    default_root: defaultRootDraft.value.trim() || null,
    recursive_default: settings.recursive_default
  });
}

async function indexKnowledge() {
  indexing.value = true;
  queryResult.value = null;
  try {
    await loadStatus();
    if (ragStatus.value && !ragStatus.value.ready) {
      showMessage(`RAG 未就绪：${(ragStatus.value.issues || []).join(" ")}`, "error");
      return;
    }
    const response = await apiClient.post("/rag/index-folder", {
      path: indexPath.value.trim() || ".",
      recursive: indexRecursive.value
    });
    const summary = response.data?.data;
    showMessage(
      `索引完成：${summary?.indexed || 0} indexed, ${summary?.skipped || 0} skipped, ${summary?.failed || 0} failed`,
      summary?.failed ? "error" : "success"
    );
    await loadSources();
  } catch (error) {
    showMessage(`索引失败：${error.message}`, "error");
  } finally {
    indexing.value = false;
  }
}

async function queryKnowledge() {
  querying.value = true;
  queryResult.value = null;
  try {
    const response = await apiClient.post("/rag/query", {
      query: queryText.value.trim(),
      top_k: 5
    });
    queryResult.value = response.data?.data || null;
  } catch (error) {
    showMessage(`查询失败：${error.message}`, "error");
  } finally {
    querying.value = false;
  }
}

async function deleteSource(sourceId) {
  try {
    await apiClient.delete(`/rag/sources/${encodeURIComponent(sourceId)}`);
    sources.value = sources.value.filter((source) => source.id !== sourceId);
    showMessage("知识来源已删除。", "success");
  } catch (error) {
    showMessage(`删除失败：${error.message}`, "error");
  }
}

function isInside(path, root) {
  if (!path || !root) return false;
  const normalizedPath = path.replaceAll("\\", "/").toLowerCase();
  const normalizedRoot = root.replaceAll("\\", "/").toLowerCase();
  return normalizedPath === normalizedRoot || normalizedPath.startsWith(`${normalizedRoot}/`);
}

function formatTime(value) {
  if (!value) return "never";
  return new Date(value).toLocaleString();
}

onMounted(loadAll);
</script>

<style scoped>
/* ===== Panel Container ===== */
.rag-panel {
  height: 100%;
  overflow-y: auto;
  padding: 28px;
  display: flex;
  flex-direction: column;
  gap: 18px;
  background:
    radial-gradient(circle at top left, rgba(249, 115, 22, 0.06), transparent 24%),
    radial-gradient(circle at bottom right, rgba(31, 111, 120, 0.06), transparent 28%),
    linear-gradient(180deg, rgba(255, 255, 255, 0.72), rgba(255, 255, 255, 0.66)),
    var(--bg-main-soft);
  color: var(--ink);
}

/* ===== Header ===== */
.rag-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 16px;
}

.header-text h2 {
  margin: 4px 0 6px;
  font-family: var(--font-heading);
  font-size: 26px;
  font-weight: 700;
  color: var(--text-primary);
  letter-spacing: -0.02em;
}

.header-desc {
  margin: 0;
  font-size: 13px;
  color: var(--text-muted);
  max-width: 520px;
  line-height: 1.5;
}

.eyebrow {
  margin: 0 0 4px;
  color: var(--accent-orange);
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.12em;
  text-transform: uppercase;
}

.icon-refresh {
  width: 42px;
  height: 42px;
  border: none;
  border-radius: 14px;
  background: rgba(255, 255, 255, 0.88);
  color: var(--text-secondary);
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  transition: all 0.2s ease;
  flex-shrink: 0;
  box-shadow: 0 4px 12px var(--shadow-subtle);
}

.icon-refresh:hover {
  background: white;
  color: var(--accent-orange);
  transform: scale(1.06);
  box-shadow: 0 8px 20px var(--shadow-sm);
}

.icon-refresh:disabled {
  opacity: 0.5;
  cursor: not-allowed;
  transform: none;
}

/* ===== Notice Toast ===== */
.notice-toast {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 16px;
  border-radius: 14px;
  font-size: 13px;
  font-weight: 500;
  border: 1px solid transparent;
  animation: slideDown 0.3s ease;
}

@keyframes slideDown {
  from { opacity: 0; transform: translateY(-8px); }
  to { opacity: 1; transform: translateY(0); }
}

.notice-toast.error {
  color: #dc2626;
  background: rgba(239, 68, 68, 0.08);
  border-color: rgba(239, 68, 68, 0.15);
}

.notice-toast.success {
  color: #15803d;
  background: rgba(34, 197, 94, 0.08);
  border-color: rgba(34, 197, 94, 0.15);
}

.notice-toast.info {
  color: var(--text-secondary);
  background: rgba(255, 255, 255, 0.82);
  border-color: var(--border-light);
}

.notice-toast button {
  width: 28px;
  height: 28px;
  border: none;
  border-radius: 8px;
  background: transparent;
  color: inherit;
  font-size: 18px;
  line-height: 1;
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  opacity: 0.6;
  transition: all 0.15s ease;
}

.notice-toast button:hover {
  opacity: 1;
  background: rgba(0, 0, 0, 0.05);
}

/* ===== Status Grid ===== */
.status-grid {
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  gap: 12px;
}

.status-card {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 14px 16px;
  border-radius: 18px;
  background: rgba(255, 255, 255, 0.88);
  border: 1px solid rgba(148, 163, 184, 0.14);
  box-shadow: 0 4px 14px var(--shadow-subtle);
  transition: all 0.2s ease;
}

.status-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 10px 24px var(--shadow-sm);
}

.status-icon {
  width: 36px;
  height: 36px;
  border-radius: 12px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  background: rgba(148, 163, 184, 0.12);
  color: var(--text-muted);
}

.status-icon.ok {
  background: rgba(34, 197, 94, 0.12);
  color: #15803d;
}

.status-icon.bad {
  background: rgba(239, 68, 68, 0.12);
  color: #dc2626;
}

.status-icon.teal {
  background: rgba(31, 111, 120, 0.12);
  color: var(--accent);
}

.status-icon.blue {
  background: rgba(59, 130, 246, 0.12);
  color: #2563eb;
}

.status-icon.amber {
  background: rgba(245, 158, 11, 0.12);
  color: #d97706;
}

.status-body {
  display: grid;
  gap: 4px;
  min-width: 0;
}

.status-body span {
  font-size: 11px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  color: var(--text-muted);
}

.status-body strong {
  font-size: 14px;
  color: var(--text-primary);
  word-break: break-word;
}

.status-body strong.ok {
  color: #15803d;
}

.status-body strong.bad {
  color: #dc2626;
}

/* ===== Layout ===== */
.rag-layout {
  display: grid;
  grid-template-columns: minmax(0, 1.15fr) minmax(320px, 0.85fr);
  gap: 18px;
}

/* ===== Content Panel ===== */
.content-panel {
  display: flex;
  flex-direction: column;
  gap: 16px;
  padding: 22px;
  border-radius: 22px;
  background: rgba(255, 255, 255, 0.88);
  border: 1px solid rgba(148, 163, 184, 0.14);
  box-shadow: 0 12px 30px rgba(28, 36, 48, 0.06);
}

.content-panel.full {
  width: 100%;
}

.workspace-panel {
  gap: 18px;
}

.workspace-config {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 16px;
  align-items: end;
}

.workspace-field {
  min-width: 0;
}

.panel-heading {
  display: flex;
  align-items: flex-start;
  gap: 14px;
}

.panel-heading h3 {
  margin: 0 0 4px;
  font-family: var(--font-heading);
  font-size: 18px;
  font-weight: 700;
  color: var(--text-primary);
}

.panel-heading p {
  margin: 0;
  font-size: 13px;
  color: var(--text-muted);
  line-height: 1.5;
}

.heading-icon {
  width: 40px;
  height: 40px;
  border-radius: 14px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  background: rgba(249, 115, 22, 0.1);
  color: var(--accent-orange);
}

.heading-icon.teal-bg {
  background: rgba(31, 111, 120, 0.1);
  color: var(--accent);
}

.heading-icon.purple-bg {
  background: rgba(139, 92, 246, 0.1);
  color: #7c3aed;
}

.heading-icon.green-bg {
  background: rgba(34, 197, 94, 0.1);
  color: #15803d;
}

/* ===== Forms ===== */
.config-form {
  display: grid;
  gap: 14px;
}

.config-form.default-form {
  padding-top: 14px;
  border-top: 1px solid var(--border-subtle);
}

label {
  display: grid;
  gap: 6px;
}

label span {
  font-size: 12px;
  font-weight: 700;
  color: var(--text-secondary);
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

input {
  box-sizing: border-box;
  width: 100%;
  padding: 12px 14px;
  border-radius: 14px;
  border: 1px solid var(--border-light);
  background: white;
  font-size: 14px;
  color: var(--text-primary);
  transition: all 0.2s ease;
}

input:focus {
  outline: none;
  border-color: var(--accent-orange);
  box-shadow: 0 0 0 4px var(--accent-orange-subtle);
}

input::placeholder {
  color: var(--text-placeholder);
}

.checkbox-field {
  display: inline-flex;
  align-items: center;
  gap: 10px;
  cursor: pointer;
}

.checkbox-field input {
  width: 18px;
  height: 18px;
  accent-color: var(--accent-orange);
  cursor: pointer;
}

.checkbox-field span {
  font-size: 13px;
  font-weight: 500;
  text-transform: none;
  letter-spacing: normal;
  color: var(--text-secondary);
}

.actions {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
}

.actions.full {
  grid-column: 1 / -1;
}

button.primary {
  padding: 11px 20px;
  border: none;
  border-radius: 12px;
  background: linear-gradient(135deg, var(--accent-orange), #ee8a3a);
  color: white;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s ease;
  box-shadow: 0 6px 16px rgba(218, 106, 30, 0.22);
}

button.primary:hover {
  background: #EA580C;
  transform: translateY(-1px);
  box-shadow: 0 10px 24px rgba(218, 106, 30, 0.28);
}

button.primary:disabled {
  opacity: 0.55;
  cursor: not-allowed;
  transform: none;
  box-shadow: none;
}

button.ghost {
  padding: 8px 14px;
  border: none;
  border-radius: 10px;
  background: transparent;
  color: var(--text-secondary);
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.15s ease;
}

button.ghost:hover {
  background: rgba(31, 41, 55, 0.06);
  color: var(--text-primary);
}

button.danger {
  padding: 8px 14px;
  border: 1px solid rgba(239, 68, 68, 0.25);
  border-radius: 10px;
  background: transparent;
  color: #dc2626;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.15s ease;
}

button.danger:hover {
  background: rgba(239, 68, 68, 0.08);
  border-color: rgba(239, 68, 68, 0.4);
}

/* ===== Root List ===== */
.root-list {
  display: grid;
  gap: 8px;
}

.root-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  padding: 12px 14px;
  border-radius: 14px;
  background: white;
  border: 1px solid var(--border-subtle);
  transition: all 0.15s ease;
}

.root-row:hover {
  border-color: var(--border-light);
  box-shadow: 0 4px 12px var(--shadow-subtle);
}

.root-info {
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 0;
  color: var(--text-muted);
}

.root-info code {
  font-size: 13px;
  color: var(--text-primary);
  word-break: break-all;
  font-family: var(--font-mono);
  background: rgba(31, 41, 55, 0.04);
  padding: 2px 6px;
  border-radius: 6px;
}

.root-actions {
  display: flex;
  gap: 6px;
  flex-shrink: 0;
}

.empty-hint {
  display: flex;
  align-items: center;
  gap: 8px;
  margin: 0;
  padding: 16px;
  border-radius: 14px;
  background: rgba(31, 41, 55, 0.02);
  border: 1px dashed var(--border-light);
  color: var(--text-muted);
  font-size: 13px;
}

.empty-hint svg {
  flex-shrink: 0;
  opacity: 0.6;
}

/* ===== Summary Strip ===== */
.summary-strip {
  display: flex;
  gap: 16px;
  flex-wrap: wrap;
  padding: 14px 16px;
  border-radius: 16px;
  background: rgba(31, 41, 55, 0.02);
  border: 1px solid var(--border-subtle);
}

.summary-item {
  display: flex;
  align-items: baseline;
  gap: 6px;
}

.summary-item span {
  font-size: 12px;
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 0.04em;
  font-weight: 600;
}

.summary-item strong {
  font-size: 18px;
  color: var(--text-primary);
  font-weight: 700;
}

.summary-item.ok strong {
  color: #15803d;
}

.summary-item.bad strong {
  color: #dc2626;
}

/* ===== Query Section ===== */
.query-row {
  display: flex;
  align-items: center;
  gap: 12px;
}

.search-box {
  flex: 1;
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 4px;
  border-radius: 16px;
  background: white;
  border: 1px solid var(--border-light);
  transition: all 0.2s ease;
}

.search-box:focus-within {
  border-color: var(--accent-orange);
  box-shadow: 0 0 0 4px var(--accent-orange-subtle);
}

.search-box svg {
  margin-left: 12px;
  color: var(--text-muted);
  flex-shrink: 0;
}

.search-box input {
  flex: 1;
  border: none;
  background: transparent;
  box-shadow: none;
  padding: 10px 8px;
}

.search-box input:focus {
  border: none;
  box-shadow: none;
}

.answer-box {
  display: grid;
  gap: 14px;
  padding: 18px;
  border-radius: 18px;
  background: rgba(255, 255, 255, 0.72);
  border: 1px solid var(--border-subtle);
}

.answer-text {
  margin: 0;
  font-size: 14px;
  line-height: 1.7;
  color: var(--ink);
}

.citation-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.citation-label {
  font-size: 11px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: var(--text-muted);
}

.citation-pills {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.citation-pill {
  padding: 6px 12px;
  border-radius: 999px;
  background: rgba(31, 111, 120, 0.08);
  color: var(--accent);
  font-size: 12px;
  font-weight: 600;
  font-family: var(--font-mono);
}

/* ===== Sources Table ===== */
.sources-section .panel-heading {
  justify-content: space-between;
}

.source-table {
  display: grid;
  gap: 1px;
  border-radius: 16px;
  background: var(--border-subtle);
  overflow: hidden;
  border: 1px solid var(--border-subtle);
}

.source-thead {
  display: grid;
  grid-template-columns: 2fr 80px 160px 100px 80px;
  gap: 12px;
  padding: 10px 16px;
  background: rgba(31, 41, 55, 0.03);
  font-size: 11px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  color: var(--text-muted);
}

.source-row {
  display: grid;
  grid-template-columns: 2fr 80px 160px 100px 80px;
  gap: 12px;
  align-items: center;
  padding: 12px 16px;
  background: white;
  transition: all 0.15s ease;
}

.source-row:hover {
  background: rgba(249, 115, 22, 0.02);
}

.source-file {
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 0;
  color: var(--text-muted);
}

.source-file svg {
  flex-shrink: 0;
}

.file-info {
  display: grid;
  gap: 2px;
  min-width: 0;
}

.file-info strong {
  font-size: 13px;
  color: var(--text-primary);
  font-weight: 600;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.file-info .error-text {
  color: #dc2626;
  font-size: 11px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.file-meta {
  font-size: 12px;
  color: var(--text-muted);
  font-family: var(--font-mono);
}

.status-pill {
  display: inline-flex;
  justify-content: center;
  align-items: center;
  padding: 5px 10px;
  border-radius: 999px;
  font-size: 11px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  background: rgba(148, 163, 184, 0.12);
  color: var(--text-muted);
}

.status-pill.failed {
  color: #dc2626;
  background: rgba(239, 68, 68, 0.1);
}

.status-pill.indexed {
  color: #15803d;
  background: rgba(34, 197, 94, 0.1);
}

.status-pill.processing {
  color: #2563eb;
  background: rgba(59, 130, 246, 0.1);
}

/* ===== Responsive ===== */
@media (max-width: 980px) {
  .rag-layout {
    grid-template-columns: 1fr;
  }

  .status-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .workspace-config {
    grid-template-columns: 1fr;
  }

  .source-thead,
  .source-row {
    grid-template-columns: 1fr 80px;
  }

  .source-thead span:nth-child(3),
  .source-thead span:nth-child(4),
  .source-thead span:nth-child(5),
  .source-row .file-meta,
  .source-row .status-pill,
  .source-row button {
    display: none;
  }

  .source-row button {
    display: inline-flex;
  }
}

@media (max-width: 640px) {
  .rag-panel {
    padding: 16px;
  }

  .status-grid {
    grid-template-columns: 1fr;
  }

  .query-row {
    flex-direction: column;
    align-items: stretch;
  }

  .root-row {
    flex-direction: column;
    align-items: flex-start;
  }
}
</style>
