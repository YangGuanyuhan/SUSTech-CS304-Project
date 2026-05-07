<template>
  <section class="file-panel">
    <!-- Header -->
    <header class="file-header">
      <div class="file-title-area">
        <p class="eyebrow">文件管理</p>
        <h3>黑板文件浏览器</h3>
        <p class="file-subtitle">展开课程即可加载文件，双击文件夹或文件即可下载</p>
      </div>
      <div class="header-controls">
        <button class="refresh-btn" :disabled="loading" @click="refreshCourses">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M23 4v6h-6M1 20v-6h6"/>
            <path d="M3.51 9a9 9 0 0114.85-3.36M20.49 15a9 9 0 01-14.85 3.36"/>
          </svg>
          {{ loading ? '加载中...' : '刷新' }}
        </button>
      </div>
    </header>

    <!-- Status Bar -->
    <div v-if="statusMessage" class="status-bar" :class="statusType">
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <circle cx="12" cy="12" r="10"/>
        <line x1="12" y1="8" x2="12" y2="12"/>
        <line x1="12" y1="16" x2="12.01" y2="16"/>
      </svg>
      <span>{{ statusMessage }}</span>
      <button v-if="statusType === 'error'" class="dismiss-btn" @click="clearStatus">×</button>
    </div>

    <!-- Knowledge Base -->
    <section class="knowledge-base">
      <div class="kb-controls">
        <div class="kb-field">
          <label>Knowledge folder</label>
          <input
            v-model="ragFolderPath"
            type="text"
            placeholder="Folder path inside the chat workspace"
          />
        </div>
        <label class="kb-check">
          <input v-model="ragRecursive" type="checkbox" />
          <span>Recursive</span>
        </label>
        <button class="refresh-btn" :disabled="ragIndexing || !ragFolderPath.trim()" @click="indexRagFolder">
          {{ ragIndexing ? 'Indexing...' : 'Index' }}
        </button>
        <button class="refresh-btn secondary" :disabled="ragLoading" @click="loadRagSources">
          Refresh
        </button>
      </div>
      <div v-if="ragStatus && !ragStatus.ready" class="kb-warning">
        RAG is not ready: {{ (ragStatus.issues || []).join(' ') }}
      </div>
      <div v-else-if="ragStatus" class="kb-ready">
        RAG ready · {{ ragStatus.provider }} {{ ragStatus.raganything_version || '' }}
      </div>

      <div v-if="ragSources.length" class="kb-source-list">
        <article v-for="source in ragSources" :key="source.id" class="kb-source">
          <div>
            <strong>{{ source.relative_path }}</strong>
            <span>{{ source.extension }} · {{ source.status }}</span>
            <small v-if="source.error">{{ source.error }}</small>
          </div>
          <button class="dismiss-btn" title="Remove from knowledge base" @click="deleteRagSource(source.id)">
            x
          </button>
        </article>
      </div>
      <p v-else class="kb-empty">No indexed knowledge sources yet.</p>
    </section>

    <!-- File Tree -->
    <div class="file-container">
      <div v-if="courses.length === 0 && !loading" class="empty-state">
        <p>未找到课程。请先在设置中配置黑板账户。</p>
      </div>

      <div v-else class="file-tree-wrapper">
        <div class="file-tree">
          <div
            v-for="course in courses"
            :key="course.id"
            class="tree-item"
          >
            <div class="tree-node" @click="toggleNode(course.id)">
              <span class="expand-icon" :class="{ expanded: expandedNodes.has(course.id) }">
                ▶
              </span>
              <span class="node-icon">🎓</span>
              <span class="node-title">{{ course.title }}</span>
              <span v-if="loadingNodes.has(course.id)" class="loading-spinner">⋯</span>
            </div>

            <!-- Children -->
            <div v-if="expandedNodes.has(course.id)" class="tree-children">
              <TreeNode
                v-for="child in course.children"
                :key="child.id"
                :node="child"
                :depth="1"
                :expanded-nodes="expandedNodes"
                :loading-nodes="loadingNodes"
                @toggle="toggleNode"
                @download="downloadNode"
                @download-file="downloadFile"
              />
            </div>

            <!-- Attachments -->
            <div v-if="expandedNodes.has(course.id) && course.attachments && course.attachments.length > 0" class="tree-children">
              <div
                v-for="file in course.attachments"
                :key="file.id"
                class="tree-item attachment"
              >
                <div class="tree-node file-node" @dblclick="downloadFile(file)">
                  <span class="node-icon">📎</span>
                  <span class="node-title">{{ file.file_name }}</span>
                  <span class="download-hint">(双击下载)</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Download Statistics -->
    <div v-if="downloadStats" class="download-stats">
      <div class="stat-item">
        <span class="stat-label">已下载</span>
        <span class="stat-value">{{ downloadStats.files_downloaded }}</span>
      </div>
      <div class="stat-item">
        <span class="stat-label">已跳过</span>
        <span class="stat-value">{{ downloadStats.files_skipped }}</span>
      </div>
      <div class="stat-item">
        <span class="stat-label">错误</span>
        <span class="stat-value">{{ downloadStats.errors }}</span>
      </div>
    </div>
  </section>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import TreeNode from './FileTreeNode.vue'
import { apiClient } from '../api/client'

const courses = ref([])
const expandedNodes = ref(new Set())
const loadingNodes = ref(new Set())
const loading = ref(false)
const statusMessage = ref('')
const statusType = ref('info')
const downloadStats = ref(null)
const ragFolderPath = ref('')
const ragRecursive = ref(true)
const ragIndexing = ref(false)
const ragLoading = ref(false)
const ragSources = ref([])
const ragStatus = ref(null)

const clearStatus = () => {
  statusMessage.value = ''
}

const setExpandedState = (nodeId, expanded) => {
  const next = new Set(expandedNodes.value)
  if (expanded) {
    next.add(nodeId)
  } else {
    next.delete(nodeId)
  }
  expandedNodes.value = next
}

const setLoadingState = (nodeId, loadingState) => {
  const next = new Set(loadingNodes.value)
  if (loadingState) {
    next.add(nodeId)
  } else {
    next.delete(nodeId)
  }
  loadingNodes.value = next
}

const setStatus = (message, type = 'info') => {
  statusMessage.value = message
  statusType.value = type
}

const refreshCourses = async () => {
  loading.value = true
  courses.value = []
  expandedNodes.value.clear()
  downloadStats.value = null

  try {
    console.log('[FilePanel] Starting to fetch courses...')
    const response = await apiClient.get('/blackboard/files/courses')
    console.log('[FilePanel] Raw response:', response)
    console.log('[FilePanel] Response data:', response.data)
    console.log('[FilePanel] Response data.data:', response.data?.data)
    console.log('[FilePanel] Response data.data.courses:', response.data?.data?.courses)
    
    if (response.data?.data?.courses) {
      console.log('[FilePanel] Found courses:', response.data.data.courses.length)
      courses.value = response.data.data.courses
      setStatus(`已加载 ${courses.value.length} 门课程`, 'success')
    } else {
      console.error('[FilePanel] No courses in response:', response.data)
      setStatus('未找到课程数据', 'error')
    }
  } catch (error) {
    console.error('[FilePanel] Error fetching courses:', error)
    setStatus(`加载失败: ${error.message}`, 'error')
    console.error('Failed to fetch courses:', error)
  } finally {
    loading.value = false
  }
}

const loadRagSources = async () => {
  ragLoading.value = true
  try {
    await loadRagStatus()
    const response = await apiClient.get('/rag/sources')
    ragSources.value = response.data?.data || []
  } catch (error) {
    setStatus(`Knowledge base load failed: ${error.message}`, 'error')
  } finally {
    ragLoading.value = false
  }
}

const loadRagStatus = async () => {
  const response = await apiClient.get('/rag/status')
  ragStatus.value = response.data?.data || null
}

const indexRagFolder = async () => {
  const folder = ragFolderPath.value.trim()
  if (!folder) return
  await loadRagStatus()
  if (ragStatus.value && !ragStatus.value.ready) {
    setStatus(`RAG is not ready: ${(ragStatus.value.issues || []).join(' ')}`, 'error')
    return
  }
  ragIndexing.value = true
  try {
    setStatus('Indexing knowledge folder...', 'info')
    const response = await apiClient.post('/rag/index-folder', {
      path: '.',
      workspace_root: folder,
      recursive: ragRecursive.value
    })
    const summary = response.data?.data
    ragSources.value = summary?.sources || ragSources.value
    setStatus(
      `Indexed ${summary?.indexed || 0}, skipped ${summary?.skipped || 0}, failed ${summary?.failed || 0}`,
      summary?.failed ? 'error' : 'success'
    )
    await loadRagSources()
  } catch (error) {
    setStatus(`Knowledge indexing failed: ${error.message}`, 'error')
  } finally {
    ragIndexing.value = false
  }
}

const deleteRagSource = async (sourceId) => {
  try {
    await apiClient.delete(`/rag/sources/${encodeURIComponent(sourceId)}`)
    ragSources.value = ragSources.value.filter((source) => source.id !== sourceId)
    setStatus('Knowledge source removed', 'success')
  } catch (error) {
    setStatus(`Remove failed: ${error.message}`, 'error')
  }
}

const toggleNode = async (nodeId) => {
  if (expandedNodes.value.has(nodeId)) {
    setExpandedState(nodeId, false)
    return
  }

  setExpandedState(nodeId, true)

  // Find the node and load its children
  const node = findNodeById(nodeId)
  const shouldLoad =
    !!node &&
    (
      !node.is_loaded ||
      (node.has_children && (!node.children || node.children.length === 0)) ||
      (node.type === 'x-bb-document' && (!node.attachments || node.attachments.length === 0)) ||
      (node.type === 'x-bb-assignment' && (!node.attachments || node.attachments.length === 0)) ||
      (node.type === 'x-bb-lesson' && (!node.attachments || node.attachments.length === 0))
    )

  if (shouldLoad) {
    setLoadingState(nodeId, true)
    try {
      const courseId = node.course_id || nodeId
      const response = await apiClient.get(`/blackboard/files/tree/${courseId}`, {
        params: { node_id: nodeId !== courseId ? nodeId : null }
      })
      if (response.data?.data) {
        const loadedNode = response.data.data
        console.log('[FilePanel][toggleNode] loaded:', {
          nodeId,
          title: loadedNode.title,
          type: loadedNode.type,
          is_loaded: loadedNode.is_loaded,
          children: (loadedNode.children || []).length,
          attachments: (loadedNode.attachments || []).length,
        })
        // Force array replacement to ensure Vue updates nested tree rendering.
        node.id = loadedNode.id
        node.title = loadedNode.title
        node.type = loadedNode.type
        node.course_id = loadedNode.course_id
        node.has_children = loadedNode.has_children
        node.is_loaded = loadedNode.is_loaded
        node.children = loadedNode.children || []
        node.attachments = loadedNode.attachments || []
        // Trigger tree rerender for deep nested updates.
        courses.value = [...courses.value]
        setStatus(`已加载: ${node.title}`, 'success')
      }
    } catch (error) {
      setStatus(`加载失败: ${error.message}`, 'error')
      setExpandedState(nodeId, false)
      console.error('Failed to load node:', error)
    } finally {
      setLoadingState(nodeId, false)
    }
  }
}

const downloadNode = async (courseId, nodeId) => {
  downloadStats.value = null
  try {
    setStatus('正在下载...', 'info')
    const response = await apiClient.post(`/blackboard/files/download-batch`, null, {
      params: {
        course_id: courseId,
        node_id: nodeId
      }
    })
    if (response.data?.data?.stats) {
      downloadStats.value = response.data.data.stats
      setStatus(response.data.data.message, 'success')
    }
  } catch (error) {
    setStatus(`下载失败: ${error.message}`, 'error')
    console.error('Failed to download:', error)
  }
}

const downloadFile = async (file) => {
  try {
    if (!file?.download_url) {
      setStatus('下载失败: 文件缺少下载链接', 'error')
      return
    }

    setStatus(`开始下载文件: ${file.file_name}`, 'info')

    const isAbsolute = /^https?:\/\//.test(file.download_url)
    const url = isAbsolute
      ? file.download_url
      : `http://127.0.0.1:8000/api${file.download_url}`

    window.open(url, '_blank', 'noopener,noreferrer')
    setStatus(`已触发下载: ${file.file_name}`, 'success')
  } catch (error) {
    setStatus(`下载失败: ${error.message}`, 'error')
  }
}

const findNodeById = (nodeId) => {
  for (const course of courses.value) {
    if (course.id === nodeId) return course
    const found = findNodeInTree(course, nodeId)
    if (found) return found
  }
  return null
}

const findNodeInTree = (node, targetId) => {
  if (node.id === targetId) return node
  if (node.children) {
    for (const child of node.children) {
      const found = findNodeInTree(child, targetId)
      if (found) return found
    }
  }
  return null
}

onMounted(() => {
  refreshCourses()
  loadRagSources()
})
</script>

<style scoped>
.file-panel {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: var(--vscode-editor-background);
  color: var(--vscode-editor-foreground);
}

.file-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  padding: 1.5rem;
  border-bottom: 1px solid var(--vscode-notebook-cellBorderColor);
  gap: 2rem;
}

.file-title-area {
  flex: 1;
}

.eyebrow {
  margin: 0 0 0.25rem 0;
  font-size: 0.75rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--vscode-descriptionForeground);
}

.file-header h3 {
  margin: 0 0 0.5rem 0;
  font-size: 1.5rem;
  font-weight: 600;
}

.file-subtitle {
  margin: 0;
  font-size: 0.875rem;
  color: var(--vscode-descriptionForeground);
}

.header-controls {
  display: flex;
  gap: 0.5rem;
}

.refresh-btn {
  padding: 0.5rem 1rem;
  background: var(--vscode-button-background);
  color: var(--vscode-button-foreground);
  border: none;
  border-radius: 4px;
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-size: 0.875rem;
  transition: background 0.2s;
}

.refresh-btn:hover:not(:disabled) {
  background: var(--vscode-button-hoverBackground);
}

.refresh-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.status-bar {
  padding: 0.75rem 1.5rem;
  display: flex;
  align-items: center;
  gap: 0.75rem;
  font-size: 0.875rem;
  background-color: var(--vscode-notifications-background);
  border-bottom: 1px solid var(--vscode-notebook-cellBorderColor);
}

.status-bar.error {
  background-color: var(--vscode-inputValidation-errorBackground, rgba(244, 67, 54, 0.1));
  color: var(--vscode-inputValidation-errorForeground, #f44336);
}

.status-bar.success {
  background-color: var(--vscode-inputValidation-validationBackground, rgba(76, 175, 80, 0.1));
  color: var(--vscode-inputValidation-validationForeground, #4caf50);
}

.knowledge-base {
  display: grid;
  gap: 0.75rem;
  padding: 1rem 1.5rem;
  border-bottom: 1px solid var(--vscode-notebook-cellBorderColor);
  background: var(--vscode-sideBar-background);
}

.kb-controls {
  display: flex;
  align-items: end;
  gap: 0.75rem;
  flex-wrap: wrap;
}

.kb-field {
  display: grid;
  gap: 0.35rem;
  min-width: min(100%, 360px);
  flex: 1;
}

.kb-field label {
  font-size: 0.75rem;
  font-weight: 600;
  color: var(--vscode-descriptionForeground);
}

.kb-field input {
  padding: 0.55rem 0.7rem;
  border: 1px solid var(--vscode-input-border, transparent);
  border-radius: 4px;
  background: var(--vscode-input-background);
  color: var(--vscode-input-foreground);
}

.kb-check {
  display: inline-flex;
  align-items: center;
  gap: 0.4rem;
  min-height: 34px;
  font-size: 0.875rem;
  color: var(--vscode-descriptionForeground);
}

.refresh-btn.secondary {
  background: var(--vscode-button-secondaryBackground, var(--vscode-button-background));
  color: var(--vscode-button-secondaryForeground, var(--vscode-button-foreground));
}

.kb-source-list {
  display: grid;
  gap: 0.45rem;
  max-height: 180px;
  overflow: auto;
}

.kb-source {
  display: flex;
  justify-content: space-between;
  gap: 0.75rem;
  padding: 0.65rem 0.75rem;
  border: 1px solid var(--vscode-notebook-cellBorderColor);
  border-radius: 6px;
  background: var(--vscode-editor-background);
}

.kb-source div {
  display: grid;
  gap: 0.2rem;
  min-width: 0;
}

.kb-source strong,
.kb-source small {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.kb-source span,
.kb-empty {
  font-size: 0.8rem;
  color: var(--vscode-descriptionForeground);
}

.kb-warning,
.kb-ready {
  padding: 0.55rem 0.7rem;
  border-radius: 4px;
  font-size: 0.82rem;
}

.kb-warning {
  background: var(--vscode-inputValidation-warningBackground, rgba(245, 158, 11, 0.12));
  color: var(--vscode-inputValidation-warningForeground, #b45309);
}

.kb-ready {
  background: var(--vscode-inputValidation-validationBackground, rgba(76, 175, 80, 0.1));
  color: var(--vscode-inputValidation-validationForeground, #4caf50);
}

.kb-source small {
  color: var(--vscode-inputValidation-errorForeground, #f44336);
}

.dismiss-btn {
  margin-left: auto;
  background: none;
  border: none;
  cursor: pointer;
  font-size: 1.25rem;
  opacity: 0.7;
  transition: opacity 0.2s;
}

.dismiss-btn:hover {
  opacity: 1;
}

.file-container {
  flex: 1;
  overflow-y: auto;
  padding: 1rem;
}

.empty-state {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 100%;
  color: var(--vscode-descriptionForeground);
  text-align: center;
}

.file-tree-wrapper {
  font-size: 0.875rem;
}

.file-tree {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
}

.tree-item {
  display: flex;
  flex-direction: column;
}

.tree-node {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.5rem;
  cursor: pointer;
  border-radius: 4px;
  transition: background 0.15s;
  user-select: none;
}

.tree-node:hover {
  background: var(--vscode-list-hoverBackground);
}

.expand-icon {
  display: inline-flex;
  width: 1.25rem;
  justify-content: center;
  font-size: 0.75rem;
  transition: transform 0.2s;
  color: var(--vscode-descriptionForeground);
}

.expand-icon.expanded {
  transform: rotate(90deg);
}

.node-icon {
  display: inline-flex;
  width: 1.25rem;
  justify-content: center;
  font-size: 1rem;
}

.node-title {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.loading-spinner {
  animation: spin 1s linear infinite;
  font-size: 0.75rem;
}

@keyframes spin {
  0% { transform: rotate(0deg); }
  100% { transform: rotate(360deg); }
}

.file-node .download-hint {
  margin-left: auto;
  font-size: 0.75rem;
  color: var(--vscode-descriptionForeground);
  opacity: 0;
  transition: opacity 0.2s;
}

.file-node:hover .download-hint {
  opacity: 1;
}

.tree-children {
  display: flex;
  flex-direction: column;
  margin-left: 1.5rem;
  gap: 0.25rem;
}

.attachment .tree-node {
  cursor: pointer;
}

.attachment .tree-node:active {
  opacity: 0.8;
}

.download-stats {
  display: flex;
  gap: 2rem;
  padding: 1rem 1.5rem;
  border-top: 1px solid var(--vscode-notebook-cellBorderColor);
  background: var(--vscode-sideBar-background);
  font-size: 0.875rem;
}

.stat-item {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
}

.stat-label {
  color: var(--vscode-descriptionForeground);
  font-weight: 500;
}

.stat-value {
  font-size: 1.25rem;
  font-weight: 700;
  color: var(--vscode-editor-foreground);
}
</style>
