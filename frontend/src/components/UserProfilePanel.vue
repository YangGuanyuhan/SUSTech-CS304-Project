<template>
  <section class="profile-panel">
    <header class="panel-header">
      <div class="panel-title">
        <p class="eyebrow">Account</p>
        <h2>用户管理</h2>
        <span>管理本地资料、头像和长期记忆</span>
      </div>
      <button class="icon-button" type="button" title="关闭" @click="$emit('close')">
        <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <line x1="18" y1="6" x2="6" y2="18"/>
          <line x1="6" y1="6" x2="18" y2="18"/>
        </svg>
      </button>
    </header>

    <section class="profile-hero">
      <div class="avatar-shell">
        <div class="avatar-preview">
          <img v-if="profile?.avatar_url" :src="apiAssetUrl(profile.avatar_url)" alt="用户头像" />
          <svg v-else width="34" height="34" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/>
            <circle cx="12" cy="7" r="4"/>
          </svg>
        </div>
        <label class="avatar-upload" title="上传头像">
          <input type="file" accept="image/png,image/jpeg,image/webp,image/gif" @change="uploadAvatar" />
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2">
            <path d="M23 19a2 2 0 0 1-2 2H3a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h4l2-3h6l2 3h4a2 2 0 0 1 2 2z"/>
            <circle cx="12" cy="13" r="4"/>
          </svg>
        </label>
      </div>

      <div class="profile-main">
        <div class="identity-row">
          <div>
            <strong>{{ profile?.display_name || "用户" }}</strong>
            <span>@{{ profile?.username || "local" }}</span>
          </div>
          <span class="status-pill">在线</span>
        </div>
      </div>

      <form class="profile-form" @submit.prevent="saveName">
        <label>
          <span>昵称</span>
          <input v-model="displayName" maxlength="100" autocomplete="name" />
        </label>
        <button type="submit" :disabled="savingName || !displayName.trim()">
          <svg v-if="!savingName" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.3">
            <polyline points="20 6 9 17 4 12"/>
          </svg>
          <span>{{ savingName ? "保存中" : "保存" }}</span>
        </button>
      </form>
    </section>

    <div class="memory-surface">
      <MemoryManager />
    </div>

    <p v-if="error" class="error-text">{{ error }}</p>

    <button class="logout-button" type="button" @click="$emit('logout')">
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/>
        <polyline points="16 17 21 12 16 7"/>
        <line x1="21" y1="12" x2="9" y2="12"/>
      </svg>
      <span>退出登录</span>
    </button>
  </section>
</template>

<script setup>
import { ref, watch } from "vue";
import { apiAssetUrl, updateUserProfile, uploadUserAvatar } from "../api/client";
import MemoryManager from "./MemoryManager.vue";

const props = defineProps({
  profile: {
    type: Object,
    default: null
  }
});

const emit = defineEmits(["close", "logout", "profile-updated"]);

const displayName = ref(props.profile?.display_name || "");
const savingName = ref(false);
const error = ref("");

watch(
  () => props.profile,
  (profile) => {
    displayName.value = profile?.display_name || "";
  }
);

async function saveName() {
  savingName.value = true;
  error.value = "";
  try {
    const response = await updateUserProfile({ display_name: displayName.value });
    emit("profile-updated", response.data);
  } catch (err) {
    error.value = err.message || "保存昵称失败";
  } finally {
    savingName.value = false;
  }
}

async function uploadAvatar(event) {
  const file = event.target.files?.[0];
  event.target.value = "";
  if (!file) return;
  error.value = "";
  try {
    const response = await uploadUserAvatar(file);
    emit("profile-updated", response.data);
  } catch (err) {
    error.value = err.message || "上传头像失败";
  }
}
</script>

<style scoped>
.profile-panel {
  display: flex;
  max-height: min(86vh, 860px);
  min-height: 0;
  flex-direction: column;
  gap: 16px;
  color: #172033;
}

.panel-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 14px;
}

.panel-title {
  min-width: 0;
}

.panel-header h2 {
  margin: 2px 0 0;
  color: #111827;
  font-size: 25px;
  line-height: 1.12;
}

.panel-title span {
  display: block;
  margin-top: 5px;
  color: #64748b;
  font-size: 13px;
}

.eyebrow {
  margin: 0;
  color: #64748b;
  font-size: 12px;
  font-weight: 700;
  text-transform: uppercase;
}

.icon-button {
  display: inline-flex;
  width: 36px;
  height: 36px;
  align-items: center;
  justify-content: center;
  border: 1px solid rgba(148, 163, 184, 0.3);
  border-radius: 10px;
  background: rgba(255, 255, 255, 0.82);
  color: #334155;
  cursor: pointer;
  transition: transform 0.16s ease, background 0.16s ease, box-shadow 0.16s ease;
}

.icon-button:hover {
  background: #fff;
  box-shadow: 0 8px 18px rgba(15, 23, 42, 0.08);
  transform: translateY(-1px);
}

.profile-hero {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr);
  gap: 18px;
  overflow: visible;
  border: 1px solid rgba(148, 163, 184, 0.24);
  border-radius: 18px;
  background:
    linear-gradient(135deg, rgba(255, 255, 255, 0.92), rgba(241, 245, 249, 0.9)),
    #fff;
  box-shadow: 0 18px 42px rgba(15, 23, 42, 0.08);
  padding: 18px;
}

.avatar-shell {
  position: relative;
  width: 88px;
  height: 88px;
}

.avatar-preview {
  display: flex;
  width: 88px;
  height: 88px;
  align-items: center;
  justify-content: center;
  overflow: hidden;
  border: 3px solid rgba(255, 255, 255, 0.95);
  border-radius: 24px;
  background: linear-gradient(135deg, #e0f2fe, #fef3c7);
  color: #334155;
  box-shadow: 0 14px 28px rgba(15, 23, 42, 0.13);
}

.avatar-preview img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.avatar-upload {
  position: absolute;
  right: -6px;
  bottom: -6px;
  display: inline-flex;
  width: 34px;
  height: 34px;
  align-items: center;
  justify-content: center;
  border: 2px solid #fff;
  border-radius: 12px;
  background: #0f766e;
  color: #fff;
  cursor: pointer;
  box-shadow: 0 10px 18px rgba(15, 118, 110, 0.24);
}

.avatar-upload input {
  display: none;
}

.profile-main {
  display: grid;
  min-width: 0;
  gap: 14px;
}

.identity-row {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}

.identity-row strong,
.identity-row span {
  display: block;
}

.identity-row strong {
  color: #0f172a;
  font-size: 21px;
  line-height: 1.2;
}

.identity-row div > span {
  margin-top: 3px;
  color: #64748b;
  font-size: 13px;
}

.status-pill {
  flex: 0 0 auto;
  border: 1px solid rgba(16, 185, 129, 0.28);
  border-radius: 999px;
  background: rgba(209, 250, 229, 0.75);
  color: #047857;
  font-size: 12px;
  font-weight: 800;
  padding: 5px 10px;
}

.profile-form {
  display: grid;
  grid-column: 1 / -1;
  grid-template-columns: minmax(0, 1fr) auto;
  align-items: end;
  gap: 12px;
  min-width: 0;
  padding-top: 2px;
}

.profile-form label {
  color: #475569;
  font-size: 13px;
  font-weight: 700;
}

.profile-form input {
  width: 100%;
  min-width: 0;
  height: 40px;
  margin-top: 6px;
  box-sizing: border-box;
  border: 1px solid rgba(148, 163, 184, 0.36);
  border-radius: 10px;
  background: rgba(255, 255, 255, 0.92);
  color: #0f172a;
  padding: 0 12px;
  outline: none;
}

.profile-form input:focus {
  border-color: #0f766e;
  box-shadow: 0 0 0 3px rgba(15, 118, 110, 0.12);
}

.profile-form button,
.logout-button {
  display: inline-flex;
  height: 40px;
  align-items: center;
  justify-content: center;
  gap: 7px;
  border: 0;
  border-radius: 10px;
  background: #0f766e;
  color: #fff;
  cursor: pointer;
  font-weight: 700;
  padding: 0 15px;
  white-space: nowrap;
}

.profile-form button {
  min-width: 86px;
}

.profile-form button:disabled {
  cursor: not-allowed;
  opacity: 0.6;
}

.memory-surface {
  min-height: 0;
  overflow: hidden;
  border: 1px solid rgba(148, 163, 184, 0.24);
  border-radius: 18px;
  background: rgba(248, 250, 252, 0.72);
  padding: 16px;
}

.logout-button {
  gap: 8px;
  align-self: flex-end;
  height: 38px;
  background: #172033;
  padding: 0 14px;
}

.error-text {
  margin: 0;
  border-radius: 10px;
  background: #fff1f2;
  color: #b91c1c;
  padding: 12px;
}

@media (max-width: 680px) {
  .profile-hero,
  .profile-form {
    grid-template-columns: 1fr;
  }

  .avatar-shell {
    width: 78px;
    height: 78px;
  }

  .avatar-preview {
    width: 78px;
    height: 78px;
    border-radius: 20px;
  }

  .identity-row {
    align-items: flex-start;
  }

  .logout-button {
    align-self: stretch;
  }
}
</style>
