<template>
  <div class="tree-item" :style="{ marginLeft: `${depth * 1.5}rem` }">
    <div
      class="tree-node"
      :class="{ 'has-children': node.has_children, clickable: !isFile }"
      @click="handleNodeClick"
      @dblclick="handleDoubleClick"
    >
      <span v-if="node.has_children || node.children?.length > 0" class="expand-icon" :class="{ expanded: isExpanded }">
        ▶
      </span>
      <span v-else class="expand-icon placeholder"></span>

      <span class="node-icon">{{ getNodeIcon() }}</span>
      <span class="node-title">{{ node.title }}</span>

      <span v-if="loadingNodes.has(node.id)" class="loading-spinner">⋯</span>
      <span v-if="isThirdLevel || isFile" class="download-hint">(双击下载)</span>
    </div>

    <!-- Child nodes (限制到第三级) -->
    <div v-if="isExpanded && depth < 2 && node.children && node.children.length > 0" class="tree-children">
      <TreeNode
        v-for="child in node.children"
        :key="child.id"
        :node="child"
        :depth="depth + 1"
        :expanded-nodes="expandedNodes"
        :loading-nodes="loadingNodes"
        @toggle="(id) => $emit('toggle', id)"
        @download="(courseId, nodeId) => $emit('download', courseId, nodeId)"
        @download-file="(file) => $emit('download-file', file)"
      />
    </div>

    <div
      v-if="isExpanded && node.is_loaded && (!node.children || node.children.length === 0) && (!node.attachments || node.attachments.length === 0)"
      class="tree-children empty-hint"
    >
      <span>已加载但无直接子项，继续展开文档/作业节点查看附件</span>
    </div>

    <!-- Attachments -->
    <div v-if="isExpanded && node.attachments && node.attachments.length > 0" class="tree-children">
      <div
        v-for="file in node.attachments"
        :key="file.id"
        class="tree-item attachment"
      >
        <div class="tree-node file-node" @dblclick="handleFileDoubleClick(file)">
          <span class="expand-icon placeholder"></span>
          <span class="node-icon">📎</span>
          <span class="node-title">{{ file.file_name }}</span>
          <span class="download-hint">(双击下载)</span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'

defineOptions({
  name: 'TreeNode',
})

const props = defineProps({
  node: {
    type: Object,
    required: true,
  },
  depth: {
    type: Number,
    default: 0,
  },
  expandedNodes: {
    type: Set,
    required: true,
  },
  loadingNodes: {
    type: Set,
    required: true,
  },
})

const emit = defineEmits(['toggle', 'download', 'download-file'])

const isExpanded = computed(() => props.expandedNodes.has(props.node.id))

const isFile = computed(() => props.node.type === 'x-bb-file')

const isThirdLevel = computed(() => props.depth === 2)

const getNodeIcon = () => {
  const type = props.node.type
  if (type === 'x-bb-folder') return '📁'
  if (type === 'x-bb-document') return '📄'
  if (type === 'x-bb-file') return '📎'
  if (type === 'x-bb-assignment') return '✏️'
  if (type === 'x-bb-lesson') return '📚'
  // 第三级统一使用文件icon
  if (isThirdLevel.value) return '📄'
  return '📋'
}

const handleNodeClick = () => {
  if (
    props.node.has_children ||
    (props.node.children && props.node.children.length > 0) ||
    props.node.type === 'x-bb-document' ||
    props.node.type === 'x-bb-file' ||
    props.node.type === 'x-bb-assignment' ||
    props.node.type === 'x-bb-lesson'
  ) {
    emit('toggle', props.node.id)
  }
}

const handleDoubleClick = () => {
  // 只有真正的文件类型才触发下载，其他类型（文件夹、作业等）双击无作用
  if (isFile.value) {
    emit('download', props.node.course_id, props.node.id)
  }
}

const handleFileDoubleClick = (file) => {
  emit('download-file', file)
}
</script>

<style scoped>
.tree-item {
  display: flex;
  flex-direction: column;
}

.tree-node {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.5rem;
  border-radius: 4px;
  transition: background 0.15s;
  user-select: none;
  font-size: 0.875rem;
}

.empty-hint {
  margin-left: 1.75rem;
  margin-top: 0.25rem;
  margin-bottom: 0.25rem;
  font-size: 0.78rem;
  color: var(--vscode-descriptionForeground);
}

.tree-node.clickable {
  cursor: pointer;
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
  cursor: pointer;
}

.expand-icon.expanded {
  transform: rotate(90deg);
}

.expand-icon.placeholder {
  cursor: default;
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
  color: var(--vscode-editor-foreground);
}

.loading-spinner {
  animation: spin 1s linear infinite;
  font-size: 0.75rem;
  color: var(--vscode-descriptionForeground);
}

@keyframes spin {
  0% { transform: rotate(0deg); }
  100% { transform: rotate(360deg); }
}

.download-hint {
  margin-left: auto;
  font-size: 0.75rem;
  color: var(--vscode-descriptionForeground);
  opacity: 0;
  transition: opacity 0.2s;
  white-space: nowrap;
  margin-right: 0.5rem;
}

.file-node:hover .download-hint {
  opacity: 1;
}

.file-node {
  cursor: pointer;
}

.file-node:active {
  opacity: 0.8;
}

.tree-children {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
}

.attachment {
  margin-left: 0;
}
</style>
