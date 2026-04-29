<template>
  <div class="workspace-picker">
    <input
      :value="modelValue"
      type="text"
      readonly
      placeholder="Select a project directory"
      title="Selected workspace root"
    />
    <button
      class="workspace-picker-btn"
      type="button"
      :disabled="disabled || pickerOpen"
      title="Select workspace directory"
      @click="openPicker"
    >
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <path d="M3 7h5l2 3h11v9a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/>
        <path d="M3 7V5a2 2 0 0 1 2-2h4l2 4"/>
      </svg>
    </button>
  </div>

  <teleport to="body">
    <div v-if="pickerOpen" class="directory-modal" @click.self="closePicker">
      <section class="directory-dialog" role="dialog" aria-modal="true" aria-label="Select workspace directory">
        <header class="directory-header">
          <div>
            <p>Workspace Root</p>
            <h3>{{ currentPath || "Select Directory" }}</h3>
          </div>
          <button class="directory-icon-btn" type="button" title="Close" @click="closePicker">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M18 6 6 18"/>
              <path d="m6 6 12 12"/>
            </svg>
          </button>
        </header>

        <div v-if="shortcuts.length || roots.length" class="directory-location-groups">
          <div v-if="shortcuts.length" class="directory-location-group">
            <span>Quick Access</span>
            <button
              v-for="shortcut in shortcuts"
              :key="shortcut.path"
              type="button"
              :class="{ active: shortcut.path === currentPath }"
              @click="loadDirectory(shortcut.path)"
            >
              {{ shortcut.name }}
            </button>
          </div>
          <div v-if="roots.length" class="directory-location-group">
            <span>Drives</span>
            <button
              v-for="root in roots"
              :key="root.path"
              type="button"
              :class="{ active: root.path === currentPath }"
              @click="loadDirectory(root.path)"
            >
              {{ root.name }}
            </button>
          </div>
        </div>

        <div class="directory-toolbar">
          <button
            class="directory-up"
            type="button"
            :disabled="!parentPath || loading"
            @click="loadDirectory(parentPath)"
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="m18 15-6-6-6 6"/>
            </svg>
            Up
          </button>
          <span>{{ loading ? "Loading..." : `${entries.length} folders` }}</span>
        </div>

        <div class="directory-list">
          <button
            v-for="entry in entries"
            :key="entry.path"
            class="directory-row"
            type="button"
            @dblclick="selectDirectory(entry.path)"
            @click="loadDirectory(entry.path)"
          >
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M3 7h5l2 3h11v9a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/>
              <path d="M3 7V5a2 2 0 0 1 2-2h4l2 4"/>
            </svg>
            <span>{{ entry.name }}</span>
          </button>
          <p v-if="!loading && entries.length === 0" class="directory-empty">
            No child folders in this directory.
          </p>
        </div>

        <p v-if="errorMessage" class="directory-error">{{ errorMessage }}</p>

        <footer class="directory-actions">
          <button type="button" class="secondary" @click="closePicker">Cancel</button>
          <button type="button" :disabled="!currentPath" @click="selectDirectory(currentPath)">
            Select Folder
          </button>
        </footer>
      </section>
    </div>
  </teleport>
</template>

<script setup>
import { ref } from "vue";
import { listWorkspaceDirectories } from "../api/client";

const props = defineProps({
  modelValue: {
    type: String,
    default: ""
  },
  disabled: {
    type: Boolean,
    default: false
  }
});

const emit = defineEmits(["update:modelValue", "error"]);

const pickerOpen = ref(false);
const loading = ref(false);
const currentPath = ref("");
const parentPath = ref("");
const entries = ref([]);
const roots = ref([]);
const shortcuts = ref([]);
const errorMessage = ref("");

async function loadDirectory(path = "") {
  loading.value = true;
  errorMessage.value = "";
  try {
    const response = await listWorkspaceDirectories(path);
    const data = response.data || {};
    currentPath.value = data.path || "";
    parentPath.value = data.parent || "";
    entries.value = data.entries || [];
    roots.value = data.roots || [];
    shortcuts.value = data.shortcuts || [];
  } catch (error) {
    errorMessage.value = error.message;
    emit("error", error);
    if (path) {
      await loadDirectory("");
    }
  } finally {
    loading.value = false;
  }
}

function openPicker() {
  pickerOpen.value = true;
  loadDirectory(props.modelValue);
}

function closePicker() {
  pickerOpen.value = false;
  errorMessage.value = "";
}

function selectDirectory(path) {
  if (!path) return;
  emit("update:modelValue", path);
  closePicker();
}
</script>

<style scoped>
.workspace-picker {
  display: flex;
  align-items: center;
  gap: 8px;
  width: 100%;
}

.workspace-picker input {
  width: 280px;
  min-width: 0;
  flex: 1;
  padding: 12px 14px;
  border: 1px solid rgba(53, 62, 72, 0.08);
  border-radius: 16px;
  background: rgba(255, 255, 255, 0.88);
  font: inherit;
  font-size: 13px;
  cursor: default;
  transition: all 0.2s ease;
}

.workspace-picker input:focus {
  outline: none;
  border-color: var(--accent-orange, var(--accent, #ea580c));
  box-shadow: 0 0 0 3px rgba(234, 88, 12, 0.12);
}

.workspace-picker-btn {
  width: 42px;
  height: 42px;
  display: inline-grid;
  place-items: center;
  flex: 0 0 auto;
  border: 1px solid rgba(53, 62, 72, 0.08);
  border-radius: 16px;
  background: white;
  color: var(--accent-orange, var(--accent, #ea580c));
  cursor: pointer;
  transition: all 0.2s ease;
}

.workspace-picker-btn:hover:not(:disabled) {
  border-color: rgba(234, 88, 12, 0.3);
  box-shadow: 0 6px 18px rgba(234, 88, 12, 0.12);
}

.workspace-picker-btn:disabled {
  opacity: 0.55;
  cursor: wait;
}

.directory-modal {
  position: fixed;
  inset: 0;
  z-index: 1000;
  display: grid;
  place-items: center;
  padding: 24px;
  background: rgba(16, 24, 40, 0.42);
}

.directory-dialog {
  width: min(720px, 100%);
  max-height: min(760px, calc(100vh - 48px));
  display: grid;
  grid-template-rows: auto auto auto minmax(220px, 1fr) auto auto;
  overflow: hidden;
  border-radius: 18px;
  background: #fff;
  box-shadow: 0 24px 80px rgba(16, 24, 40, 0.28);
}

.directory-header,
.directory-toolbar,
.directory-actions {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 16px 18px;
}

.directory-header {
  border-bottom: 1px solid rgba(53, 62, 72, 0.08);
}

.directory-header p {
  margin: 0 0 4px;
  font-size: 11px;
  text-transform: uppercase;
  color: #667085;
}

.directory-header h3 {
  margin: 0;
  max-width: 560px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 16px;
  color: #1f2937;
}

.directory-icon-btn,
.directory-up {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  border: 1px solid rgba(53, 62, 72, 0.1);
  border-radius: 12px;
  background: #fff;
  color: #344054;
  cursor: pointer;
}

.directory-icon-btn {
  width: 38px;
  height: 38px;
  justify-content: center;
}

.directory-location-groups {
  display: grid;
  gap: 10px;
  padding: 12px 18px;
  border-bottom: 1px solid rgba(53, 62, 72, 0.08);
}

.directory-location-group {
  display: flex;
  align-items: center;
  gap: 8px;
  overflow-x: auto;
}

.directory-location-group span {
  flex: 0 0 86px;
  font-size: 11px;
  font-weight: 700;
  text-transform: uppercase;
  color: #667085;
}

.directory-location-group button {
  flex: 0 0 auto;
  border: 1px solid rgba(53, 62, 72, 0.1);
  border-radius: 999px;
  padding: 8px 12px;
  background: #f9fafb;
  color: #344054;
  cursor: pointer;
}

.directory-location-group button.active {
  border-color: rgba(234, 88, 12, 0.35);
  background: rgba(234, 88, 12, 0.08);
  color: #c2410c;
}

.directory-toolbar {
  padding-top: 12px;
  padding-bottom: 12px;
  color: #667085;
  font-size: 13px;
}

.directory-up {
  padding: 9px 12px;
}

.directory-up:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.directory-list {
  overflow: auto;
  padding: 8px 12px 12px;
}

.directory-row {
  width: 100%;
  display: flex;
  align-items: center;
  gap: 10px;
  min-height: 42px;
  border: 0;
  border-radius: 10px;
  padding: 9px 10px;
  background: transparent;
  color: #1f2937;
  text-align: left;
  cursor: pointer;
}

.directory-row:hover {
  background: #f2f4f7;
}

.directory-row span {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.directory-empty,
.directory-error {
  margin: 12px 18px;
  color: #667085;
  font-size: 13px;
}

.directory-error {
  color: #b42318;
}

.directory-actions {
  justify-content: flex-end;
  border-top: 1px solid rgba(53, 62, 72, 0.08);
}

.directory-actions button {
  border: 0;
  border-radius: 999px;
  padding: 10px 16px;
  background: var(--accent-orange, var(--accent, #ea580c));
  color: white;
  font-weight: 700;
  cursor: pointer;
}

.directory-actions button.secondary {
  background: #f2f4f7;
  color: #344054;
}

.directory-actions button:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}
</style>
