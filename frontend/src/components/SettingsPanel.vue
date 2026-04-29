<template>
  <section class="settings-panel">
    <header class="settings-header">
      <div class="header-title">
        <p class="eyebrow">运行设置</p>
        <h2>服务与工具配置中心</h2>
        <p class="header-copy">左侧选择配置分组，右侧只展示当前分组的设置内容。</p>
      </div>
      <div class="header-actions">
        <span class="badge" :class="{ ready: state.api_key_configured || bbState.password_configured }">
          {{ state.api_key_configured || bbState.password_configured ? "部分已就绪" : "等待配置" }}
        </span>
        <button type="button" class="collapse-btn" @click="navCollapsed = !navCollapsed">
          {{ navCollapsed ? "展开导航" : "折叠导航" }}
        </button>
        <button type="button" class="close-btn" @click="$emit('close')">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <line x1="18" y1="6" x2="6" y2="18" />
            <line x1="6" y1="6" x2="18" y2="18" />
          </svg>
          关闭
        </button>
      </div>
    </header>

    <div class="settings-layout">
      <aside :class="['settings-nav', { collapsed: navCollapsed }]">
        <button
          v-for="item in sections"
          :key="item.id"
          type="button"
          :class="['nav-item', { active: activeSection === item.id }]"
          @click="activeSection = item.id"
        >
          <span class="nav-icon">{{ item.icon }}</span>
          <span v-if="!navCollapsed" class="nav-copy">
            <strong>{{ item.label }}</strong>
            <small>{{ item.description }}</small>
          </span>
        </button>
      </aside>

      <div class="settings-content">
        <template v-if="activeSection === 'llm'">
          <section class="content-panel hero-panel">
            <div class="panel-heading">
              <div>
                <p class="eyebrow">LLM</p>
                <h3>模型与网关配置</h3>
              </div>
              <span class="badge" :class="{ ready: state.api_key_configured }">
                {{ state.api_key_configured ? "已加载密钥" : "缺少密钥" }}
              </span>
            </div>
            <p class="hint">
              API 密钥仅发送到后端并存储在服务器内存中，不会返回浏览器。服务重启后需要重新注入。
            </p>

            <div class="status-grid">
              <article class="status-card">
                <span>当前提供商</span>
                <strong>{{ state.provider || "未设置" }}</strong>
              </article>
              <article class="status-card">
                <span>当前模型</span>
                <strong>{{ state.model || "未设置" }}</strong>
              </article>
              <article class="status-card">
                <span>Base URL</span>
                <strong>{{ state.base_url || "默认地址" }}</strong>
              </article>
              <article class="status-card">
                <span>推理模式</span>
                <strong>{{ state.enable_reasoning ? "已启用" : "已禁用" }}</strong>
              </article>
            </div>
          </section>

          <section class="content-panel">
            <div class="section-top">
              <div>
                <strong>已保存的 LLM 配置</strong>
                <p class="hint compact">保存 provider、model、Base URL 等非敏感字段，便于快速切换。</p>
              </div>
              <button type="button" :disabled="saving" @click="openLLMEditorForCreate">新建配置</button>
            </div>

            <div v-if="profiles.length" class="profile-list">
              <article v-for="profile in profiles" :key="profile.name" class="profile-item">
                <div class="profile-info">
                  <strong>{{ profile.name }}</strong>
                  <p>{{ profile.provider }} / {{ profile.model }}</p>
                  <small>{{ profile.base_url || "使用默认 Base URL" }}</small>
                </div>
                <div class="profile-actions">
                  <button type="button" class="apply-btn" :disabled="saving" @click="useProfile(profile)">应用</button>
                  <button type="button" class="secondary action-btn" :disabled="saving" @click="openLLMEditorForEdit(profile)">编辑</button>
                  <button type="button" class="delete-btn" :disabled="saving" @click="removeProfile(profile.name)">删除</button>
                </div>
              </article>
            </div>
            <p v-else class="hint compact">暂无保存的配置。</p>

            <div class="actions inline-actions panel-actions">
              <button type="button" class="secondary" :disabled="saving" @click="refresh">刷新运行时</button>
              <button type="button" class="secondary" :disabled="saving" @click="testConnection">测试连接</button>
            </div>
          </section>

          <section v-if="llmEditorOpen" class="content-panel editor-panel">
            <div class="section-top">
              <div>
                <strong>{{ llmEditorMode === "create" ? "新增 LLM 配置" : "编辑 LLM 配置" }}</strong>
                <p class="hint compact">填写后可保存为配置，也可直接应用到当前运行时。</p>
              </div>
              <button type="button" class="secondary" :disabled="saving" @click="closeLLMEditor">收起</button>
            </div>

            <form class="config-form" @submit.prevent="save">
              <label class="full">
                <span>配置名称</span>
                <input v-model="form.profile_name" placeholder="例如: openai-main 或 deepseek-gateway" autocomplete="off" />
              </label>
              <label>
                <span>提供商</span>
                <select v-model="form.provider">
                  <option value="openai">OpenAI</option>
                  <option value="anthropic">Anthropic</option>
                  <option value="deepseek">DeepSeek</option>
                  <option value="azure">Azure OpenAI</option>
                </select>
              </label>
              <label>
                <span>模型</span>
                <input v-model="form.model" placeholder="例如: gpt-4o-mini" autocomplete="off" />
              </label>
              <label class="full">
                <span>Base URL</span>
                <input v-model="form.base_url" placeholder="https://api.openai.com/v1" autocomplete="off" />
              </label>
              <label class="full">
                <span>API 密钥</span>
                <input
                  v-model="form.api_key"
                  type="password"
                  placeholder="留空以保持当前密钥"
                  autocomplete="new-password"
                />
              </label>
              <label class="toggle-label full">
                <span class="toggle-row">
                  <span>启用推理模式 (DeepSeek R1 等推理模型)</span>
                  <input v-model="form.enable_reasoning" type="checkbox" class="toggle-input" />
                </span>
              </label>
              <div class="actions full">
                <button type="button" class="secondary" :disabled="saving" @click="saveProfile">
                  {{ saving ? "保存中..." : "保存到列表" }}
                </button>
                <button type="submit" :disabled="saving">{{ saving ? "保存中..." : "应用到运行时" }}</button>
              </div>
            </form>
          </section>
        </template>

        <template v-else-if="activeSection === 'bb'">
          <section class="content-panel hero-panel bb-hero">
            <div class="panel-heading">
              <div>
                <p class="eyebrow">Blackboard</p>
                <h3>课程系统登录配置</h3>
              </div>
              <span class="badge" :class="{ ready: bbState.password_configured }">
                {{ bbState.password_configured ? "已配置密码" : "未配置密码" }}
              </span>
            </div>
            <p class="hint">
              这里用于配置 Blackboard 登录信息，供课程同步和日历拉取使用。密码只存在后端运行时内存。
            </p>

            <div class="status-grid">
              <article class="status-card">
                <span>当前学号</span>
                <strong>{{ bbState.student_id || "未设置" }}</strong>
              </article>
              <article class="status-card">
                <span>Base URL</span>
                <strong>{{ bbState.base_url || "默认地址" }}</strong>
              </article>
              <article class="status-card">
                <span>密码状态</span>
                <strong>{{ bbState.password_configured ? "已存在" : "待输入" }}</strong>
              </article>
            </div>
          </section>

          <section class="content-panel">
            <div class="section-top">
              <div>
                <strong>已保存的 Blackboard 配置</strong>
                <p class="hint compact">保存学号和地址，密码会加密存储，方便切换不同账户。</p>
              </div>
              <button type="button" :disabled="saving" @click="openBBEditorForCreate">新建配置</button>
            </div>

            <div v-if="bbProfiles.length" class="profile-list">
              <article v-for="profile in bbProfiles" :key="profile.name" class="profile-item">
                <div class="profile-info">
                  <strong>{{ profile.name }}</strong>
                  <p>{{ profile.student_id }}</p>
                  <small>{{ profile.base_url || "使用默认 Base URL" }}</small>
                </div>
                <div class="profile-actions">
                  <button type="button" class="apply-btn" :disabled="saving" @click="useBBProfile(profile)">应用</button>
                  <button type="button" class="secondary action-btn" :disabled="saving" @click="openBBEditorForEdit(profile)">编辑</button>
                  <button type="button" class="delete-btn" :disabled="saving" @click="removeBBProfile(profile.name)">删除</button>
                </div>
              </article>
            </div>
            <p v-else class="hint compact">暂无保存的配置。</p>

            <div class="actions inline-actions panel-actions">
              <button type="button" class="secondary" :disabled="saving" @click="refreshBlackboard">刷新运行时</button>
              <button type="button" class="secondary" :disabled="saving" @click="testBlackboard">测试连接</button>
            </div>
          </section>

          <section v-if="bbEditorOpen" class="content-panel editor-panel">
            <div class="section-top">
              <div>
                <strong>{{ bbEditorMode === "create" ? "新增 Blackboard 配置" : "编辑 Blackboard 配置" }}</strong>
                <p class="hint compact">填写后可保存为配置，也可直接应用到当前运行时。</p>
              </div>
              <button type="button" class="secondary" :disabled="saving" @click="closeBBEditor">收起</button>
            </div>

            <form class="bb-form" @submit.prevent="saveBlackboard">
              <label class="full">
                <span>配置名称</span>
                <input v-model="bbForm.profile_name" placeholder="例如: bb-main" autocomplete="off" />
              </label>
              <label class="full">
                <span>学号</span>
                <input v-model="bbForm.student_id" placeholder="你的学号" autocomplete="off" />
              </label>
              <label class="full">
                <span>CAS 密码</span>
                <input
                  v-model="bbForm.password"
                  type="password"
                  placeholder="留空以保持当前密码"
                  autocomplete="new-password"
                />
              </label>
              <label class="full">
                <span>Base URL（可选）</span>
                <input v-model="bbForm.base_url" placeholder="https://bb.sustech.edu.cn" autocomplete="off" />
              </label>
              <div class="actions full">
                <button type="button" class="secondary" :disabled="saving" @click="saveBBProfile">
                  {{ saving ? "保存中..." : "保存到列表" }}
                </button>
                <button type="submit" :disabled="saving">{{ saving ? "保存中..." : "应用到运行时" }}</button>
              </div>
            </form>
          </section>
        </template>

        <template v-else-if="activeSection === 'backend'">
          <section class="content-panel hero-panel backend-hero">
            <div class="panel-heading">
              <div>
                <p class="eyebrow">Backend</p>
                <h3>后端服务状态</h3>
              </div>
              <span class="badge" :class="{ ready: backendStatus.healthy }">
                {{ backendStatus.healthy ? "服务在线" : "等待检测" }}
              </span>
            </div>
            <p class="hint">
              这一栏集中展示前端当前连接的后端地址、健康状态，以及依赖它的运行配置摘要。
            </p>
          </section>

          <section class="content-panel">
            <div class="status-grid backend-grid">
              <article class="status-card wide">
                <span>API Base</span>
                <strong>{{ backendBaseUrl }}</strong>
                <small>前端所有设置、聊天、课程与日程请求都通过这个入口访问后端。</small>
              </article>
              <article class="status-card">
                <span>健康状态</span>
                <strong>{{ backendStatus.healthy ? "Healthy" : "Unknown" }}</strong>
                <small>{{ backendStatus.message }}</small>
              </article>
              <article class="status-card">
                <span>LLM 运行时</span>
                <strong>{{ state.provider }} / {{ state.model }}</strong>
                <small>{{ state.api_key_configured ? "已注入密钥" : "缺少密钥" }}</small>
              </article>
              <article class="status-card">
                <span>Blackboard 运行时</span>
                <strong>{{ bbState.student_id || "未设置账号" }}</strong>
                <small>{{ bbState.password_configured ? "密码可用" : "密码未配置" }}</small>
              </article>
            </div>

            <div class="actions inline-actions">
              <button type="button" class="secondary" :disabled="saving" @click="checkBackendHealth">检查健康状态</button>
              <button type="button" class="secondary" :disabled="saving" @click="refreshAll">刷新全部设置</button>
            </div>
          </section>
        </template>

        <template v-else-if="activeSection === 'dev'">
          <section class="content-panel hero-panel developer-panel">
            <div class="panel-heading">
              <div>
                <p class="eyebrow">Developer</p>
                <h3>开发者工具</h3>
              </div>
              <span class="badge" :class="{ ready: showDeveloperTools }">
                {{ showDeveloperTools ? "开发模式" : "生产模式" }}
              </span>
            </div>
            <p class="hint">
              集中放调试入口，避免和运行配置混在一起。如果不是本地开发环境，这里会保持只读提示。
            </p>
          </section>

          <section class="content-panel">
            <div v-if="showDeveloperTools" class="dev-actions">
              <article class="dev-card">
                <div>
                  <strong>数据库视图</strong>
                  <p>打开后端数据库概览，用于课程演示和本地调试。</p>
                </div>
                <button type="button" :disabled="saving" @click="$emit('open-database-overview')">打开数据库视图</button>
              </article>

              <article class="dev-card">
                <div>
                  <strong>运行时刷新</strong>
                  <p>同步检查后端状态、LLM 配置和 Blackboard 配置，确认当前页面状态没有过期。</p>
                </div>
                <button type="button" :disabled="saving" @click="refreshAll">执行刷新</button>
              </article>
            </div>
            <p v-else class="hint">当前不是开发模式，开发者工具已隐藏。</p>
          </section>
        </template>

      </div>
    </div>

    <transition name="toast-fade">
      <p v-if="message" class="result" :class="{ error: messageType === 'error' }">{{ message }}</p>
    </transition>
  </section>
</template>

<script setup>
import { onBeforeUnmount, onMounted, reactive, ref, watch } from "vue";
import {
  applyBBProfile,
  applyLLMProfile,
  deleteBBProfile,
  deleteLLMProfile,
  getBBProfiles,
  getBlackboardSettings,
  getHealth,
  getLLMProfiles,
  getLLMSettings,
  saveBBProfile as saveBBProfileAPI,
  saveLLMProfile,
  testBlackboardSettings,
  testLLMSettings,
  updateBlackboardSettings,
  updateLLMSettings
} from "../api/client";

defineEmits(["close", "open-database-overview"]);

const showDeveloperTools = import.meta.env.DEV;
const backendBaseUrl = "http://127.0.0.1:8000/api";
const navCollapsed = ref(false);
const activeSection = ref("llm");
const llmEditorOpen = ref(false);
const llmEditorMode = ref("create");
const bbEditorOpen = ref(false);
const bbEditorMode = ref("create");
const saving = ref(false);
const message = ref("");
const messageType = ref("info");
const profiles = ref([]);
const bbProfiles = ref([]);
let messageTimer = null;

const sections = [
  { id: "llm", label: "LLM 后端", description: "模型、网关与密钥", icon: "AI" },
  { id: "bb", label: "Blackboard", description: "课程系统登录", icon: "BB" },
  { id: "backend", label: "后端服务", description: "状态与联通性", icon: "BE" },
  { id: "dev", label: "开发者工具", description: "数据库与调试入口", icon: "DV" }
];

const backendStatus = reactive({
  healthy: false,
  message: "尚未检测"
});

const state = reactive({
  provider: "openai",
  model: "gpt-4o-mini",
  base_url: "",
  api_key_configured: false,
  enable_reasoning: false
});

const bbState = reactive({
  student_id: "",
  base_url: "",
  password_configured: false
});

const form = reactive({
  profile_name: "",
  provider: "openai",
  model: "gpt-4o-mini",
  base_url: "",
  api_key: "",
  enable_reasoning: false
});

const bbForm = reactive({
  profile_name: "",
  student_id: "",
  password: "",
  base_url: "",
  replace_password: false
});

function clearMessage() {
  message.value = "";
  if (messageTimer) {
    clearTimeout(messageTimer);
    messageTimer = null;
  }
}

function showMessage(text, type = "info") {
  message.value = text;
  messageType.value = type;
  if (messageTimer) {
    clearTimeout(messageTimer);
  }
  messageTimer = window.setTimeout(() => {
    message.value = "";
    messageTimer = null;
  }, 10000);
}

function applyState(payload) {
  state.provider = payload.provider;
  state.model = payload.model;
  state.base_url = payload.base_url ?? "";
  state.api_key_configured = Boolean(payload.api_key_configured);
  state.enable_reasoning = Boolean(payload.enable_reasoning);
  form.provider = payload.provider;
  form.model = payload.model;
  form.base_url = payload.base_url ?? "";
  form.enable_reasoning = Boolean(payload.enable_reasoning);
  form.api_key = "";
}

function closeLLMEditor() {
  llmEditorOpen.value = false;
}

function openLLMEditorForCreate() {
  llmEditorMode.value = "create";
  llmEditorOpen.value = true;
  form.profile_name = "";
  form.provider = "openai";
  form.model = "gpt-4o-mini";
  form.base_url = "";
  form.api_key = "";
}

function openLLMEditorForEdit(profile) {
  llmEditorMode.value = "edit";
  llmEditorOpen.value = true;
  form.profile_name = profile.name;
  form.provider = profile.provider;
  form.model = profile.model;
  form.base_url = profile.base_url ?? "";
  form.api_key = "";
}

function applyBBState(payload) {
  bbState.student_id = payload.student_id ?? "";
  bbState.base_url = payload.base_url ?? "";
  bbState.password_configured = Boolean(payload.password_configured);
  bbForm.student_id = payload.student_id ?? "";
  bbForm.base_url = payload.base_url ?? "";
  bbForm.password = "";
  bbForm.replace_password = false;
}

function closeBBEditor() {
  bbEditorOpen.value = false;
}

function openBBEditorForCreate() {
  bbEditorMode.value = "create";
  bbEditorOpen.value = true;
  bbForm.profile_name = "";
  bbForm.student_id = "";
  bbForm.password = "";
  bbForm.base_url = "";
  bbForm.replace_password = false;
}

function openBBEditorForEdit(profile) {
  bbEditorMode.value = "edit";
  bbEditorOpen.value = true;
  bbForm.profile_name = profile.name;
  bbForm.student_id = profile.student_id;
  bbForm.password = "";
  bbForm.base_url = profile.base_url ?? "";
  bbForm.replace_password = false;
}

async function checkBackendHealth() {
  try {
    const response = await getHealth();
    backendStatus.healthy = true;
    backendStatus.message = response.status || "服务响应正常";
  } catch (error) {
    backendStatus.healthy = false;
    backendStatus.message = error.message;
  }
}

async function refreshBlackboard() {
  saving.value = true;
  try {
    const response = await getBlackboardSettings();
    applyBBState(response.data);
    showMessage("Blackboard 配置已加载。");
  } catch (error) {
    showMessage(`加载 Blackboard 配置失败: ${error.message}`, "error");
  } finally {
    saving.value = false;
  }
}

async function saveBlackboard() {
  saving.value = true;
  try {
    const response = await updateBlackboardSettings({
      student_id: bbForm.student_id,
      password: bbForm.password || null,
      base_url: bbForm.base_url || null,
      replace_password: bbForm.replace_password
    });
    applyBBState(response.data);
    closeBBEditor();
    showMessage("Blackboard 配置已保存。密码仅存储在服务器内存中。");
  } catch (error) {
    showMessage(`保存失败: ${error.message}`, "error");
  } finally {
    saving.value = false;
  }
}

async function testBlackboard() {
  saving.value = true;
  try {
    const response = await testBlackboardSettings({
      student_id: bbForm.student_id,
      password: bbForm.password || null,
      base_url: bbForm.base_url || null,
      replace_password: bbForm.replace_password
    });
    if (response.success) {
      showMessage("Blackboard 连接测试成功。");
    } else {
      showMessage(`连接测试失败: ${response.data?.error || "未知错误"}`, "error");
    }
  } catch (error) {
    showMessage(`测试失败: ${error.message}`, "error");
  } finally {
    saving.value = false;
  }
}

function applyProfile(profile) {
  form.profile_name = profile.name;
  form.provider = profile.provider;
  form.model = profile.model;
  form.base_url = profile.base_url ?? "";
  showMessage(`已加载配置 "${profile.name}"。如未设置密钥，请为此运行时设置 API 密钥。`);
}

async function useProfile(profile) {
  saving.value = true;
  try {
    applyProfile(profile);
    const response = await applyLLMProfile(profile.name);
    applyState(response.data);
    closeLLMEditor();
    showMessage(`配置 "${profile.name}" 已应用到运行时。`);
  } catch (error) {
    showMessage(`应用失败: ${error.message}`, "error");
  } finally {
    saving.value = false;
  }
}

async function refreshProfiles() {
  const response = await getLLMProfiles();
  profiles.value = response.data ?? [];
}

async function refresh() {
  saving.value = true;
  try {
    const [settingsResponse] = await Promise.all([getLLMSettings(), refreshProfiles()]);
    applyState(settingsResponse.data);
    showMessage("已从后端加载运行时 LLM 配置。");
  } catch (error) {
    showMessage(`加载运行时配置失败: ${error.message}`, "error");
  } finally {
    saving.value = false;
  }
}

async function saveProfile() {
  if (!form.profile_name.trim()) {
    showMessage("请输入配置名称后再保存。", "error");
    return;
  }

  saving.value = true;
  try {
    await saveLLMProfile({
      name: form.profile_name.trim(),
      provider: form.provider,
      model: form.model,
      base_url: form.base_url || null,
      api_key: form.api_key || null
    });
    await refreshProfiles();
    closeLLMEditor();
    showMessage(`配置 "${form.profile_name.trim()}" 已保存。${form.api_key ? "API 密钥已加密保存。" : "API 密钥未更改。"}`);
  } catch (error) {
    showMessage(`保存配置失败: ${error.message}`, "error");
  } finally {
    saving.value = false;
  }
}

async function removeProfile(name) {
  saving.value = true;
  try {
    await deleteLLMProfile(name);
    await refreshProfiles();
    showMessage(`配置 "${name}" 已删除。`);
    if (form.profile_name === name) {
      form.profile_name = "";
    }
  } catch (error) {
    showMessage(`删除失败: ${error.message}`, "error");
  } finally {
    saving.value = false;
  }
}

async function refreshBBProfiles() {
  const response = await getBBProfiles();
  bbProfiles.value = response.data ?? [];
}

async function useBBProfile(profile) {
  saving.value = true;
  try {
    bbForm.profile_name = profile.name;
    bbForm.student_id = profile.student_id;
    bbForm.base_url = profile.base_url ?? "";
    bbForm.password = "";
    const response = await applyBBProfile(profile.name);
    applyBBState(response.data);
    closeBBEditor();
    showMessage(`配置 "${profile.name}" 已应用到运行时。`);
  } catch (error) {
    showMessage(`应用失败: ${error.message}`, "error");
  } finally {
    saving.value = false;
  }
}

async function saveBBProfile() {
  if (!bbForm.profile_name.trim()) {
    showMessage("请输入配置名称后再保存。", "error");
    return;
  }

  saving.value = true;
  try {
    await saveBBProfileAPI({
      name: bbForm.profile_name.trim(),
      student_id: bbForm.student_id,
      base_url: bbForm.base_url || null,
      password: bbForm.password || null
    });
    await refreshBBProfiles();
    closeBBEditor();
    showMessage(`Blackboard 配置 "${bbForm.profile_name.trim()}" 已保存。${bbForm.password ? "密码已加密保存。" : "密码未更改。"}`);
  } catch (error) {
    showMessage(`保存配置失败: ${error.message}`, "error");
  } finally {
    saving.value = false;
  }
}

async function removeBBProfile(name) {
  saving.value = true;
  try {
    await deleteBBProfile(name);
    await refreshBBProfiles();
    showMessage(`配置 "${name}" 已删除。`);
    if (bbForm.profile_name === name) {
      bbForm.profile_name = "";
    }
  } catch (error) {
    showMessage(`删除失败: ${error.message}`, "error");
  } finally {
    saving.value = false;
  }
}

async function save() {
  saving.value = true;
  try {
    const response = await updateLLMSettings({
      provider: form.provider,
      model: form.model,
      base_url: form.base_url || null,
      api_key: form.api_key || null,
      enable_reasoning: form.enable_reasoning
    });
    applyState(response.data);
    closeLLMEditor();
    showMessage("运行时配置已保存。API 密钥仅保留在服务器端。");
  } catch (error) {
    showMessage(`保存失败: ${error.message}`, "error");
  } finally {
    saving.value = false;
  }
}

async function testConnection() {
  saving.value = true;
  try {
    const response = await testLLMSettings({
      provider: form.provider,
      model: form.model,
      base_url: form.base_url || null,
      api_key: form.api_key || null,
      enable_reasoning: form.enable_reasoning
    });
    const result = response.data;
    showMessage(`连接正常，耗时 ${result.latency_ms}ms。预览: ${result.preview}`);
  } catch (error) {
    showMessage(`连接测试失败: ${error.message}`, "error");
  } finally {
    saving.value = false;
  }
}

async function refreshAll() {
  saving.value = true;
  try {
    const [llmResponse, bbResponse, llmProfilesResponse, bbProfilesResponse, healthResponse] = await Promise.all([
      getLLMSettings(),
      getBlackboardSettings(),
      getLLMProfiles(),
      getBBProfiles(),
      getHealth()
    ]);

    applyState(llmResponse.data);
    applyBBState(bbResponse.data);
    profiles.value = llmProfilesResponse.data ?? [];
    bbProfiles.value = bbProfilesResponse.data ?? [];
    backendStatus.healthy = true;
    backendStatus.message = healthResponse.status || "服务响应正常";
    showMessage("所有配置与后端状态已刷新。");
  } catch (error) {
    backendStatus.healthy = false;
    backendStatus.message = error.message;
    showMessage(`刷新失败: ${error.message}`, "error");
  } finally {
    saving.value = false;
  }
}

watch(activeSection, () => {
  clearMessage();
});

onMounted(async () => {
  await Promise.all([refresh(), refreshBlackboard(), refreshBBProfiles(), checkBackendHealth()]);
});

onBeforeUnmount(() => {
  clearMessage();
});
</script>

<style scoped>
.settings-panel {
  position: relative;
  max-width: 1120px;
  margin: 0 auto;
  padding: 28px;
  border-radius: 24px;
  background:
    radial-gradient(circle at top left, rgba(249, 115, 22, 0.12), transparent 24%),
    radial-gradient(circle at bottom right, rgba(31, 111, 120, 0.12), transparent 28%),
    rgba(255, 255, 255, 0.94);
  box-shadow: 0 24px 60px rgba(28, 36, 48, 0.14);
  backdrop-filter: blur(20px);
  max-height: 84vh;
  overflow: hidden;
}

.settings-header {
  display: flex;
  justify-content: space-between;
  gap: 20px;
  align-items: flex-start;
  margin-bottom: 22px;
}

.header-title h2 {
  margin: 0;
  font-family: var(--font-heading);
  font-size: 28px;
  color: var(--text-primary);
}

.header-copy {
  margin: 10px 0 0;
  max-width: 560px;
  color: var(--text-muted);
  font-size: 14px;
  line-height: 1.6;
}

.header-actions {
  display: flex;
  gap: 12px;
  align-items: center;
  flex-wrap: wrap;
  justify-content: flex-end;
}

.settings-layout {
  display: grid;
  grid-template-columns: 260px minmax(0, 1fr);
  gap: 20px;
  min-height: 0;
}

.settings-nav {
  display: grid;
  align-content: start;
  gap: 10px;
  padding: 16px;
  border-radius: 22px;
  background: rgba(17, 24, 39, 0.04);
  border: 1px solid rgba(148, 163, 184, 0.2);
  transition: width 0.2s ease, padding 0.2s ease;
}

.settings-nav.collapsed {
  width: 84px;
  padding: 16px 10px;
}

.nav-item {
  display: flex;
  align-items: center;
  gap: 12px;
  width: 100%;
  padding: 14px;
  border: 1px solid transparent;
  border-radius: 18px;
  background: transparent;
  text-align: left;
  cursor: pointer;
  transition: all 0.2s ease;
}

.nav-item:hover {
  background: rgba(249, 115, 22, 0.08);
}

.nav-item.active {
  background: linear-gradient(135deg, rgba(249, 115, 22, 0.16), rgba(31, 111, 120, 0.14));
  border-color: rgba(249, 115, 22, 0.18);
}

.nav-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 40px;
  height: 40px;
  border-radius: 14px;
  background: white;
  color: var(--text-primary);
  font-size: 13px;
  font-weight: 700;
  letter-spacing: 0.08em;
  flex-shrink: 0;
}

.nav-copy {
  display: grid;
  gap: 4px;
}

.nav-copy strong {
  font-size: 14px;
  color: var(--text-primary);
}

.nav-copy small {
  font-size: 12px;
  color: var(--text-muted);
}

.settings-content {
  display: grid;
  gap: 16px;
  max-height: calc(84vh - 110px);
  overflow-y: auto;
  padding-right: 6px;
  padding-bottom: 10px;
}

.content-panel {
  padding: 22px;
  border-radius: 22px;
  background: rgba(255, 255, 255, 0.92);
  border: 1px solid rgba(148, 163, 184, 0.18);
  box-shadow: 0 12px 30px rgba(28, 36, 48, 0.06);
}

.hero-panel {
  background: linear-gradient(135deg, rgba(249, 115, 22, 0.1), rgba(255, 255, 255, 0.95) 40%, rgba(31, 111, 120, 0.08));
}

.bb-hero {
  background: linear-gradient(135deg, rgba(31, 111, 120, 0.12), rgba(255, 255, 255, 0.95) 38%, rgba(249, 115, 22, 0.08));
}

.backend-hero {
  background: linear-gradient(135deg, rgba(14, 116, 144, 0.12), rgba(255, 255, 255, 0.94) 45%, rgba(15, 23, 42, 0.06));
}

.developer-panel {
  background: linear-gradient(135deg, rgba(15, 23, 42, 0.08), rgba(255, 255, 255, 0.94) 40%, rgba(249, 115, 22, 0.1));
}

.panel-heading,
.section-top,
.profiles-header {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  align-items: flex-start;
}

.panel-heading h3 {
  margin: 4px 0 0;
  font-family: var(--font-heading);
  font-size: 22px;
  color: var(--text-primary);
}

.eyebrow {
  margin: 0 0 6px;
  text-transform: uppercase;
  letter-spacing: 0.12em;
  font-size: 11px;
  font-weight: 700;
  color: var(--accent-orange);
}

.badge {
  padding: 7px 14px;
  border-radius: 999px;
  background: rgba(239, 68, 68, 0.12);
  color: #dc2626;
  font-size: 12px;
  font-weight: 700;
}

.badge.ready {
  background: rgba(34, 197, 94, 0.12);
  color: #15803d;
}

.hint {
  color: var(--text-muted);
  font-size: 13px;
  margin: 0;
  line-height: 1.6;
}

.compact {
  margin-top: 6px;
}

.status-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
  margin-top: 18px;
}

.backend-grid {
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.status-card {
  display: grid;
  gap: 6px;
  padding: 16px;
  border-radius: 18px;
  background: rgba(255, 255, 255, 0.88);
  border: 1px solid rgba(148, 163, 184, 0.16);
}

.status-card.wide {
  grid-column: 1 / -1;
}

.status-card span {
  font-size: 12px;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  color: var(--text-muted);
}

.status-card strong {
  font-size: 15px;
  color: var(--text-primary);
  line-height: 1.5;
  word-break: break-word;
}

.status-card small {
  font-size: 12px;
  color: var(--text-muted);
  line-height: 1.5;
}

.profile-list {
  display: grid;
  gap: 10px;
  margin-top: 14px;
}

.profile-item,
.dev-card {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  align-items: center;
  padding: 16px;
  border-radius: 18px;
  background: white;
  border: 1px solid var(--border-light);
}

.profile-info strong,
.dev-card strong,
.section-top strong {
  font-size: 15px;
  color: var(--text-primary);
}

.profile-info p,
.dev-card p {
  margin: 4px 0 0;
  font-size: 13px;
  color: var(--text-secondary);
}

.profile-info small {
  display: block;
  margin-top: 2px;
  font-size: 12px;
  color: var(--text-muted);
}

.profile-actions,
.dev-actions {
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  align-items: center;
  gap: 12px;
}

.action-btn {
  background: rgba(31, 41, 55, 0.06);
  color: var(--text-primary);
}

.action-btn:hover {
  background: rgba(31, 41, 55, 0.12);
}

.config-form {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
  margin-top: 18px;
}

.bb-form {
  display: grid;
  gap: 16px;
  margin-top: 18px;
}

.editor-panel {
  border-style: dashed;
  border-color: rgba(218, 106, 30, 0.2);
  background: linear-gradient(180deg, rgba(255, 247, 239, 0.92), rgba(255, 255, 255, 0.94));
}

.panel-actions {
  margin-top: 16px;
}

label {
  display: grid;
  gap: 8px;
}

label span {
  font-size: 12px;
  font-weight: 700;
  color: var(--text-secondary);
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

input,
select {
  box-sizing: border-box;
  width: 100%;
  padding: 14px 16px;
  border-radius: 14px;
  border: 1px solid var(--border-light);
  background: white;
  font-size: 14px;
  transition: all 0.2s ease;
}

input:focus,
select:focus {
  outline: none;
  border-color: var(--accent-orange);
  box-shadow: 0 0 0 4px var(--accent-orange-subtle);
}

.full {
  grid-column: 1 / -1;
}

.actions {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
  margin-top: 8px;
  flex-wrap: wrap;
}

.inline-actions {
  justify-content: flex-start;
  margin-top: 18px;
}

button {
  padding: 10px 16px;
  border: none;
  border-radius: 999px;
  font-weight: 700;
  font-size: 13px;
  cursor: pointer;
  transition: all 0.2s ease;
}

button[type="submit"],
.section-top > button,
.dev-card button {
  background: var(--accent-orange);
  color: white;
}

button[type="submit"]:hover,
.section-top > button:hover,
.dev-card button:hover {
  background: #ea580c;
}

.secondary {
  background: var(--bg-hover);
  color: var(--text-primary);
}

.secondary:hover {
  background: var(--border-subtle);
}

.apply-btn {
  background: var(--accent-orange-subtle);
  color: var(--accent-orange);
}

.apply-btn:hover {
  background: var(--accent-orange);
  color: white;
}

.delete-btn {
  background: rgba(239, 68, 68, 0.1);
  color: #dc2626;
}

.delete-btn:hover {
  background: #dc2626;
  color: white;
}

button:disabled {
  opacity: 0.6;
  cursor: wait;
}

.close-btn,
.collapse-btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  background: rgba(28, 36, 48, 0.08);
  color: var(--text-primary);
}

.close-btn:hover,
.collapse-btn:hover {
  background: rgba(28, 36, 48, 0.12);
}

.result {
  position: absolute;
  right: 28px;
  bottom: 28px;
  z-index: 6;
  max-width: min(520px, calc(100% - 56px));
  margin: 0;
  padding: 14px 18px;
  border-radius: 16px;
  background: rgba(34, 197, 94, 0.1);
  color: #15803d;
  font-size: 13px;
  font-weight: 600;
  border: 1px solid rgba(34, 197, 94, 0.14);
  box-shadow: 0 14px 24px rgba(15, 23, 42, 0.08);
  backdrop-filter: blur(12px);
  line-height: 1.5;
  word-break: break-word;
}

.result.error {
  background: rgba(239, 68, 68, 0.1);
  color: #dc2626;
  border-color: rgba(239, 68, 68, 0.16);
}

.toast-fade-enter-active,
.toast-fade-leave-active {
  transition: opacity 0.22s ease, transform 0.22s ease;
}

.toast-fade-enter-from,
.toast-fade-leave-to {
  opacity: 0;
  transform: translateY(8px);
}

@media (max-width: 980px) {
  .settings-panel {
    padding: 20px;
    max-height: 90vh;
  }

  .settings-layout {
    grid-template-columns: 1fr;
  }

  .settings-nav,
  .settings-nav.collapsed {
    width: auto;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    padding: 12px;
  }

  .nav-copy {
    display: grid !important;
  }

  .result {
    right: 20px;
    bottom: 20px;
    max-width: calc(100% - 40px);
  }

  .status-grid,
  .backend-grid,
  .config-form {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 700px) {
  .settings-header,
  .panel-heading,
  .section-top,
  .profile-item,
  .dev-card {
    flex-direction: column;
    align-items: stretch;
  }

  .header-actions {
    width: 100%;
    justify-content: flex-start;
  }

  .settings-nav,
  .settings-nav.collapsed {
    grid-template-columns: 1fr;
  }
}
</style>

<style scoped>
.toggle-label {
  display: flex;
  align-items: center;
  cursor: pointer;
}
.toggle-row {
  display: flex;
  justify-content: space-between;
  width: 100%;
}
.toggle-input {
  width: auto;
  margin-left: 10px;
}
</style>
