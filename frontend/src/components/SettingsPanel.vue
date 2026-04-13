<template>
  <section class="settings-panel">
    <header class="settings-header">
      <div class="header-title">
        <p class="eyebrow">运行设置</p>
        <h2>LLM 后端配置</h2>
      </div>
      <div class="header-actions">
        <span class="badge" :class="{ ready: state.api_key_configured }">
          {{ state.api_key_configured ? '已加载密钥' : '缺少密钥' }}
        </span>
        <button type="button" class="close-btn" @click="$emit('close')">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <line x1="18" y1="6" x2="6" y2="18"/>
            <line x1="6" y1="6" x2="18" y2="18"/>
          </svg>
          关闭
        </button>
      </div>
    </header>

    <p class="hint">
      API 密钥仅发送到后端并存储在服务器内存中。不会返回给浏览器，重启后消失。
    </p>

    <!-- Saved Profiles -->
    <section class="profiles">
      <div class="profiles-header">
        <strong>已保存的配置</strong>
        <button type="button" :disabled="saving" @click="saveProfile">保存当前配置</button>
      </div>
      <p class="hint compact">
        保存的配置仅持久化非敏感字段：提供商、模型和 Base URL。API 密钥不会存储。
      </p>
      <div v-if="profiles.length" class="profile-list">
        <article v-for="profile in profiles" :key="profile.name" class="profile-item">
          <div class="profile-info">
            <strong>{{ profile.name }}</strong>
            <p>{{ profile.provider }} / {{ profile.model }}</p>
            <small>{{ profile.base_url || '使用默认 Base URL' }}</small>
          </div>
          <div class="profile-actions">
            <button type="button" class="apply-btn" :disabled="saving" @click="useProfile(profile)">应用</button>
            <button type="button" class="delete-btn" :disabled="saving" @click="removeProfile(profile.name)">删除</button>
          </div>
        </article>
      </div>
      <p v-else class="hint compact">暂无保存的配置。</p>
    </section>

    <!-- Developer Tools -->
    <section v-if="showDeveloperTools" class="developer-tools">
      <div class="developer-header">
        <div>
          <p class="eyebrow compact-eyebrow">开发者工具</p>
          <strong>内部调试面板</strong>
        </div>
        <button type="button" :disabled="saving" @click="$emit('open-database-overview')">打开数据库视图</button>
      </div>
      <p class="hint compact">
        此面板用于本地调试和课程演示，不适用于常规最终用户工作流程。
      </p>
    </section>

    <!-- Form -->
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
      <div class="actions full">
        <button type="button" class="secondary" :disabled="saving" @click="refresh">刷新</button>
        <button type="button" class="secondary" :disabled="saving" @click="testConnection">测试连接</button>
        <button type="submit" :disabled="saving">{{ saving ? '保存中...' : '保存配置' }}</button>
      </div>
    </form>

    <!-- Blackboard Profiles -->
    <section class="profiles">
      <div class="profiles-header">
        <strong>已保存的 Blackboard 配置</strong>
        <button type="button" :disabled="saving" @click="saveBBProfile">保存当前配置</button>
      </div>
      <p class="hint compact">
        保存的配置仅持久化非敏感字段：学号和 Base URL。密码加密存储。
      </p>
      <div v-if="bbProfiles.length" class="profile-list">
        <article v-for="profile in bbProfiles" :key="profile.name" class="profile-item">
          <div class="profile-info">
            <strong>{{ profile.name }}</strong>
            <p>{{ profile.student_id }}</p>
            <small>{{ profile.base_url || '使用默认 Base URL' }}</small>
          </div>
          <div class="profile-actions">
            <button type="button" class="apply-btn" :disabled="saving" @click="useBBProfile(profile)">应用</button>
            <button type="button" class="delete-btn" :disabled="saving" @click="removeBBProfile(profile.name)">删除</button>
          </div>
        </article>
      </div>
      <p v-else class="hint compact">暂无保存的配置。</p>
    </section>

    <!-- Blackboard Settings -->
    <section class="blackboard-section">
      <div class="section-header">
        <div class="section-title-area">
          <p class="eyebrow">Blackboard 配置</p>
          <h3>南方科技大学 Blackboard 登录</h3>
        </div>
        <div class="header-badge">
          <span class="badge" :class="{ ready: bbState.password_configured }">
            {{ bbState.password_configured ? '已配置' : '未配置' }}
          </span>
        </div>
      </div>
      <p class="hint">
        输入你的校园网账号和密码，用于访问 Blackboard 课程系统。密码仅保存在服务器内存中，重启后需要重新输入。
      </p>

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
          <button type="button" class="secondary" :disabled="saving" @click="refreshBlackboard">刷新</button>
          <button type="button" class="secondary" :disabled="saving" @click="testBlackboard">测试连接</button>
          <button type="submit" :disabled="saving">{{ saving ? '保存中...' : '保存配置' }}</button>
        </div>
      </form>
    </section>

    <p class="result" :class="{ error: messageType === 'error' }">{{ message }}</p>
  </section>
</template>

<script setup>
import { onMounted, reactive, ref } from "vue";
import {
  applyBBProfile,
  applyLLMProfile,
  deleteBBProfile,
  deleteLLMProfile,
  getBBProfiles,
  getBlackboardSettings,
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

const saving = ref(false);
const message = ref("加载或更新运行时 LLM 配置。");
const messageType = ref("info");
const profiles = ref([]);
const bbProfiles = ref([]);

// LLM State
const state = reactive({
  provider: "openai",
  model: "gpt-4o-mini",
  base_url: "",
  api_key_configured: false
});

// Blackboard State
const bbState = reactive({
  student_id: "",
  base_url: "",
  password_configured: false
});

// LLM Form
const form = reactive({
  profile_name: "",
  provider: "openai",
  model: "gpt-4o-mini",
  base_url: "",
  api_key: ""
});

// Blackboard Form
const bbForm = reactive({
  profile_name: "",
  student_id: "",
  password: "",
  base_url: "",
  replace_password: false
});

function applyState(payload) {
  state.provider = payload.provider;
  state.model = payload.model;
  state.base_url = payload.base_url ?? "";
  state.api_key_configured = Boolean(payload.api_key_configured);
  form.provider = payload.provider;
  form.model = payload.model;
  form.base_url = payload.base_url ?? "";
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

async function refreshBlackboard() {
  saving.value = true;
  try {
    const response = await getBlackboardSettings();
    applyBBState(response.data);
    message.value = "Blackboard 配置已加载。";
    messageType.value = "info";
  } catch (error) {
    message.value = `加载 Blackboard 配置失败: ${error.message}`;
    messageType.value = "error";
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
    message.value = "Blackboard 配置已保存。密码仅存储在服务器内存中。";
    messageType.value = "info";
  } catch (error) {
    message.value = `保存失败: ${error.message}`;
    messageType.value = "error";
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
      message.value = "Blackboard 连接测试成功！";
      messageType.value = "info";
    } else {
      message.value = `连接测试失败: ${response.data?.error || "未知错误"}`;
      messageType.value = "error";
    }
  } catch (error) {
    message.value = `测试失败: ${error.message}`;
    messageType.value = "error";
  } finally {
    saving.value = false;
  }
}

function applyProfile(profile) {
  form.profile_name = profile.name;
  form.provider = profile.provider;
  form.model = profile.model;
  form.base_url = profile.base_url ?? "";
  message.value = `已加载配置 "${profile.name}"。如未设置密钥，请为此运行时设置 API 密钥。`;
  messageType.value = "info";
}

async function useProfile(profile) {
  saving.value = true;
  try {
    applyProfile(profile);
    const response = await applyLLMProfile(profile.name);
    applyState(response.data);
    message.value = `配置 "${profile.name}" 已应用到运行时。`;
    messageType.value = "info";
  } catch (error) {
    message.value = `应用失败: ${error.message}`;
    messageType.value = "error";
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
    const response = settingsResponse;
    applyState(response.data);
    message.value = "已从后端加载运行时配置。";
    messageType.value = "info";
  } catch (error) {
    message.value = `加载运行时配置失败: ${error.message}`;
    messageType.value = "error";
  } finally {
    saving.value = false;
  }
}

async function saveProfile() {
  if (!form.profile_name.trim()) {
    message.value = "请输入配置名称后再保存。";
    messageType.value = "error";
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
    message.value = `配置 "${form.profile_name.trim()}" 已保存。${form.api_key ? 'API 密钥已加密保存。' : 'API 密钥未更改。'}`;
    messageType.value = "info";
  } catch (error) {
    message.value = `保存配置失败: ${error.message}`;
    messageType.value = "error";
  } finally {
    saving.value = false;
  }
}

async function removeProfile(name) {
  saving.value = true;
  try {
    await deleteLLMProfile(name);
    await refreshProfiles();
    message.value = `配置 "${name}" 已删除。`;
    messageType.value = "info";
    if (form.profile_name === name) {
      form.profile_name = "";
    }
  } catch (error) {
    message.value = `删除失败: ${error.message}`;
    messageType.value = "error";
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
    message.value = `配置 "${profile.name}" 已应用到运行时。`;
    messageType.value = "info";
  } catch (error) {
    message.value = `应用失败: ${error.message}`;
    messageType.value = "error";
  } finally {
    saving.value = false;
  }
}

async function saveBBProfile() {
  if (!bbForm.profile_name.trim()) {
    message.value = "请输入配置名称后再保存。";
    messageType.value = "error";
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
    message.value = `Blackboard 配置 "${bbForm.profile_name.trim()}" 已保存。${bbForm.password ? '密码已加密保存。' : '密码未更改。'}`;
    messageType.value = "info";
  } catch (error) {
    message.value = `保存配置失败: ${error.message}`;
    messageType.value = "error";
  } finally {
    saving.value = false;
  }
}

async function removeBBProfile(name) {
  saving.value = true;
  try {
    await deleteBBProfile(name);
    await refreshBBProfiles();
    message.value = `配置 "${name}" 已删除。`;
    messageType.value = "info";
    if (bbForm.profile_name === name) {
      bbForm.profile_name = "";
    }
  } catch (error) {
    message.value = `删除失败: ${error.message}`;
    messageType.value = "error";
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
      api_key: form.api_key || null
    });
    applyState(response.data);
    message.value = "运行时配置已保存。API 密钥仅保留在服务器端。";
    messageType.value = "info";
  } catch (error) {
    message.value = `保存失败: ${error.message}`;
    messageType.value = "error";
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
      api_key: form.api_key || null
    });
    const result = response.data;
    message.value = `连接正常，耗时 ${result.latency_ms}ms。预览: ${result.preview}`;
    messageType.value = "info";
  } catch (error) {
    message.value = `连接测试失败: ${error.message}`;
    messageType.value = "error";
  } finally {
    saving.value = false;
  }
}

onMounted(() => {
  refresh();
  refreshBlackboard();
  refreshBBProfiles();
});
</script>

<style scoped>
.settings-panel {
  max-width: 800px;
  margin: 0 auto;
  padding: 28px;
  border-radius: 16px;
  background: rgba(255, 255, 255, 0.92);
  box-shadow: 0 20px 50px rgba(28, 36, 48, 0.12);
  backdrop-filter: blur(20px);
  max-height: 80vh;
  overflow-y: auto;
}

.settings-header {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  align-items: flex-start;
  margin-bottom: 16px;
}

.header-title h2 {
  margin: 0;
  font-family: var(--font-heading);
  font-size: 24px;
  color: var(--text-primary);
}

.header-actions {
  display: flex;
  gap: 12px;
  align-items: center;
}

.eyebrow {
  margin: 0 0 6px;
  text-transform: uppercase;
  letter-spacing: 0.12em;
  font-size: 11px;
  font-weight: 600;
  color: var(--accent-orange);
}

.badge {
  padding: 6px 14px;
  border-radius: 999px;
  background: rgba(239, 68, 68, 0.12);
  color: #dc2626;
  font-size: 12px;
  font-weight: 600;
}

.badge.ready {
  background: rgba(34, 197, 94, 0.12);
  color: #16a34a;
}

.hint {
  color: var(--text-muted);
  font-size: 13px;
  margin: 0 0 20px;
}

/* Profiles Section */
.profiles {
  margin: 0 0 24px;
  padding: 20px;
  border-radius: 20px;
  background: var(--bg-main);
}

.profiles-header {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  align-items: center;
  margin-bottom: 8px;
}

.profiles-header strong {
  font-size: 14px;
  color: var(--text-primary);
}

.profile-list {
  display: grid;
  gap: 10px;
  margin-top: 12px;
}

.profile-item {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  align-items: center;
  padding: 14px 16px;
  border-radius: 16px;
  background: white;
  border: 1px solid var(--border-light);
}

.profile-info strong {
  font-size: 14px;
  color: var(--text-primary);
}

.profile-info p {
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

.profile-actions {
  display: flex;
  gap: 8px;
}

.compact {
  margin: 8px 0 0;
  font-size: 12px;
}

/* Developer Tools */
.developer-tools {
  margin: 0 0 24px;
  padding: 18px;
  border-radius: 20px;
  background: rgba(31, 111, 120, 0.06);
  border: 1px dashed rgba(31, 111, 120, 0.24);
}

.developer-header {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  align-items: center;
}

.compact-eyebrow {
  margin-bottom: 4px;
}

/* Form */
.config-form {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
}

label {
  display: grid;
  gap: 8px;
}

label span {
  font-size: 12px;
  font-weight: 600;
  color: var(--text-secondary);
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

input, select {
  box-sizing: border-box;
  width: 100%;
  padding: 14px 16px;
  border-radius: 14px;
  border: 1px solid var(--border-light);
  background: white;
  font-size: 14px;
  transition: all 0.2s ease;
}

input:focus, select:focus {
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
}

.actions button {
  padding: 12px 20px;
  border: none;
  border-radius: 999px;
  font-weight: 600;
  font-size: 13px;
  cursor: pointer;
  transition: all 0.2s ease;
}

.actions button[type="submit"] {
  background: var(--accent-orange);
  color: white;
}

.actions button[type="submit"]:hover {
  background: #EA580C;
}

.actions button.secondary {
  background: var(--bg-hover);
  color: var(--text-primary);
}

.actions button.secondary:hover {
  background: var(--border-subtle);
}

.actions button:disabled {
  opacity: 0.6;
  cursor: wait;
}

.close-btn {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 10px 16px;
  border: none;
  border-radius: 999px;
  background: rgba(28, 36, 48, 0.08);
  color: var(--text-primary);
  font-weight: 500;
  font-size: 13px;
  cursor: pointer;
  transition: all 0.2s ease;
}

.close-btn:hover {
  background: rgba(28, 36, 48, 0.12);
}

.profiles button[type="button"] {
  padding: 8px 16px;
  border: none;
  border-radius: 999px;
  background: var(--accent-orange);
  color: white;
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s ease;
}

.profiles button[type="button"]:hover {
  background: #EA580C;
}

.profile-item button {
  padding: 8px 14px;
  border: none;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s ease;
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

/* Blackboard Section */
.blackboard-section {
  margin: 24px 0 0;
  padding: 24px;
  border-radius: 20px;
  background: linear-gradient(135deg, rgba(31, 111, 120, 0.06), rgba(249, 115, 22, 0.06));
  border: 1px solid var(--border-light);
}

.section-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 12px;
}

.section-title-area h3 {
  margin: 4px 0 0;
  font-family: var(--font-heading);
  font-size: 18px;
  color: var(--text-primary);
}

.header-badge {
  display: flex;
  align-items: center;
}

.blackboard-section .hint {
  margin: 0 0 20px;
  font-size: 13px;
  color: var(--text-muted);
}

.bb-form {
  display: grid;
  grid-template-columns: 1fr;
  gap: 16px;
}

.blackboard-section .badge {
  padding: 6px 14px;
  border-radius: 999px;
  background: rgba(239, 68, 68, 0.12);
  color: #dc2626;
  font-size: 12px;
  font-weight: 600;
}

.blackboard-section .badge.ready {
  background: rgba(34, 197, 94, 0.12);
  color: #16a34a;
}

.result {
  margin: 20px 0 0;
  padding: 12px 16px;
  border-radius: 12px;
  background: rgba(34, 197, 94, 0.1);
  color: #16a34a;
  font-size: 13px;
  font-weight: 500;
}

.result.error {
  background: rgba(239, 68, 68, 0.1);
  color: #dc2626;
}

@media (max-width: 700px) {
  .config-form {
    grid-template-columns: 1fr;
  }

  .settings-header {
    flex-direction: column;
  }

  .header-actions {
    width: 100%;
    justify-content: flex-end;
  }
}
</style>