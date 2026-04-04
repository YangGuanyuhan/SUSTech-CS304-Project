<template>
  <section class="settings-card">
    <header>
      <div>
        <p class="eyebrow">Runtime Settings</p>
        <h2>LLM Backend</h2>
      </div>
      <div class="header-actions">
        <span class="badge" :class="{ ready: state.api_key_configured }">
          {{ state.api_key_configured ? "Key loaded" : "Key missing" }}
        </span>
        <button type="button" class="close-btn" @click="$emit('close')">Close</button>
      </div>
    </header>

    <p class="hint">
      API key is sent only to the backend and stored in server memory for this process. It is never
      returned to the browser and disappears after restart.
    </p>

    <section class="profiles">
      <div class="profiles-header">
        <strong>Saved API Profiles</strong>
        <button type="button" :disabled="saving" @click="saveProfile">Save Current Profile</button>
      </div>
      <p class="hint compact">
        Saved profiles persist only non-secret fields: provider, model, and base URL. API key is not
        stored, so you still decide when to inject a secret into the running backend.
      </p>
      <div v-if="profiles.length" class="profile-list">
        <article v-for="profile in profiles" :key="profile.name" class="profile-item">
          <div>
            <strong>{{ profile.name }}</strong>
            <p>{{ profile.provider }} / {{ profile.model }}</p>
            <small>{{ profile.base_url || "OpenAI default base URL" }}</small>
            <small>{{ profile.api_key_configured ? "Encrypted key saved locally" : "No saved key" }}</small>
          </div>
          <div class="profile-actions">
            <button type="button" :disabled="saving" @click="useProfile(profile)">Apply</button>
            <button type="button" :disabled="saving" @click="removeProfile(profile.name)">Delete</button>
          </div>
        </article>
      </div>
      <p v-else class="hint compact">No saved profiles yet.</p>
    </section>

    <section v-if="showDeveloperTools" class="developer-tools">
      <div class="developer-header">
        <div>
          <p class="eyebrow compact-eyebrow">Developer / Debug</p>
          <strong>Internal Inspection Tools</strong>
        </div>
        <button type="button" :disabled="saving" @click="$emit('open-database-overview')">Open Database View</button>
      </div>
      <p class="hint compact">
        This panel is meant for local debugging and coursework demos, not normal end-user workflows.
      </p>
      <p class="hint compact">
        Backend endpoint: <code>/api/database/overview</code>
      </p>
    </section>

    <form class="grid" @submit.prevent="save">
      <label class="full">
        <span>Profile Name</span>
        <input v-model="form.profile_name" placeholder="e.g. openai-main or deepseek-gateway" autocomplete="off" />
      </label>
      <label>
        <span>Provider</span>
        <input v-model="form.provider" autocomplete="off" />
      </label>
      <label>
        <span>Model</span>
        <input v-model="form.model" autocomplete="off" />
      </label>
      <label class="full">
        <span>Base URL</span>
        <input v-model="form.base_url" placeholder="https://api.openai.com/v1" autocomplete="off" />
      </label>
      <label class="full">
        <span>API Key</span>
        <input
          v-model="form.api_key"
          type="password"
          placeholder="Leave blank to keep current key"
          autocomplete="new-password"
        />
      </label>
      <div class="actions full">
        <button type="button" :disabled="saving" @click="refresh">Refresh</button>
        <button type="button" :disabled="saving" @click="testConnection">Test Connection</button>
        <button type="submit" :disabled="saving">{{ saving ? "Saving..." : "Save Runtime Config" }}</button>
      </div>
    </form>

    <p class="result" :class="{ error: messageType === 'error' }">{{ message }}</p>
  </section>
</template>

<script setup>
import { onMounted, reactive, ref } from "vue";
import {
  applyLLMProfile,
  deleteLLMProfile,
  getLLMProfiles,
  getLLMSettings,
  saveLLMProfile,
  testLLMSettings,
  updateLLMSettings
} from "../api/client";

defineEmits(["close", "open-database-overview"]);

const showDeveloperTools = import.meta.env.DEV;

const saving = ref(false);
const message = ref("Load or update the runtime LLM config.");
const messageType = ref("info");
const profiles = ref([]);
const state = reactive({
  provider: "openai",
  model: "gpt-4o-mini",
  base_url: "",
  api_key_configured: false
});
const form = reactive({
  profile_name: "",
  provider: "openai",
  model: "gpt-4o-mini",
  base_url: "",
  api_key: ""
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

function applyProfile(profile) {
  form.profile_name = profile.name;
  form.provider = profile.provider;
  form.model = profile.model;
  form.base_url = profile.base_url ?? "";
  message.value = `Loaded profile "${profile.name}". API key still needs to be set for this runtime if not already present.`;
  messageType.value = "info";
}

async function useProfile(profile) {
  saving.value = true;
  try {
    applyProfile(profile);
    const response = await applyLLMProfile(profile.name);
    applyState(response.data);
    message.value = `Profile "${profile.name}" applied to the runtime configuration.`;
    messageType.value = "info";
  } catch (error) {
    message.value = `Apply failed: ${error.message}`;
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
    message.value = "Runtime config loaded from backend.";
    messageType.value = "info";
  } catch (error) {
    message.value = `Failed to load runtime config: ${error.message}`;
    messageType.value = "error";
  } finally {
    saving.value = false;
  }
}

async function saveProfile() {
  if (!form.profile_name.trim()) {
    message.value = "Please enter a profile name before saving.";
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
    message.value = `Profile "${form.profile_name.trim()}" saved. ${form.api_key ? "API key was encrypted and saved locally." : "API key was not changed."}`;
    messageType.value = "info";
  } catch (error) {
    message.value = `Profile save failed: ${error.message}`;
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
    message.value = `Profile "${name}" deleted.`;
    messageType.value = "info";
    if (form.profile_name === name) {
      form.profile_name = "";
    }
  } catch (error) {
    message.value = `Delete failed: ${error.message}`;
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
    message.value = "Runtime config saved. API key remains server-side only.";
    messageType.value = "info";
  } catch (error) {
    message.value = `Save failed: ${error.message}`;
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
    message.value = `Connection ok in ${result.latency_ms} ms. Preview: ${result.preview}`;
    messageType.value = "info";
  } catch (error) {
    message.value = `Connection test failed: ${error.message}`;
    messageType.value = "error";
  } finally {
    saving.value = false;
  }
}

onMounted(() => {
  refresh();
});
</script>

<style scoped>
.settings-card {
  max-width: 960px;
  margin: 0 auto 24px;
  padding: 24px;
  border-radius: 28px;
  background: rgba(255, 255, 255, 0.72);
  box-shadow: 0 20px 50px rgba(28, 36, 48, 0.08);
  backdrop-filter: blur(12px);
}

header {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  align-items: start;
}

.header-actions {
  display: flex;
  gap: 12px;
  align-items: center;
}

h2 {
  margin: 0;
  font-family: "Space Grotesk", "IBM Plex Sans", sans-serif;
}

.eyebrow {
  margin: 0 0 8px;
  text-transform: uppercase;
  letter-spacing: 0.14em;
  font-size: 0.78rem;
  color: var(--accent);
}

.badge {
  padding: 8px 12px;
  border-radius: 999px;
  background: rgba(201, 61, 74, 0.14);
  color: #9b2833;
  font-weight: 700;
}

.badge.ready {
  background: rgba(31, 111, 120, 0.14);
  color: #1f6f78;
}

.hint {
  color: var(--muted);
  max-width: 70ch;
}

.grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
}

.profiles {
  margin: 16px 0 22px;
  padding: 18px;
  border-radius: 22px;
  background: rgba(28, 36, 48, 0.05);
}

.developer-tools {
  margin: 0 0 22px;
  padding: 18px;
  border-radius: 22px;
  background: rgba(31, 111, 120, 0.08);
  border: 1px dashed rgba(31, 111, 120, 0.28);
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

.profiles-header {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  align-items: center;
}

.profile-list {
  display: grid;
  gap: 12px;
  margin-top: 12px;
}

.profile-item {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  align-items: center;
  padding: 14px 16px;
  border-radius: 18px;
  background: rgba(255, 255, 255, 0.88);
}

.profile-item p,
.profile-item small {
  margin: 4px 0 0;
  display: block;
}

.profile-actions {
  display: flex;
  gap: 10px;
}

.compact {
  margin: 8px 0 0;
}

label {
  display: grid;
  gap: 8px;
}

label span {
  font-weight: 700;
}

input {
  box-sizing: border-box;
  width: 100%;
  padding: 14px 16px;
  border-radius: 18px;
  border: 1px solid rgba(28, 36, 48, 0.14);
  background: rgba(255, 255, 255, 0.9);
  font: inherit;
}

.full {
  grid-column: 1 / -1;
}

.actions {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
}

button {
  border: 0;
  border-radius: 999px;
  padding: 12px 18px;
  background: var(--accent);
  color: white;
  font-weight: 700;
  cursor: pointer;
}

button[type="button"] {
  background: rgba(28, 36, 48, 0.78);
}

.close-btn {
  background: rgba(28, 36, 48, 0.92);
}

.result {
  margin: 16px 0 0;
  color: #1f6f78;
}

.result.error {
  color: #9b2833;
}

@media (max-width: 700px) {
  .grid {
    grid-template-columns: 1fr;
  }
}
</style>
