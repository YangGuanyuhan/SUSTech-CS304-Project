<template>
  <section class="memory-manager">
    <header class="memory-header">
      <div>
        <p class="eyebrow">Memory</p>
        <h2>用户记忆</h2>
      </div>
      <button class="icon-button" type="button" title="刷新记忆" :disabled="loading" @click="loadMemories">
        <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M21 12a9 9 0 0 1-9 9 9.75 9.75 0 0 1-6.74-2.74L3 16"/>
          <path d="M3 21v-5h5"/>
          <path d="M3 12a9 9 0 0 1 9-9 9.75 9.75 0 0 1 6.74 2.74L21 8"/>
          <path d="M16 8h5V3"/>
        </svg>
      </button>
    </header>

    <div class="memory-tabs">
      <button :class="{ active: activeTab === 'long' }" type="button" @click="activeTab = 'long'">长期记忆</button>
      <button :class="{ active: activeTab === 'legacy' }" type="button" @click="activeTab = 'legacy'">基础记忆</button>
    </div>

    <label v-if="activeTab === 'long'" class="filter-row">
      <span>类型</span>
      <select v-model="memoryType" @change="loadLongTermMemories">
        <option value="">全部</option>
        <option value="user_preference">用户偏好</option>
        <option value="factual">事实</option>
        <option value="procedural">流程</option>
        <option value="episodic">经历</option>
        <option value="tool_usage">工具使用</option>
      </select>
    </label>

    <p v-if="error" class="error-text">{{ error }}</p>
    <p v-else-if="loading" class="empty-text">正在加载记忆...</p>

    <div v-else-if="activeTab === 'long'" class="memory-list">
      <article v-for="memory in longTermMemories" :key="memory.id" class="memory-item">
        <div>
          <div class="memory-meta">
            <span>{{ typeLabel(memory.memory_type) }}</span>
            <span>{{ formatDate(memory.created_at) }}</span>
          </div>
          <p>{{ memory.content }}</p>
        </div>
        <button class="danger-icon" type="button" title="删除记忆" @click="removeLongTermMemory(memory.id)">
          <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <polyline points="3 6 5 6 21 6"/>
            <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6"/>
            <path d="M10 11v6"/>
            <path d="M14 11v6"/>
          </svg>
        </button>
      </article>
      <p v-if="!longTermMemories.length" class="empty-text">还没有长期记忆。</p>
    </div>

    <div v-else class="memory-list">
      <article v-for="memory in legacyMemories" :key="memory.id" class="memory-item">
        <div>
          <div class="memory-meta">
            <span>{{ memory.category }}</span>
            <span>{{ formatDate(memory.created_at) }}</span>
          </div>
          <strong>{{ memory.key }}</strong>
          <p>{{ displayValue(memory.value) }}</p>
        </div>
        <button class="danger-icon" type="button" title="删除记忆" @click="removeMemory(memory.id)">
          <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <polyline points="3 6 5 6 21 6"/>
            <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6"/>
            <path d="M10 11v6"/>
            <path d="M14 11v6"/>
          </svg>
        </button>
      </article>
      <p v-if="!legacyMemories.length" class="empty-text">还没有基础记忆。</p>
    </div>
  </section>
</template>

<script setup>
import { onMounted, ref, watch } from "vue";
import {
  deleteLongTermMemory,
  deleteMemory,
  listLongTermMemories,
  listMemories
} from "../api/client";

const activeTab = ref("long");
const memoryType = ref("");
const longTermMemories = ref([]);
const legacyMemories = ref([]);
const loading = ref(false);
const error = ref("");

function typeLabel(type) {
  return {
    user_preference: "用户偏好",
    factual: "事实",
    procedural: "流程",
    episodic: "经历",
    tool_usage: "工具使用"
  }[type] || type;
}

function formatDate(value) {
  if (!value) return "";
  return new Date(value).toLocaleString([], {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit"
  });
}

function displayValue(value) {
  if (typeof value === "string") return value;
  return JSON.stringify(value);
}

async function loadLongTermMemories() {
  loading.value = true;
  error.value = "";
  try {
    const response = await listLongTermMemories(memoryType.value);
    longTermMemories.value = response.data || [];
  } catch (err) {
    error.value = err.message || "加载长期记忆失败";
  } finally {
    loading.value = false;
  }
}

async function loadLegacyMemories() {
  loading.value = true;
  error.value = "";
  try {
    const response = await listMemories();
    legacyMemories.value = response.data || [];
  } catch (err) {
    error.value = err.message || "加载基础记忆失败";
  } finally {
    loading.value = false;
  }
}

function loadMemories() {
  if (activeTab.value === "long") {
    return loadLongTermMemories();
  }
  return loadLegacyMemories();
}

async function removeLongTermMemory(memoryId) {
  await deleteLongTermMemory(memoryId);
  await loadLongTermMemories();
}

async function removeMemory(memoryId) {
  await deleteMemory(memoryId);
  await loadLegacyMemories();
}

watch(activeTab, () => loadMemories());
onMounted(() => loadMemories());
</script>

<style scoped>
.memory-manager {
  display: flex;
  min-height: 0;
  flex-direction: column;
  gap: 14px;
}

.memory-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.memory-header h2 {
  margin: 2px 0 0;
  font-size: 22px;
}

.eyebrow {
  margin: 0;
  color: #64748b;
  font-size: 12px;
  font-weight: 700;
  text-transform: uppercase;
}

.icon-button,
.danger-icon {
  display: inline-flex;
  width: 34px;
  height: 34px;
  align-items: center;
  justify-content: center;
  border: 1px solid #dbe4ef;
  border-radius: 8px;
  background: #fff;
  color: #334155;
  cursor: pointer;
}

.danger-icon {
  flex: 0 0 auto;
  color: #b91c1c;
}

.memory-tabs {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 6px;
  padding: 4px;
  border-radius: 8px;
  background: #edf2f7;
}

.memory-tabs button {
  border: 0;
  border-radius: 6px;
  background: transparent;
  color: #475569;
  cursor: pointer;
  font-weight: 700;
  padding: 9px 10px;
}

.memory-tabs button.active {
  background: #fff;
  color: #0f172a;
  box-shadow: 0 1px 3px rgba(15, 23, 42, 0.12);
}

.filter-row {
  display: flex;
  align-items: center;
  gap: 10px;
  color: #475569;
  font-size: 13px;
}

.filter-row select {
  height: 36px;
  border: 1px solid #dbe4ef;
  border-radius: 8px;
  background: #fff;
  color: #0f172a;
  padding: 0 10px;
}

.memory-list {
  display: flex;
  min-height: 0;
  flex-direction: column;
  gap: 10px;
  overflow: auto;
}

.memory-item {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  background: #fff;
  padding: 12px;
}

.memory-item strong,
.memory-item p {
  margin: 4px 0 0;
  color: #0f172a;
  line-height: 1.5;
}

.memory-meta {
  display: flex;
  gap: 8px;
  color: #64748b;
  font-size: 12px;
}

.empty-text,
.error-text {
  margin: 0;
  border-radius: 8px;
  padding: 12px;
  color: #64748b;
  background: #f8fafc;
}

.error-text {
  color: #b91c1c;
  background: #fff1f2;
}
</style>
