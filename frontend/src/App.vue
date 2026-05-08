<template>
  <main class="app-shell">
    <!-- Sidebar -->
    <aside class="sidebar">
      <div class="sidebar-top">
        <!-- Logo Area -->
        <div class="logo-area">
          <div class="logo-icon">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="2.5">
              <path d="M12 2L2 7l10 5 10-5-10-5z"/>
              <path d="M2 17l10 5 10-5"/>
              <path d="M2 12l10 5 10-5"/>
            </svg>
          </div>
          <span class="logo-text">StudyAI</span>
        </div>

        <!-- Tab Navigation -->
        <nav class="tab-nav">
          <button :class="['tab-item', { active: activeView === 'chat' }]" @click="activeView = 'chat'">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>
            </svg>
            <span>对话</span>
          </button>
          <button class="tab-item" @click="quizHistoryOpen = true">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <circle cx="12" cy="12" r="10"/>
              <path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3"/>
              <line x1="12" y1="17" x2="12.01" y2="17"/>
            </svg>
            <span>测验</span>
          </button>
          <button :class="['tab-item', { active: activeView === 'rag' }]" @click="activeView = 'rag'">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"/>
              <path d="M4 4.5A2.5 2.5 0 0 1 6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5z"/>
              <path d="M8 7h8"/>
              <path d="M8 11h6"/>
            </svg>
            <span>知识库</span>
          </button>
          <button :class="['tab-item', { active: activeView === 'calendar' }]" @click="activeView = 'calendar'">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <rect x="3" y="3" width="18" height="18" rx="2" ry="2"/>
              <line x1="3" y1="9" x2="21" y2="9"/>
              <line x1="9" y1="21" x2="9" y2="9"/>
            </svg>
            <span>日程</span>
          </button>
          <button class="tab-item" @click="settingsOpen = true">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <circle cx="12" cy="12" r="3"/>
              <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"/>
            </svg>
            <span>设置</span>
          </button>
        </nav>

        <!-- Conversation List -->
        <div class="conv-section">
          <div class="conv-header">
            <p class="section-title">历史对话</p>
            <button class="new-chat-btn" @click="createConversation" title="新建对话">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <line x1="12" y1="5" x2="12" y2="19"/>
                <line x1="5" y1="12" x2="19" y2="12"/>
              </svg>
            </button>
          </div>
          <div class="conv-list">
            <article
              v-for="conversation in sortedConversations"
              :key="conversation.id"
              :class="['conv-item', { active: conversation.id === activeConversationId }]"
              @click="selectConversation(conversation.id)"
            >
              <div class="conv-info">
                <strong v-if="editingConversationId !== conversation.id">{{ conversation.title }}</strong>
                <input
                  v-else
                  v-model="editingTitle"
                  class="rename-input"
                  @click.stop
                  @keydown.enter.prevent="confirmRename(conversation.id)"
                  @keydown.esc.prevent="cancelRename"
                />
                <span class="conv-time">{{ formatConversationTime(conversation.updatedAt) }}</span>
              </div>
              <div class="conv-actions">
                <button
                  v-if="editingConversationId !== conversation.id"
                  class="icon-btn"
                  title="重命名"
                  @click.stop="beginRename(conversation)"
                >
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/>
                    <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/>
                  </svg>
                </button>
                <button
                  class="icon-btn delete"
                  title="删除"
                  @click.stop="deleteConversation(conversation.id)"
                >
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <polyline points="3 6 5 6 21 6"/>
                    <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/>
                  </svg>
                </button>
              </div>
            </article>
          </div>
        </div>

        <!-- User Profile -->
        <div class="user-profile">
          <div class="user-avatar">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/>
              <circle cx="12" cy="7" r="4"/>
            </svg>
          </div>
          <div class="user-info">
            <strong>用户</strong>
            <span>在线</span>
          </div>
        </div>
      </div>
    </aside>

    <!-- Main Content -->
    <section class="main-content">
      <template v-if="activeView === 'chat'">
      <!-- Header -->
      <header :class="['header', { collapsed: !headerExpanded }]">
        <div v-if="headerExpanded" class="header-left">
          <h2>{{ activeConversation.title }}</h2>
          <p>继续之前的对话或开始新对话</p>
          <div class="header-meta">
            <span class="meta-chip">StudyAI Workspace</span>
            <span class="meta-chip subtle">{{ activeConversation.messages.length }} 条消息</span>
          </div>
        </div>
        <div v-if="headerExpanded" class="header-right">
          <div class="workspace-field">
            <span>工作目录</span>
            <WorkspaceDirectoryPicker
              v-model="activeConversation.workspaceRoot"
              @error="handleWorkspacePickerError"
            />
          </div>
          <button class="header-btn" :disabled="loading" @click="loadCourses">
            加载课程
          </button>
        </div>
        <button
          :class="['header-toggle', { collapsed: !headerExpanded }]"
          type="button"
          :aria-label="headerExpanded ? '收起顶部栏' : '展开顶部栏'"
          @click="headerExpanded = !headerExpanded"
        >
          <svg
            width="18"
            height="18"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            stroke-width="2"
            stroke-linecap="round"
            stroke-linejoin="round"
          >
            <path v-if="headerExpanded" d="M18 15l-6-6-6 6" />
            <path v-else d="M6 9l6 6 6-6" />
          </svg>
        </button>
      </header>

      <!-- Chat Container -->
      <div class="chat-container">
        <article
          v-for="message in activeConversation.messages"
          :key="message.id"
          :class="['message-row', message.role]"
        >
          <div v-if="message.role === 'assistant'" :class="['avatar', message.role]">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M12 2L2 7l10 5 10-5-10-5z"/>
              <path d="M2 17l10 5 10-5"/>
              <path d="M2 12l10 5 10-5"/>
            </svg>
          </div>
          <div :class="['message-bubble', message.role]">
            <div v-if="message.role === 'assistant' || message.elapsedLabel" class="message-meta">
              <span v-if="message.role === 'assistant'" class="role-label">StudyAI</span>
              <span v-if="message.elapsedLabel" class="elapsed">{{ message.elapsedLabel }}</span>
            </div>
            <template v-for="(part, i) in message.parts" :key="`${message.id}-${i}`">
              <div v-if="part.type === 'text'" class="markdown-body" v-html="renderMarkdown(part.content)" />
              <details v-else-if="part.type === 'thinking'" class="thinking-block">
                <summary class="thinking-summary">
                  <span class="thinking-label">思考过程</span>
                </summary>
                <div class="markdown-body thinking-content" v-html="renderMarkdown(part.content)" />
              </details>
              <details v-else-if="part.type === 'tool'" class="tool-event">
                <summary class="tool-event-summary">
                  <span class="tool-event-name">{{ part.toolEvent.tool_name }}</span>
                  <span :class="['tool-event-status', part.toolEvent.status]">{{ formatToolStatus(part.toolEvent.status) }}</span>
                </summary>
                <div class="tool-event-body">
                  <div class="tool-event-block">
                    <strong>输入</strong>
                    <pre>{{ formatToolPayload(part.toolEvent.arguments) }}</pre>
                  </div>
                  <div v-if="part.toolEvent.output" class="tool-event-block">
                    <strong>输出</strong>
                    <pre>{{ formatToolPayload(part.toolEvent.output) }}</pre>
                  </div>
                </div>
              </details>
              <QuizPanel
                v-if="part.type === 'tool' && part.toolEvent.tool_name === 'create_quiz' && tryParseToolOutput(part.toolEvent.output)?.quiz_session"
                :quiz="tryParseToolOutput(part.toolEvent.output).quiz_session"
              />
            </template>
          </div>
        </article>

      </div>

      <!-- Approval Panel -->
      <Transition name="approval-slide">
        <section v-if="activeConversation.pendingApproval" class="approval-banner">
          <div class="approval-content">
            <div class="approval-icon">
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>
                <path d="M12 8v4"/>
                <path d="M12 16h.01"/>
              </svg>
            </div>
            <div>
              <p class="eyebrow">需要审批</p>
              <h3>{{ activeConversation.pendingApproval.tool_name }}</h3>
              <p>{{ activeConversation.pendingApproval.summary }}</p>
              <code v-if="activeConversation.pendingApproval.workspace_root">
                {{ activeConversation.pendingApproval.workspace_root }}
              </code>
            </div>
          </div>
          <div class="approval-actions">
            <button :disabled="loading" @click="resolveApproval(true)">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
                <polyline points="20 6 9 17 4 12"/>
              </svg>
              <span>批准</span>
            </button>
            <button class="secondary" :disabled="loading" @click="resolveApproval(false)">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
                <line x1="18" y1="6" x2="6" y2="18"/>
                <line x1="6" y1="6" x2="18" y2="18"/>
              </svg>
              <span>拒绝</span>
            </button>
          </div>
        </section>
      </Transition>

      <!-- Composer -->
      <div class="composer-wrapper">
        <div class="composer">
          <textarea
            ref="composerInput"
            v-model="draft"
            rows="1"
            placeholder="输入消息... (Shift + Enter 换行)"
            @input="autoResizeComposer"
            @keydown.enter.exact.prevent="submitMessage"
          />
        </div>
        <button
          v-if="chatStreaming"
          class="send-btn stop-btn"
          @click="stopActiveChat"
        >
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <rect x="7" y="7" width="10" height="10" rx="1.5" ry="1.5"/>
          </svg>
          <span>停止</span>
        </button>
        <button
          v-else
          class="send-btn"
          :disabled="loading || !draft.trim()"
          @click="submitMessage"
        >
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <line x1="22" y1="2" x2="11" y2="13"/>
            <polygon points="22 2 15 22 11 13 2 9 22 2"/>
          </svg>
          <span>发送</span>
        </button>
      </div>
      </template>

      <RagPanel v-else-if="activeView === 'rag'" />
      <CalendarPanel v-else />
    </section>

    <div v-if="settingsOpen" class="overlay" @click.self="settingsOpen = false">
      <div class="overlay-panel">
        <SettingsPanel
          @close="settingsOpen = false"
          @open-database-overview="databaseOpen = true"
        />
      </div>
    </div>

    <div v-if="quizHistoryOpen" class="overlay" @click.self="quizHistoryOpen = false">
      <div class="overlay-panel">
        <QuizHistoryPanel @close="quizHistoryOpen = false" />
      </div>
    </div>

    <div v-if="databaseOpen" class="overlay" @click.self="databaseOpen = false">
      <div class="overlay-panel">
        <DatabaseOverviewPanel @close="databaseOpen = false" />
      </div>
    </div>
  </main>
</template>

<script setup>
import MarkdownIt from "markdown-it";
import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref, watch } from "vue";
import CalendarPanel from "./components/CalendarPanel.vue";
import QuizPanel from "./components/QuizPanel.vue";
import DatabaseOverviewPanel from "./components/DatabaseOverviewPanel.vue";
import QuizHistoryPanel from "./components/QuizHistoryPanel.vue";
import RagPanel from "./components/RagPanel.vue";
import SettingsPanel from "./components/SettingsPanel.vue";
import WorkspaceDirectoryPicker from "./components/WorkspaceDirectoryPicker.vue";
import {
  getCourses,
  getHealth,
  streamApprovalDecision,
  streamChat
} from "./api/client";

const CHAT_CONVERSATIONS_KEY = "spa-conversations";
const ACTIVE_CONVERSATION_KEY = "spa-active-conversation-id";

const markdown = new MarkdownIt({
  html: false,
  breaks: true,
  linkify: true
});

function makeConversation(title = "新对话") {
  return reactive({
    id: crypto.randomUUID(),
    title,
    createdAt: Date.now(),
    updatedAt: Date.now(),
    workspaceRoot: "",
    pendingApproval: null,
    messages: [
      reactive({
        id: crypto.randomUUID(),
        role: "assistant",
        parts: [
          { type: "text", content: "你好！我是 StudyAI 助手，可以帮助你查询课程、搜索文件、管理记忆等。有什么可以帮你的吗？" }
        ],
        elapsedLabel: ""
      })
    ]
  });
}

function migrateMessage(message) {
  if (message.parts) {
    return reactive({ ...message, content: undefined, toolEvents: undefined });
  }
  const parts = [];
  if (message.toolEvents?.length) {
    message.toolEvents.forEach((te) => parts.push({ type: "tool", toolEvent: te }));
  }
  if (message.content) {
    parts.push({ type: "text", content: message.content });
  }
  return reactive({ ...message, parts, content: undefined, toolEvents: undefined });
}

function restoreConversations() {
  try {
    const raw = JSON.parse(window.localStorage.getItem(CHAT_CONVERSATIONS_KEY) || "null");
    if (!Array.isArray(raw) || raw.length === 0) {
      return [makeConversation("欢迎对话")];
    }
    return raw.map((conversation) =>
      reactive({
        ...conversation,
        workspaceRoot: conversation.workspaceRoot || "",
        pendingApproval: conversation.pendingApproval || null,
        messages: (conversation.messages || []).map((message) => migrateMessage(message))
      })
    );
  } catch {
    return [makeConversation("欢迎对话")];
  }
}

const status = ref("Unknown");
const checking = ref(false);
const settingsOpen = ref(false);
const quizHistoryOpen = ref(false);
const databaseOpen = ref(false);
const activeView = ref("chat");

const conversations = ref(restoreConversations());
const activeConversationId = ref(
  window.localStorage.getItem(ACTIVE_CONVERSATION_KEY) || conversations.value[0].id
);
const editingConversationId = ref("");
const editingTitle = ref("");
const draft = ref("");
const composerInput = ref(null);
const loading = ref(false);
const chatStreaming = ref(false);
const headerExpanded = ref(false);
let activeTimer = null;
let activeChatAbortController = null;
let chatStopRequested = false;

const sortedConversations = computed(() =>
  [...conversations.value].sort((left, right) => (right.updatedAt || 0) - (left.updatedAt || 0))
);

function scrollToBottom() {
  nextTick(() => {
    const mainContent = document.querySelector(".main-content");
    if (mainContent) {
      mainContent.scrollTop = mainContent.scrollHeight;
    }
  });
}

function resizeComposer(target) {
  if (!target) return;
  const maxHeight = 160;
  target.style.height = "auto";
  target.style.height = `${Math.min(target.scrollHeight, maxHeight)}px`;
  target.style.overflowY = target.scrollHeight > maxHeight ? "auto" : "hidden";
}

function autoResizeComposer(event) {
  resizeComposer(event.target);
}

const activeConversation = computed(() => {
  const conversation =
    conversations.value.find((item) => item.id === activeConversationId.value) || conversations.value[0];
  if (!conversation) {
    const fallback = makeConversation("恢复的对话");
    conversations.value = [fallback];
    activeConversationId.value = fallback.id;
    return fallback;
  }
  return conversation;
});

function persistConversations() {
  window.localStorage.setItem(CHAT_CONVERSATIONS_KEY, JSON.stringify(conversations.value));
  window.localStorage.setItem(ACTIVE_CONVERSATION_KEY, activeConversationId.value);
}

function renderMarkdown(content) {
  return markdown.render(content || "");
}

function formatConversationTime(timestamp) {
  const date = new Date(timestamp || Date.now());
  const time = date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  const now = new Date();
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const yesterday = new Date(today.getTime() - 86400000);
  const msgDay = new Date(date.getFullYear(), date.getMonth(), date.getDate());
  if (msgDay.getTime() >= today.getTime()) return time;
  if (msgDay.getTime() >= yesterday.getTime()) return `昨天 ${time}`;
  return `${date.getFullYear()}/${String(date.getMonth() + 1).padStart(2, "0")}/${String(date.getDate()).padStart(2, "0")} ${time}`;
}

function formatElapsed(ms) {
  if (ms < 1000) return `${ms} ms`;
  return `${(ms / 1000).toFixed(1)} s`;
}

function formatToolStatus(status) {
  if (status === "running") return "运行中";
  if (status === "completed") return "完成";
  if (status === "failed") return "失败";
  if (status === "denied") return "已拒绝";
  if (status === "awaiting_approval") return "等待审批";
  return status;
}

function formatToolPayload(payload) {
  if (typeof payload === "string") {
    return payload;
  }
  return JSON.stringify(payload, null, 2);
}

function tryParseToolOutput(output) {
  if (!output || typeof output !== "string") return null;
  try {
    return JSON.parse(output);
  } catch {
    return null;
  }
}

function startTimer(message) {
  const startedAt = Date.now();
  message.elapsedLabel = "0 ms";
  activeTimer = window.setInterval(() => {
    message.elapsedLabel = formatElapsed(Date.now() - startedAt);
  }, 100);
  return () => {
    if (activeTimer) {
      window.clearInterval(activeTimer);
      activeTimer = null;
    }
    message.elapsedLabel = formatElapsed(Date.now() - startedAt);
  };
}

function updateConversationTitle(conversation) {
  const firstUserMessage = conversation.messages.find((message) => message.role === "user");
  if (!firstUserMessage) return;
  const firstText = firstUserMessage.parts?.find((p) => p.type === "text");
  const text = firstText?.content || "";
  conversation.title = text.slice(0, 20) || conversation.title;
}

function createConversation() {
  const conversation = makeConversation(`新对话 ${conversations.value.length + 1}`);
  conversations.value.unshift(conversation);
  activeConversationId.value = conversation.id;
  editingConversationId.value = "";
  draft.value = "";
  nextTick(() => resizeComposer(composerInput.value));
  persistConversations();
}

function selectConversation(id) {
  activeConversationId.value = id;
  persistConversations();
  scrollToBottom();
}

function deleteConversation(id) {
  const remaining = conversations.value.filter((conversation) => conversation.id !== id);
  conversations.value = remaining.length ? remaining : [makeConversation("欢迎对话")];
  if (editingConversationId.value === id) {
    editingConversationId.value = "";
    editingTitle.value = "";
  }
  if (!conversations.value.some((conversation) => conversation.id === activeConversationId.value)) {
    activeConversationId.value = conversations.value[0].id;
  }
  persistConversations();
}

function beginRename(conversation) {
  editingConversationId.value = conversation.id;
  editingTitle.value = conversation.title;
}

function cancelRename() {
  editingConversationId.value = "";
  editingTitle.value = "";
}

function confirmRename(id) {
  const conversation = conversations.value.find((item) => item.id === id);
  if (!conversation) return;
  const nextTitle = editingTitle.value.trim();
  if (nextTitle) {
    conversation.title = nextTitle;
    conversation.updatedAt = Date.now();
  }
  cancelRename();
  persistConversations();
}

function appendMessage(role, content) {
  activeConversation.value.messages.push(
    reactive({
      id: crypto.randomUUID(),
      role,
      parts: content ? [{ type: "text", content }] : [],
      elapsedLabel: ""
    })
  );
  activeConversation.value.updatedAt = Date.now();
  scrollToBottom();
}

function handleWorkspacePickerError(error) {
  appendMessage("assistant", `工作目录选择失败: ${error.message}`);
}

async function loadCourses() {
  loading.value = true;
  try {
    const response = await getCourses();
    const courses = response.data?.data ?? [];
    const summary = courses.map((item) => `- ${item.name} (${item.blackboard_course_id})`).join("\n");
    appendMessage("assistant", summary || "没有返回课程。");
  } catch (error) {
    appendMessage("assistant", `课程请求失败: ${error.message}`);
  } finally {
    loading.value = false;
  }
}

async function submitMessage() {
  if (loading.value) return;

  const content = draft.value.trim();
  if (!content) return;

  const conversation = activeConversation.value;
  conversation.messages.push(
    reactive({
      id: crypto.randomUUID(),
      role: "user",
      parts: [{ type: "text", content }],
      elapsedLabel: ""
    })
  );
  const assistantMessage = reactive({
    id: crypto.randomUUID(),
    role: "assistant",
    parts: [{ type: "text", content: "正在等待模型响应..." }],
    elapsedLabel: ""
  });
  conversation.messages.push(assistantMessage);
  conversation.updatedAt = Date.now();
  conversation.pendingApproval = null;
  updateConversationTitle(conversation);
  draft.value = "";
  nextTick(() => resizeComposer(composerInput.value));
  loading.value = true;
  chatStreaming.value = true;
  chatStopRequested = false;
  activeChatAbortController = new AbortController();
  const stopTimer = startTimer(assistantMessage);
  scrollToBottom();

  const WAITING_TEXT = "正在等待模型响应...";

  try {
    await streamChat(
      {
        message: content,
        session_id: conversation.id,
        workspace_root: conversation.workspaceRoot?.trim() || null
      },
      {
        onChunk(text) {
          const lastPart = assistantMessage.parts.at(-1);
          if (lastPart?.type === "text" && lastPart.content === WAITING_TEXT) {
            lastPart.content = "";
          }
          const appendPart = assistantMessage.parts.at(-1);
          if (!appendPart || appendPart.type !== "text") {
            assistantMessage.parts.push({ type: "text", content: text });
          } else {
            appendPart.content += text;
          }
          scrollToBottom();
        },
        onReasoning(thinking) {
          const firstPart = assistantMessage.parts[0];
          if (firstPart?.type === "text" && firstPart.content === WAITING_TEXT) {
            assistantMessage.parts.shift();
          }
          const appendPart = assistantMessage.parts.at(-1);
          if (!appendPart || appendPart.type !== "thinking") {
            assistantMessage.parts.push({ type: "thinking", content: thinking });
          } else {
            appendPart.content += thinking;
          }
          scrollToBottom();
        },
        onToolEvents(toolEvents) {
          const firstPart = assistantMessage.parts[0];
          if (firstPart?.type === "text" && firstPart.content === WAITING_TEXT) {
            assistantMessage.parts.shift();
          }
          const existingToolParts = assistantMessage.parts.filter((p) => p.type === "tool");
          toolEvents.forEach((newEvent, idx) => {
            if (idx < existingToolParts.length) {
              existingToolParts[idx].toolEvent = newEvent;
            } else {
              assistantMessage.parts.push({ type: "tool", toolEvent: newEvent });
            }
          });
          scrollToBottom();
        },
        onApprovalRequired(approval) {
          const firstPart = assistantMessage.parts[0];
          if (firstPart?.type === "text" && firstPart.content === WAITING_TEXT) {
            assistantMessage.parts.shift();
          }
          const lastPart = assistantMessage.parts.at(-1);
          if (lastPart?.type === "text") {
            lastPart.content = "工具调用正在等待你的审批。";
          } else {
            assistantMessage.parts.push({ type: "text", content: "工具调用正在等待你的审批。" });
          }
          (approval.tool_events || []).forEach((te) => {
            const toolParts = assistantMessage.parts.filter((p) => p.type === "tool");
            const existingIdx = toolParts.findIndex(
              (tp) => tp.toolEvent.tool_name === te.tool_name
            );
            if (existingIdx >= 0) {
              toolParts[existingIdx].toolEvent = te;
            } else {
              assistantMessage.parts.push({ type: "tool", toolEvent: te });
            }
          });
          conversation.pendingApproval = approval;
          scrollToBottom();
        },
        onDone(payload) {
          const lastText = assistantMessage.parts.findLast((p) => p.type === "text");
          if (lastText) {
            lastText.content = lastText.content.trim();
          }
          const lastThinking = assistantMessage.parts.findLast((p) => p.type === "thinking");
          if (lastThinking) {
            lastThinking.content = lastThinking.content.trim();
          }
          scrollToBottom();
        }
      },
      {
        signal: activeChatAbortController.signal
      }
    );
  } catch (error) {
    const aborted = chatStopRequested || error?.name === "AbortError";
    const lastText = assistantMessage.parts.findLast((p) => p.type === "text");
    if (aborted) {
      if (lastText) {
        const partial = lastText.content.trim();
        lastText.content = partial ? `${partial}\n\n[已停止生成]` : "已停止生成。";
      }
    } else {
      if (lastText) {
        lastText.content = `聊天失败: ${error.message}`;
      } else {
        assistantMessage.parts.push({ type: "text", content: `聊天失败: ${error.message}` });
      }
    }
  } finally {
    conversation.updatedAt = Date.now();
    stopTimer();
    activeChatAbortController = null;
    chatStopRequested = false;
    chatStreaming.value = false;
    loading.value = false;
  }
}

function stopActiveChat() {
  if (!chatStreaming.value || !activeChatAbortController) return;
  chatStopRequested = true;
  activeChatAbortController.abort();
}

async function resolveApproval(approved) {
  const conversation = activeConversation.value;
  const pending = conversation.pendingApproval;
  if (!pending) return;

  const INITIAL_TEXT = approved ? "正在执行批准的操作..." : "审批被拒绝。让智能体继续...";
  const assistantMessage = reactive({
    id: crypto.randomUUID(),
    role: "assistant",
    parts: [{ type: "text", content: INITIAL_TEXT }],
    elapsedLabel: ""
  });
  conversation.messages.push(assistantMessage);
  conversation.pendingApproval = null;
  conversation.updatedAt = Date.now();
  loading.value = true;
  const stopTimer = startTimer(assistantMessage);
  scrollToBottom();


  try {
    await streamApprovalDecision(
      {
        session_id: conversation.id,
        approval_id: pending.id,
        approved
      },
      {
        onChunk(text) {
          const lastPart = assistantMessage.parts.at(-1);
          if (lastPart?.type === "text" && lastPart.content === INITIAL_TEXT) {
            lastPart.content = "";
          }
          const appendPart = assistantMessage.parts.at(-1);
          if (!appendPart || appendPart.type !== "text") {
            assistantMessage.parts.push({ type: "text", content: text });
          } else {
            appendPart.content += text;
          }
          scrollToBottom();
        },
        onReasoning(thinking) {
          const firstPart = assistantMessage.parts[0];
          if (firstPart?.type === "text" && firstPart.content === INITIAL_TEXT) {
            assistantMessage.parts.shift();
          }
          const appendPart = assistantMessage.parts.at(-1);
          if (!appendPart || appendPart.type !== "thinking") {
            assistantMessage.parts.push({ type: "thinking", content: thinking });
          } else {
            appendPart.content += thinking;
          }
          scrollToBottom();
        },
        onToolEvents(toolEvents) {
          const firstPart = assistantMessage.parts[0];
          if (firstPart?.type === "text" && firstPart.content === INITIAL_TEXT) {
            assistantMessage.parts.shift();
          }
          const existingToolParts = assistantMessage.parts.filter((p) => p.type === "tool");
          toolEvents.forEach((newEvent, idx) => {
            if (idx < existingToolParts.length) {
              existingToolParts[idx].toolEvent = newEvent;
            } else {
              assistantMessage.parts.push({ type: "tool", toolEvent: newEvent });
            }
          });
          scrollToBottom();
        },
        onApprovalRequired(nextApproval) {
          const firstPart = assistantMessage.parts[0];
          if (firstPart?.type === "text" && firstPart.content === INITIAL_TEXT) {
            assistantMessage.parts.shift();
          }
          const lastPart = assistantMessage.parts.at(-1);
          if (lastPart?.type === "text") {
            lastPart.content = "另一个操作正在等待你的审批。";
          } else {
            assistantMessage.parts.push({ type: "text", content: "另一个操作正在等待你的审批。" });
          }
          (nextApproval.tool_events || []).forEach((te) => {
            const toolParts = assistantMessage.parts.filter((p) => p.type === "tool");
            const existingIdx = toolParts.findIndex(
              (tp) => tp.toolEvent.tool_name === te.tool_name
            );
            if (existingIdx >= 0) {
              toolParts[existingIdx].toolEvent = te;
            } else {
              assistantMessage.parts.push({ type: "tool", toolEvent: te });
            }
          });
          conversation.pendingApproval = nextApproval;
          scrollToBottom();
        },
        onDone(payload) {
          const lastText = assistantMessage.parts.findLast((p) => p.type === "text");
          if (lastText) {
            lastText.content = lastText.content.trim();
          }
          const lastThinking = assistantMessage.parts.findLast((p) => p.type === "thinking");
          if (lastThinking) {
            lastThinking.content = lastThinking.content.trim();
          }
          scrollToBottom();
        }
      }
    );
  } catch (error) {
    const lastText = assistantMessage.parts.findLast((p) => p.type === "text");
    if (lastText) {
      lastText.content = `审批流程失败: ${error.message}`;
    } else {
      assistantMessage.parts.push({ type: "text", content: `审批流程失败: ${error.message}` });
    }
  } finally {
    conversation.updatedAt = Date.now();
    stopTimer();
    loading.value = false;
  }
}

async function checkHealth() {
  checking.value = true;
  try {
    const response = await getHealth();
    status.value = response.data?.status === "ok" ? "后端正常" : "意外响应";
  } catch (error) {
    status.value = `不可用: ${error.message}`;
  } finally {
    checking.value = false;
  }
}

watch(
  [conversations, activeConversationId],
  () => {
    persistConversations();
  },
  { deep: true }
);

onBeforeUnmount(() => {
  if (activeTimer) window.clearInterval(activeTimer);
  if (activeChatAbortController) {
    activeChatAbortController.abort();
    activeChatAbortController = null;
  }
});

onMounted(() => {
  resizeComposer(composerInput.value);
});
</script>

<style>
/* Design System Variables */
:root {
  color-scheme: light;
  --bg-main: #f3f0ea;
  --bg-main-soft: #fcfbf8;
  --bg-card: rgba(255, 255, 255, 0.78);
  --bg-card-strong: rgba(255, 255, 255, 0.92);
  --bg-sidebar: rgba(251, 249, 244, 0.84);
  --bg-hover: rgba(33, 41, 52, 0.05);
  --accent: #1f6f78;
  --accent-light: #2f8b93;
  --accent-orange: #da6a1e;
  --accent-orange-light: #fdf1e4;
  --accent-orange-subtle: #f8dfc7;
  --accent-line: rgba(218, 106, 30, 0.16);
  --ink: #1f2933;
  --ink-light: #5b6773;
  --text-primary: #171717;
  --text-secondary: #5f6368;
  --text-muted: #8b8f94;
  --text-placeholder: #9aa0a6;
  --border-default: #e8e0d5;
  --border-light: rgba(53, 62, 72, 0.1);
  --border-subtle: rgba(53, 62, 72, 0.06);
  --shadow-glass: rgba(15, 23, 42, 0.06);
  --shadow-subtle: rgba(15, 23, 42, 0.04);
  --shadow-sm: rgba(15, 23, 42, 0.08);
  --shadow-md: rgba(15, 23, 42, 0.12);
  --shadow-elevated: rgba(15, 23, 42, 0.14);
  --shadow-float: rgba(15, 23, 42, 0.2);
  --radius-sm: 10px;
  --radius-md: 14px;
  --radius-lg: 20px;
  --radius-xl: 24px;
  --radius-2xl: 28px;
  /* Fonts */
  --font-heading: -apple-system, BlinkMacSystemFont, "SF Pro Display", "SF Pro Text", "Helvetica Neue", "PingFang SC", "Microsoft YaHei", sans-serif;
  --font-body: -apple-system, BlinkMacSystemFont, "SF Pro Text", "SF Pro Display", "Helvetica Neue", "PingFang SC", "Microsoft YaHei", sans-serif;
  --font-mono: "SF Mono", ui-monospace, "Cascadia Code", "Roboto Mono", "Menlo", monospace;
}

* {
  box-sizing: border-box;
}

body {
  margin: 0;
  font-family: var(--font-body);
  background:
    radial-gradient(circle at top left, rgba(31, 111, 120, 0.08), transparent 20%),
    radial-gradient(circle at bottom right, rgba(218, 106, 30, 0.1), transparent 24%),
    linear-gradient(180deg, #f8f5ef 0%, var(--bg-main) 100%);
  color: var(--ink);
  -webkit-font-smoothing: antialiased;
}

/* App Shell Layout */
.app-shell {
  display: grid;
  grid-template-columns: 280px 1fr;
  height: 100vh;
  overflow: hidden;
  padding: 18px;
  gap: 18px;
}

/* Sidebar */
.sidebar {
  position: relative;
  height: calc(100vh - 36px);
  background: var(--bg-sidebar);
  backdrop-filter: blur(24px);
  border: 1px solid rgba(255, 255, 255, 0.5);
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.7), 0 16px 40px var(--shadow-glass);
  border-radius: 30px;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.sidebar-top {
  display: flex;
  flex-direction: column;
  height: 100%;
  padding: 22px 18px;
  gap: 22px;
}

/* Logo Area */
.logo-area {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 4px 4px 18px;
  border-bottom: 1px solid var(--border-subtle);
}

.logo-icon {
  width: 42px;
  height: 42px;
  border-radius: 16px;
  background: linear-gradient(135deg, var(--accent) 0%, var(--accent-orange) 100%);
  display: flex;
  align-items: center;
  justify-content: center;
  color: white;
  box-shadow: 0 10px 24px rgba(31, 111, 120, 0.22);
}

.logo-text {
  font-family: var(--font-heading);
  font-size: 20px;
  font-weight: 600;
  letter-spacing: -0.02em;
  color: var(--text-primary);
}

/* Tab Navigation */
.tab-nav {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.tab-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 13px 16px;
  border: none;
  border-radius: 18px;
  background: transparent;
  color: var(--text-secondary);
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s ease;
}

.tab-item:hover {
  background: rgba(255, 255, 255, 0.72);
  color: var(--text-primary);
  transform: translateX(2px);
}

.tab-item.active {
  background: linear-gradient(135deg, rgba(255, 255, 255, 0.94), rgba(248, 223, 199, 0.95));
  color: var(--accent-orange);
  box-shadow: 0 10px 24px rgba(218, 106, 30, 0.1);
}

/* Conversation Section */
.conv-section {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 8px;
  overflow: hidden;
}

.section-title {
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 1px;
  text-transform: uppercase;
  color: var(--text-muted);
  padding: 0 8px;
  margin: 0;
}

.conv-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0 8px;
}

.new-chat-btn {
  width: 32px;
  height: 32px;
  border: none;
  border-radius: 10px;
  background: linear-gradient(135deg, var(--accent-orange), #ee8a3a);
  color: white;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.2s ease;
}

.new-chat-btn:hover {
  background: #EA580C;
  transform: scale(1.05);
}

.conv-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
  overflow-y: auto;
  padding-right: 4px;
}

.conv-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 13px;
  border-radius: 16px;
  border: 1px solid transparent;
  cursor: pointer;
  transition: all 0.18s ease;
}

.conv-item:hover {
  background: rgba(255, 255, 255, 0.78);
  border-color: rgba(255, 255, 255, 0.8);
}

.conv-item.active {
  background: linear-gradient(135deg, rgba(255, 255, 255, 0.94), rgba(248, 223, 199, 0.92));
  border-color: var(--accent-line);
  box-shadow: 0 12px 24px rgba(218, 106, 30, 0.08);
}

.conv-info {
  flex: 1;
  min-width: 0;
}

.conv-info strong {
  display: block;
  font-size: 13px;
  color: var(--text-primary);
  font-weight: 600;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.conv-time {
  font-size: 11px;
  color: var(--text-muted);
}

.conv-actions {
  display: flex;
  gap: 4px;
  opacity: 0;
  transition: opacity 0.15s ease;
}

.conv-item:hover .conv-actions {
  opacity: 1;
}

.icon-btn {
  width: 28px;
  height: 28px;
  border: none;
  border-radius: 10px;
  background: rgba(31, 41, 55, 0.05);
  color: var(--text-muted);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.15s ease;
}

.icon-btn:hover {
  background: var(--accent-orange-subtle);
  color: var(--accent-orange);
}

.icon-btn.delete:hover {
  background: rgba(239, 68, 68, 0.1);
  color: #ef4444;
}

.rename-input {
  width: 100%;
  padding: 4px 8px;
  border: 1px solid var(--border-default);
  border-radius: 8px;
  font-size: 13px;
}

/* User Profile */
.user-profile {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 14px 16px;
  background: var(--bg-card-strong);
  border: 1px solid rgba(255, 255, 255, 0.72);
  border-radius: 22px;
  box-shadow: 0 12px 24px var(--shadow-subtle);
}

.user-avatar {
  width: 40px;
  height: 40px;
  border-radius: 16px;
  background: linear-gradient(135deg, var(--accent-orange), #ef8d3f);
  color: white;
  display: flex;
  align-items: center;
  justify-content: center;
}

.user-info {
  display: flex;
  flex-direction: column;
}

.user-info strong {
  font-size: 14px;
  color: var(--text-primary);
}

.user-info span {
  font-size: 12px;
  color: #34C759;
}

/* Main Content */
.main-content {
  display: flex;
  flex-direction: column;
  height: calc(100vh - 36px);
  background:
    linear-gradient(180deg, rgba(255, 255, 255, 0.72), rgba(255, 255, 255, 0.66)),
    var(--bg-main-soft);
  border-radius: 32px;
  border: 1px solid rgba(255, 255, 255, 0.6);
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.7), 0 20px 44px var(--shadow-glass);
  overflow-y: auto;
}

/* Header */
.header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  padding: 18px 28px 16px;
  background: rgba(255, 255, 255, 0.62);
  backdrop-filter: blur(16px);
  border-bottom: 1px solid rgba(53, 62, 72, 0.05);
  position: sticky;
  top: 0;
  z-index: 10;
  min-height: 84px;
}

.header.collapsed {
  justify-content: flex-end;
  align-items: center;
  min-height: auto;
  padding: 10px 18px 0;
  background: transparent;
  backdrop-filter: none;
  border-bottom: none;
  box-shadow: none;
}

.header-left {
  display: grid;
  gap: 0;
  flex: 1;
  min-width: 0;
}

.header-left h2 {
  margin: 0;
  font-family: var(--font-heading);
  font-size: 24px;
  font-weight: 700;
  letter-spacing: -0.045em;
  line-height: 1.08;
  color: var(--text-primary);
}

.header-left p {
  margin: 8px 0 0;
  font-size: 13px;
  color: var(--text-muted);
}

.header-toggle {
  width: 46px;
  height: 46px;
  padding: 0;
  border: 1px solid rgba(53, 62, 72, 0.08);
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.72);
  color: var(--text-secondary);
  cursor: pointer;
  transition: all 0.2s ease;
  flex-shrink: 0;
  align-self: flex-start;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  backdrop-filter: blur(14px);
  box-shadow: 0 10px 24px rgba(15, 23, 42, 0.08);
}

.header-toggle:hover {
  background: rgba(255, 255, 255, 0.92);
  color: var(--text-primary);
}

.header-toggle.collapsed {
  background: rgba(255, 255, 255, 0.82);
}

.header-meta {
  display: flex;
  gap: 8px;
  margin-top: 14px;
  flex-wrap: wrap;
}

.meta-chip {
  display: inline-flex;
  align-items: center;
  padding: 7px 12px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.82);
  border: 1px solid rgba(53, 62, 72, 0.06);
  color: var(--text-primary);
  font-size: 12px;
  font-weight: 600;
  letter-spacing: -0.01em;
}

.meta-chip.subtle {
  color: var(--text-secondary);
  background: rgba(255, 255, 255, 0.55);
}

.header-right {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 10px 12px;
  border-radius: 22px;
  background: rgba(255, 255, 255, 0.5);
  border: 1px solid rgba(53, 62, 72, 0.05);
}

.workspace-field {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.workspace-field span {
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: var(--text-muted);
}

.workspace-field input {
  width: 280px;
  padding: 12px 14px;
  border: 1px solid rgba(53, 62, 72, 0.08);
  border-radius: 16px;
  background: rgba(255, 255, 255, 0.82);
  font-size: 13px;
  transition: all 0.2s ease;
}

.workspace-field input[readonly] {
  cursor: default;
}

.workspace-field input:focus {
  outline: none;
  border-color: var(--accent-orange);
  box-shadow: 0 0 0 3px var(--accent-orange-subtle);
}

.header-btn {
  padding: 12px 20px;
  border: none;
  border-radius: 999px;
  background: linear-gradient(135deg, var(--accent-orange), #e78137);
  color: white;
  font-weight: 600;
  font-size: 13px;
  cursor: pointer;
  transition: all 0.2s ease;
}

.header-btn:hover {
  background: #EA580C;
}

.header-btn:disabled {
  opacity: 0.6;
  cursor: wait;
}

/* Chat Container */
.chat-container {
  --send-btn-width: 118px;
  flex: 1;
  padding: 28px 72px 24px 72px;
  display: flex;
  flex-direction: column;
  gap: 18px;
  max-width: none;
  margin: 0;
  width: auto;
  position: relative;
}

.chat-container::before {
  content: "";
  position: absolute;
  top: 24px;
  bottom: 24px;
  left: 92px;
  width: 1px;
  background: linear-gradient(180deg, rgba(53, 62, 72, 0.04), rgba(53, 62, 72, 0.08), rgba(53, 62, 72, 0.03));
  pointer-events: none;
}

/* Message Row */
.message-row {
  display: flex;
  gap: 14px;
  max-width: min(880px, 92%);
  width: auto;
  position: relative;
  z-index: 1;
}

.message-row.user {
  flex-direction: row-reverse;
  margin-left: auto;
  margin-right: calc(var(--send-btn-width) - 22px);
  margin-top: 4px;
  max-width: min(600px, calc(100% - 108px));
}

.message-row.assistant {
  margin-right: auto;
  margin-left: 0;
  max-width: min(920px, calc(100% - var(--send-btn-width) - 24px));
}

.avatar {
  width: 42px;
  height: 42px;
  border-radius: 16px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.avatar.assistant {
  background: rgba(255, 255, 255, 0.92);
  color: var(--ink);
  border: 1px solid rgba(53, 62, 72, 0.06);
}

.message-bubble {
  padding: 14px 16px;
  border-radius: 22px;
  background: var(--bg-card);
  border: 1px solid rgba(53, 62, 72, 0.06);
  box-shadow: 0 16px 30px rgba(15, 23, 42, 0.06);
  max-width: 100%;
  width: fit-content;
  min-width: 0;
  word-break: break-word;
  overflow-wrap: break-word;
}

.message-row.user .message-bubble {
  background: linear-gradient(180deg, #fff7ef 0%, #fff1e3 100%);
  border-color: rgba(218, 106, 30, 0.1);
  border-top-right-radius: 10px;
  border-radius: 22px 12px 22px 22px;
  padding: 10px 16px;
  box-shadow: 0 12px 24px rgba(218, 106, 30, 0.08);
}

.message-row.assistant .message-bubble {
  background: rgba(255, 255, 255, 0.88);
  border-top-left-radius: 12px;
  min-width: min(560px, calc(100vw - 220px));
}

.message-meta {
  display: flex;
  justify-content: flex-start;
  gap: 8px;
  align-items: center;
  margin-bottom: 8px;
  padding-bottom: 8px;
  border-bottom: 1px solid rgba(53, 62, 72, 0.05);
}

.role-label {
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: var(--text-secondary);
  font-weight: 700;
}

.elapsed {
  font-size: 12px;
  color: var(--text-muted);
  margin-left: auto;
}

/* Markdown Styles */
.markdown-body {
  color: var(--ink);
  line-height: 1.75;
  font-size: 14px;
}

.markdown-body :deep(p) {
  margin: 0 0 10px;
}

.markdown-body :deep(h1),
.markdown-body :deep(h2),
.markdown-body :deep(h3) {
  margin: 0 0 12px;
  font-family: var(--font-heading);
  letter-spacing: -0.02em;
  color: var(--text-primary);
}

.markdown-body :deep(p:last-child) {
  margin-bottom: 0;
}

.message-row.user .markdown-body {
  font-size: 15px;
  line-height: 1.4;
}

.message-row.user .markdown-body :deep(p) {
  margin: 0;
}

.markdown-body :deep(ul),
.markdown-body :deep(ol) {
  margin: 0 0 12px 20px;
  padding: 0;
}

.markdown-body :deep(code) {
  padding: 3px 7px;
  border-radius: 8px;
  background: rgba(31, 41, 55, 0.06);
  font-family: var(--font-mono);
  font-size: 0.92em;
}

.markdown-body :deep(pre) {
  margin: 0 0 12px;
  padding: 14px;
  border-radius: 16px;
  overflow: auto;
  background: #1b2430;
  color: white;
  border: 1px solid rgba(255, 255, 255, 0.06);
}

.markdown-body :deep(pre code) {
  padding: 0;
  background: transparent;
  color: inherit;
}

.markdown-body :deep(a) {
  color: var(--accent);
}

/* Thinking Block */
.thinking-block {
  margin: 8px 0;
  border: 1px solid rgba(139, 92, 246, 0.2);
  border-radius: 18px;
  background: linear-gradient(135deg, rgba(139, 92, 246, 0.04), rgba(99, 102, 241, 0.02));
  overflow: hidden;
}

.thinking-summary {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 12px 16px;
  cursor: pointer;
  list-style: none;
  background: rgba(139, 92, 246, 0.06);
  user-select: none;
}

.thinking-summary::-webkit-details-marker {
  display: none;
}

.thinking-label {
  font-weight: 700;
  font-size: 13px;
  color: #7c3aed;
}

.thinking-summary::after {
  content: "▸";
  margin-left: auto;
  font-size: 12px;
  color: #7c3aed;
  transition: transform 0.2s ease;
}

.thinking-block[open] .thinking-summary::after {
  transform: rotate(90deg);
}

.thinking-block[open] .thinking-summary {
  border-bottom: 1px solid rgba(139, 92, 246, 0.1);
}

.thinking-content {
  padding: 14px 16px;
  border-left: 3px solid rgba(139, 92, 246, 0.18);
}

/* Tool Events */
.tool-events {
  display: grid;
  gap: 10px;
  margin-top: 14px;
  padding-top: 6px;
}

.tool-event {
  margin: 8px 0;
  border: 1px solid var(--border-light);
  border-radius: 18px;
  background: rgba(255, 255, 255, 0.82);
  overflow: hidden;
}

.tool-event-summary {
  display: flex;
  justify-content: flex-start;
  align-items: center;
  gap: 12px;
  padding: 14px 16px;
  cursor: pointer;
  list-style: none;
  background: rgba(248, 250, 252, 0.72);
}

.tool-event-summary::-webkit-details-marker {
  display: none;
}

.tool-event-name {
  font-weight: 700;
  font-size: 13px;
  color: var(--text-primary);
}

.tool-event-status {
  border-radius: 999px;
  padding: 4px 10px;
  font-size: 11px;
  font-weight: 600;
}

.tool-event-status.completed {
  background: rgba(34, 197, 94, 0.12);
  color: #15803d;
}

.tool-event-status.running {
  background: rgba(59, 130, 246, 0.14);
  color: #1d4ed8;
}

.tool-event-status.failed,
.tool-event-status.denied {
  background: rgba(239, 68, 68, 0.12);
  color: #b91c1c;
}

.tool-event-status.awaiting_approval {
  background: rgba(245, 158, 11, 0.16);
  color: #b45309;
}

.tool-event-body {
  display: grid;
  gap: 12px;
  padding: 0 16px 16px;
  border-top: 1px solid rgba(53, 62, 72, 0.05);
}

.tool-event-block {
  display: grid;
  gap: 6px;
}

.tool-event-block pre {
  margin: 0;
  padding: 12px 14px;
  border-radius: 14px;
  overflow: auto;
  background: var(--ink);
  color: #f8fafc;
  font-family: var(--font-mono);
  font-size: 12px;
  line-height: 1.55;
}

/* Approval Banner */
.approval-slide-enter-active,
.approval-slide-leave-active {
  transition: all 0.35s cubic-bezier(0.34, 1.56, 0.64, 1);
}

.approval-slide-enter-from,
.approval-slide-leave-to {
  opacity: 0;
  transform: translateY(16px);
}

.approval-banner {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 20px;
  padding: 18px 24px;
  margin: 0 34px 16px 128px;
  border-radius: 22px;
  background: linear-gradient(135deg, rgba(255, 251, 235, 0.95), rgba(255, 247, 237, 0.95));
  border: 1px solid rgba(218, 106, 30, 0.18);
  box-shadow: 0 16px 40px rgba(180, 131, 32, 0.1), inset 0 1px 0 rgba(255, 255, 255, 0.6);
  backdrop-filter: blur(16px);
  max-width: min(800px, calc(100% - 162px));
  position: relative;
  z-index: 10;
}

.approval-banner::before {
  content: "";
  position: absolute;
  left: 0;
  top: 16px;
  bottom: 16px;
  width: 4px;
  border-radius: 0 4px 4px 0;
  background: linear-gradient(180deg, var(--accent-orange), #ee8a3a);
}

.approval-content {
  display: flex;
  align-items: flex-start;
  gap: 14px;
  min-width: 0;
}

.approval-icon {
  width: 40px;
  height: 40px;
  border-radius: 14px;
  background: linear-gradient(135deg, var(--accent-orange), #ee8a3a);
  color: white;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  box-shadow: 0 8px 20px rgba(218, 106, 30, 0.22);
}

.approval-content h3,
.approval-content p {
  margin: 0;
}

.approval-content h3 {
  margin-top: 2px;
  margin-bottom: 6px;
  font-family: var(--font-heading);
  font-size: 16px;
  font-weight: 700;
  color: var(--text-primary);
}

.approval-content p {
  font-size: 13px;
  color: var(--text-secondary);
  line-height: 1.5;
}

.approval-content code {
  display: inline-block;
  margin-top: 8px;
  padding: 6px 12px;
  border-radius: 10px;
  background: rgba(28, 36, 48, 0.05);
  font-family: var(--font-mono);
  font-size: 12px;
  color: var(--ink-light);
}

.approval-actions {
  display: flex;
  gap: 10px;
  align-items: center;
  flex-shrink: 0;
}

.approval-actions button {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 11px 20px;
  border: none;
  border-radius: 14px;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s ease;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.06);
}

.approval-actions button:first-child {
  background: linear-gradient(135deg, var(--accent-orange), #ee8a3a);
  color: white;
}

.approval-actions button:first-child:hover {
  background: #EA580C;
  transform: translateY(-1px);
  box-shadow: 0 8px 20px rgba(218, 106, 30, 0.2);
}

.approval-actions button.secondary {
  background: rgba(28, 36, 48, 0.06);
  color: var(--ink);
}

.approval-actions button.secondary:hover {
  background: rgba(28, 36, 48, 0.12);
}

.approval-actions button:disabled {
  opacity: 0.5;
  cursor: not-allowed;
  transform: none;
  box-shadow: none;
}

/* Composer */
.composer-wrapper {
  display: flex;
  gap: 16px;
  padding: 20px 34px 30px;
  padding-left: 128px;
  background: linear-gradient(180deg, rgba(243, 240, 234, 0.12), rgba(255, 255, 255, 0.68));
  border-top: 1px solid rgba(53, 62, 72, 0.05);
  position: sticky;
  bottom: 0;
  z-index: 10;
  backdrop-filter: blur(18px);
}

.composer {
  flex: 1;
  position: relative;
  padding: 10px;
  border-radius: 28px;
  background: rgba(255, 255, 255, 0.74);
  border: 1px solid rgba(255, 255, 255, 0.7);
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.65), 0 14px 30px rgba(15, 23, 42, 0.05);
  max-width: 980px;
}

.composer textarea {
  width: 100%;
  resize: none;
  padding: 14px 16px;
  border-radius: 20px;
  border: 1px solid transparent;
  background: rgba(255, 255, 255, 0.84);
  font-family: var(--font-body);
  font-size: 14px;
  line-height: 1.6;
  transition: all 0.2s ease;
  min-height: 52px;
  max-height: 160px;
  overflow-y: hidden;
}

.composer textarea:focus {
  outline: none;
  border-color: var(--accent-orange);
  box-shadow: 0 0 0 4px var(--accent-orange-subtle);
}

.send-btn {
  display: flex;
  align-items: center;
  gap: 8px;
  width: var(--send-btn-width);
  padding: 15px 28px;
  border: none;
  border-radius: 999px;
  background: linear-gradient(135deg, var(--accent-orange), #e78137);
  color: white;
  font-weight: 600;
  font-size: 14px;
  cursor: pointer;
  transition: all 0.2s ease;
  align-self: flex-end;
  justify-content: center;
  box-shadow: 0 12px 24px rgba(218, 106, 30, 0.2);
}

.send-btn:hover {
  background: #EA580C;
  transform: translateY(-1px);
}

.stop-btn {
  background: linear-gradient(135deg, #b33a24, #cc4a2f);
  box-shadow: 0 12px 24px rgba(179, 58, 36, 0.22);
}

.stop-btn:hover {
  background: #a5321f;
}

.send-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
  transform: none;
}

/* Overlay */
.overlay {
  position: fixed;
  inset: 0;
  background: rgba(28, 36, 48, 0.36);
  backdrop-filter: blur(14px);
  padding: 24px;
  overflow: auto;
  z-index: 100;
}

.overlay-panel {
  max-width: 1040px;
  margin: 32px auto;
}

/* Eyebrow style */
.eyebrow {
  text-transform: uppercase;
  letter-spacing: 0.12em;
  font-size: 11px;
  color: var(--accent-orange);
  font-weight: 600;
  margin: 0 0 4px;
}

/* Scrollbar */
::-webkit-scrollbar {
  width: 8px;
}

::-webkit-scrollbar-track {
  background: transparent;
}

::-webkit-scrollbar-thumb {
  background: var(--border-default);
  border-radius: 4px;
}

::-webkit-scrollbar-thumb:hover {
  background: var(--text-muted);
}

/* Responsive */
@media (max-width: 1024px) {
  .app-shell {
    grid-template-columns: 1fr;
    padding: 0;
    gap: 0;
  }

  .sidebar {
    display: none;
  }

  .main-content {
    height: 100vh;
    border-radius: 0;
    border: none;
  }

  .chat-container {
    padding: 24px 24px;
    margin: 0 auto;
  }

  .chat-container::before {
    display: none;
  }

  .message-row.assistant {
    margin-left: 0;
    max-width: 100%;
  }

  .message-row.user {
    margin-right: 0;
    max-width: 100%;
  }

  .composer-wrapper {
    padding: 16px 24px 24px;
  }

  .approval-banner {
    margin: 0 24px 12px;
    max-width: none;
    flex-direction: column;
    align-items: stretch;
    gap: 16px;
  }

  .approval-actions {
    justify-content: flex-end;
  }

  .header {
    flex-direction: column;
    gap: 16px;
    align-items: flex-start;
    padding: 16px 24px;
  }

  .header-left h2 {
    font-size: 24px;
  }

  .header-right {
    width: 100%;
    flex-direction: column;
    align-items: stretch;
    padding: 0;
    background: transparent;
    border: none;
  }

  .workspace-field input {
    width: 100%;
  }

  .message-row {
    max-width: 100%;
  }

  .message-row.assistant .message-bubble {
    min-width: 0;
  }
}

@media (max-width: 680px) {
  .header {
    padding: 16px 18px 14px;
  }

  .header-left h2 {
    font-size: 22px;
  }

  .header-toggle {
    padding: 8px 12px;
  }

  .header.collapsed {
    padding: 10px 14px 0;
  }

  .header-meta {
    margin-top: 10px;
  }

  .chat-container {
    padding: 18px 16px 16px;
    gap: 14px;
  }

  .message-row {
    gap: 10px;
  }

  .avatar {
    width: 36px;
    height: 36px;
    border-radius: 14px;
  }

  .message-bubble {
    padding: 14px 14px;
    border-radius: 18px;
  }

  .message-meta {
    margin-bottom: 8px;
    padding-bottom: 8px;
  }

  .composer-wrapper {
    padding: 14px 16px 18px;
    flex-direction: column;
  }

  .composer {
    padding: 8px;
    border-radius: 22px;
  }

  .composer textarea {
    min-height: 48px;
    padding: 13px 14px;
  }

  .send-btn {
    width: 100%;
    align-self: stretch;
  }

  .approval-panel {
    flex-direction: column;
    gap: 14px;
  }
}
</style>
