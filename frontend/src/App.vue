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
          <button class="tab-item" @click="quizHistoryOpen = true">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M13 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9z"/>
              <polyline points="13 2 13 9 20 9"/>
            </svg>
            <span>文件</span>
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
      <header class="header">
        <div class="header-left">
          <h2>{{ activeConversation.title }}</h2>
          <p>继续之前的对话或开始新对话</p>
        </div>
        <div class="header-right">
          <div class="workspace-field">
            <span>工作目录</span>
            <input
              v-model="activeConversation.workspaceRoot"
              type="text"
              placeholder="/path/to/your/project"
            />
          </div>
          <button class="header-btn" :disabled="loading" @click="loadCourses">
            加载课程
          </button>
        </div>
      </header>

      <!-- Chat Container -->
      <div class="chat-container">
        <article
          v-for="message in activeConversation.messages"
          :key="message.id"
          :class="['message-row', message.role]"
        >
          <div :class="['avatar', message.role]">
            <svg v-if="message.role === 'user'" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/>
              <circle cx="12" cy="7" r="4"/>
            </svg>
            <svg v-else width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M12 2L2 7l10 5 10-5-10-5z"/>
              <path d="M2 17l10 5 10-5"/>
              <path d="M2 12l10 5 10-5"/>
            </svg>
          </div>
          <div :class="['message-bubble', message.role]">
            <div class="message-meta">
              <span class="role-label">{{ message.role === 'user' ? '你' : 'AI' }}</span>
              <span v-if="message.elapsedLabel" class="elapsed">{{ message.elapsedLabel }}</span>
            </div>
            <div
              class="markdown-body"
              v-html="renderMarkdown(message.content)"
            />
            <!-- Tool Events -->
            <div v-if="message.toolEvents?.length" class="tool-events">
              <details
                v-for="(toolEvent, index) in message.toolEvents"
                :key="`${message.id}-${toolEvent.tool_name}-${index}`"
                class="tool-event"
              >
                <summary class="tool-event-summary">
                  <span class="tool-event-name">{{ toolEvent.tool_name }}</span>
                  <span :class="['tool-event-status', toolEvent.status]">{{ formatToolStatus(toolEvent.status) }}</span>
                </summary>
                <div class="tool-event-body">
                  <div class="tool-event-block">
                    <strong>输入</strong>
                    <pre>{{ formatToolPayload(toolEvent.arguments) }}</pre>
                  </div>
                  <div v-if="toolEvent.output" class="tool-event-block">
                    <strong>输出</strong>
                    <pre>{{ formatToolPayload(toolEvent.output) }}</pre>
                  </div>
                </div>
              </details>
            </div>
            <!-- Quiz Panel -->
            <template
              v-for="(toolEvent, index) in message.toolEvents?.filter((event) => event.tool_name === 'create_quiz') || []"
              :key="`${message.id}-quiz-${index}`"
            >
              <QuizPanel
                v-if="tryParseToolOutput(toolEvent.output)?.quiz_session"
                :quiz="tryParseToolOutput(toolEvent.output).quiz_session"
              />
            </template>
          </div>
        </article>

        <!-- Approval Panel -->
        <section v-if="activeConversation.pendingApproval" class="approval-panel">
          <div class="approval-content">
            <p class="eyebrow">需要审批</p>
            <h3>{{ activeConversation.pendingApproval.tool_name }}</h3>
            <p>{{ activeConversation.pendingApproval.summary }}</p>
            <code v-if="activeConversation.pendingApproval.workspace_root">
              {{ activeConversation.pendingApproval.workspace_root }}
            </code>
          </div>
          <div class="approval-actions">
            <button :disabled="loading" @click="resolveApproval(true)">批准</button>
            <button class="secondary" :disabled="loading" @click="resolveApproval(false)">拒绝</button>
          </div>
        </section>
      </div>

      <!-- Composer -->
      <div class="composer-wrapper">
        <div class="composer">
          <textarea
            v-model="draft"
            rows="4"
            placeholder="输入消息... (Shift + Enter 换行)"
            @keydown.enter.exact.prevent="submitMessage"
          />
          <p class="composer-hint">Shift + Enter 换行，Enter 发送</p>
        </div>
        <button
          class="send-btn"
          :disabled="loading || !draft.trim()"
          @click="submitMessage"
        >
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <line x1="22" y1="2" x2="11" y2="13"/>
            <polygon points="22 2 15 22 11 13 2 9 22 2"/>
          </svg>
          <span>{{ loading ? '发送中...' : '发送' }}</span>
        </button>
      </div>
      </template>

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
import { computed, nextTick, onBeforeUnmount, reactive, ref, watch } from "vue";
import CalendarPanel from "./components/CalendarPanel.vue";
import QuizPanel from "./components/QuizPanel.vue";
import DatabaseOverviewPanel from "./components/DatabaseOverviewPanel.vue";
import QuizHistoryPanel from "./components/QuizHistoryPanel.vue";
import SettingsPanel from "./components/SettingsPanel.vue";
import { getCourses, getHealth, streamApprovalDecision, streamChat } from "./api/client";

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
        content: "你好！我是 StudyAI 助手，可以帮助你查询课程、搜索文件、管理记忆等。有什么可以帮你的吗？",
        elapsedLabel: "",
        toolEvents: []
      })
    ]
  });
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
        messages: (conversation.messages || []).map((message) =>
          reactive({
            ...message,
            toolEvents: message.toolEvents || []
          })
        )
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
const loading = ref(false);
let activeTimer = null;

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
  return date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

function formatElapsed(ms) {
  if (ms < 1000) return `${ms} ms`;
  return `${(ms / 1000).toFixed(1)} s`;
}

function formatToolStatus(status) {
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
  conversation.title = firstUserMessage.content.slice(0, 20) || conversation.title;
}

function createConversation() {
  const conversation = makeConversation(`新对话 ${conversations.value.length + 1}`);
  conversations.value.unshift(conversation);
  activeConversationId.value = conversation.id;
  editingConversationId.value = "";
  draft.value = "";
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
      content,
      elapsedLabel: "",
      toolEvents: []
    })
  );
  activeConversation.value.updatedAt = Date.now();
  scrollToBottom();
}

async function loadCourses() {
  loading.value = true;
  try {
    const response = await getCourses();
    const courses = response.data?.data ?? [];
    const summary = courses.map((item) => `- ${item.name} (${item.code})`).join("\n");
    appendMessage("assistant", summary || "没有返回课程。");
  } catch (error) {
    appendMessage("assistant", `课程请求失败: ${error.message}`);
  } finally {
    loading.value = false;
  }
}

async function submitMessage() {
  const content = draft.value.trim();
  if (!content) return;

  const conversation = activeConversation.value;
  conversation.messages.push(
    reactive({
      id: crypto.randomUUID(),
      role: "user",
      content,
      elapsedLabel: ""
    })
  );
  const assistantMessage = reactive({
    id: crypto.randomUUID(),
    role: "assistant",
    content: "正在等待模型响应...",
    elapsedLabel: "",
    toolEvents: []
  });
  conversation.messages.push(assistantMessage);
  conversation.updatedAt = Date.now();
  conversation.pendingApproval = null;
  updateConversationTitle(conversation);
  draft.value = "";
  loading.value = true;
  const stopTimer = startTimer(assistantMessage);
  scrollToBottom();

  try {
    await streamChat(
      {
        message: content,
        session_id: conversation.id,
        workspace_root: conversation.workspaceRoot?.trim() || null
      },
      {
        onChunk(chunk) {
          if (assistantMessage.content === "正在等待模型响应...") {
            assistantMessage.content = "";
          }
          assistantMessage.content += chunk;
          scrollToBottom();
        },
        onApprovalRequired(approval) {
          assistantMessage.content = "工具调用正在等待你的审批。";
          assistantMessage.toolEvents = approval.tool_events || [];
          conversation.pendingApproval = approval;
          scrollToBottom();
        },
        onDone(payload) {
          assistantMessage.content = assistantMessage.content.trim();
          assistantMessage.toolEvents = payload.tool_events || assistantMessage.toolEvents || [];
          scrollToBottom();
        }
      }
    );
  } catch (error) {
    assistantMessage.content = `聊天失败: ${error.message}`;
  } finally {
    conversation.updatedAt = Date.now();
    stopTimer();
    loading.value = false;
  }
}

async function resolveApproval(approved) {
  const conversation = activeConversation.value;
  const pending = conversation.pendingApproval;
  if (!pending) return;

  const assistantMessage = reactive({
    id: crypto.randomUUID(),
    role: "assistant",
    content: approved ? "正在执行批准的操作..." : "审批被拒绝。让智能体继续...",
    elapsedLabel: "",
    toolEvents: []
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
        onChunk(chunk) {
          if (
            assistantMessage.content === "正在执行批准的操作..." ||
            assistantMessage.content === "审批被拒绝。让智能体继续..."
          ) {
            assistantMessage.content = "";
          }
          assistantMessage.content += chunk;
          scrollToBottom();
        },
        onApprovalRequired(nextApproval) {
          assistantMessage.content = "另一个操作正在等待你的审批。";
          assistantMessage.toolEvents = nextApproval.tool_events || [];
          conversation.pendingApproval = nextApproval;
          scrollToBottom();
        },
        onDone(payload) {
          assistantMessage.content = assistantMessage.content.trim();
          assistantMessage.toolEvents = payload.tool_events || assistantMessage.toolEvents || [];
          scrollToBottom();
        }
      }
    );
  } catch (error) {
    assistantMessage.content = `审批流程失败: ${error.message}`;
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
});
</script>

<style>
/* Design System Variables */
:root {
  color-scheme: light;
  /* Colors from Pencil */
  --bg-main: #F5F5F7;
  --bg-card: rgba(255, 255, 255, 0.72);
  --bg-sidebar: rgba(240, 240, 243, 0.8);
  --bg-hover: rgba(0, 0, 0, 0.04);
  --accent: #1f6f78;
  --accent-light: #2a8f9a;
  --accent-orange: #F97316;
  --accent-orange-light: #FFF7ED;
  --accent-orange-subtle: #FFEDD5;
  --ink: #1c2430;
  --ink-light: #54606e;
  --text-primary: #1D1D1F;
  --text-secondary: #86868B;
  --text-muted: #A1A1A6;
  --text-placeholder: #A1A1A6;
  --border-default: #E5E7EB;
  --border-light: rgba(0, 0, 0, 0.08);
  --border-subtle: #F0F0F3;
  /* Shadows */
  --shadow-glass: #0000000D;
  --shadow-subtle: #00000008;
  --shadow-sm: #00000010;
  --shadow-md: #00000014;
  --shadow-elevated: #0000001A;
  --shadow-float: #00000029;
  /* Radii */
  --radius-sm: 10px;
  --radius-md: 14px;
  --radius-lg: 20px;
  --radius-xl: 24px;
  --radius-2xl: 28px;
  /* Fonts */
  --font-heading: "Space Grotesk", -apple-system, sans-serif;
  --font-body: "IBM Plex Sans", -apple-system, sans-serif;
  --font-mono: "IBM Plex Mono", monospace;
}

* {
  box-sizing: border-box;
}

body {
  margin: 0;
  font-family: var(--font-body);
  background: var(--bg-main);
  color: var(--ink);
  -webkit-font-smoothing: antialiased;
}

/* App Shell Layout */
.app-shell {
  display: grid;
  grid-template-columns: 280px 1fr;
  height: 100vh;
  overflow: hidden;
}

/* Sidebar */
.sidebar {
  position: sticky;
  top: 0;
  height: 100vh;
  background: var(--bg-sidebar);
  backdrop-filter: blur(20px);
  border-right: 1px solid var(--border-subtle);
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.sidebar-top {
  display: flex;
  flex-direction: column;
  height: 100%;
  padding: 20px 16px;
  gap: 20px;
}

/* Logo Area */
.logo-area {
  display: flex;
  align-items: center;
  gap: 10px;
  padding-bottom: 16px;
}

.logo-icon {
  width: 36px;
  height: 36px;
  border-radius: 14px;
  background: var(--accent-orange);
  display: flex;
  align-items: center;
  justify-content: center;
  color: white;
}

.logo-text {
  font-size: 18px;
  font-weight: 700;
  color: var(--text-primary);
}

/* Tab Navigation */
.tab-nav {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.tab-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 14px 18px;
  border: none;
  border-radius: 16px;
  background: transparent;
  color: var(--text-secondary);
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s ease;
}

.tab-item:hover {
  background: var(--bg-hover);
  color: var(--text-primary);
}

.tab-item.active {
  background: var(--accent-orange-subtle);
  color: var(--accent-orange);
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
  font-weight: 600;
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
  width: 28px;
  height: 28px;
  border: none;
  border-radius: 8px;
  background: var(--accent-orange);
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
  gap: 4px;
  overflow-y: auto;
}

.conv-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 12px;
  border-radius: 10px;
  cursor: pointer;
  transition: all 0.15s ease;
}

.conv-item:hover {
  background: var(--bg-card);
}

.conv-item.active {
  background: var(--accent-orange-subtle);
}

.conv-info {
  flex: 1;
  min-width: 0;
}

.conv-info strong {
  display: block;
  font-size: 13px;
  color: var(--text-primary);
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
  border-radius: 8px;
  background: var(--bg-hover);
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
  padding: 12px 16px;
  background: var(--bg-card);
  border-radius: 24px;
  box-shadow: 0 2px 4px var(--shadow-subtle);
}

.user-avatar {
  width: 40px;
  height: 40px;
  border-radius: 50%;
  background: var(--accent-orange);
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
  height: 100vh;
  background: var(--bg-main);
  overflow-y: auto;
}

/* Header */
.header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 32px;
  background: rgba(255, 255, 255, 0.92);
  backdrop-filter: blur(12px);
  border-bottom: 1px solid var(--border-subtle);
  position: sticky;
  top: 0;
  z-index: 10;
}

.header-left h2 {
  margin: 0;
  font-family: var(--font-heading);
  font-size: 18px;
  color: var(--text-primary);
}

.header-left p {
  margin: 4px 0 0;
  font-size: 13px;
  color: var(--text-muted);
}

.header-right {
  display: flex;
  align-items: center;
  gap: 16px;
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
  padding: 10px 14px;
  border: 1px solid var(--border-light);
  border-radius: var(--radius-md);
  background: white;
  font-size: 13px;
  transition: all 0.2s ease;
}

.workspace-field input:focus {
  outline: none;
  border-color: var(--accent-orange);
  box-shadow: 0 0 0 3px var(--accent-orange-subtle);
}

.header-btn {
  padding: 10px 20px;
  border: none;
  border-radius: 999px;
  background: var(--accent-orange);
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
  padding: 20px 64px 20px 80px;
  display: flex;
  flex-direction: column;
  gap: 16px;
  max-width: none;
  margin: 0;
  width: auto;
}

/* Message Row */
.message-row {
  display: flex;
  gap: 16px;
  max-width: 95%;
  width: auto;
}

.message-row.user {
  flex-direction: row-reverse;
  margin-left: auto;
  margin-right: calc(var(--send-btn-width) + 16px - 60px);
}

.message-row.assistant {
  margin-right: auto;
  margin-left: -60px;
  max-width: calc(100% + 60px - var(--send-btn-width) - 16px);
}

.avatar {
  width: 44px;
  height: 44px;
  border-radius: 22px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.avatar.user {
  background: var(--accent-orange);
  color: white;
}

.avatar.assistant {
  background: var(--bg-hover);
  color: var(--ink);
}

.message-bubble {
  padding: 16px 20px;
  border-radius: 20px;
  background: var(--bg-card);
  box-shadow: 0 4px 16px var(--shadow-elevated);
  max-width: 100%;
  width: fit-content;
  min-width: 0;
}

.message-row.user .message-bubble {
  background: var(--accent-orange-light);
}

.message-row.assistant .message-bubble {
  background: white;
}

.message-meta {
  display: flex;
  justify-content: flex-start;
  gap: 8px;
  align-items: center;
  margin-bottom: 8px;
}

.role-label {
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: var(--text-muted);
}

.elapsed {
  font-size: 12px;
  color: var(--text-muted);
}

/* Markdown Styles */
.markdown-body {
  color: var(--ink);
  line-height: 1.65;
  font-size: 14px;
}

.markdown-body :deep(p) {
  margin: 0 0 12px;
}

.markdown-body :deep(p:last-child) {
  margin-bottom: 0;
}

.markdown-body :deep(ul),
.markdown-body :deep(ol) {
  margin: 0 0 12px 20px;
  padding: 0;
}

.markdown-body :deep(code) {
  padding: 2px 6px;
  border-radius: 8px;
  background: var(--bg-hover);
  font-family: var(--font-mono);
  font-size: 0.92em;
}

.markdown-body :deep(pre) {
  margin: 0 0 12px;
  padding: 14px;
  border-radius: 16px;
  overflow: auto;
  background: var(--ink);
  color: white;
}

.markdown-body :deep(pre code) {
  padding: 0;
  background: transparent;
  color: inherit;
}

.markdown-body :deep(a) {
  color: var(--accent);
}

/* Tool Events */
.tool-events {
  display: grid;
  gap: 10px;
  margin-top: 14px;
}

.tool-event {
  border: 1px solid var(--border-light);
  border-radius: 16px;
  background: white;
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
}

.tool-event-summary::-webkit-details-marker {
  display: none;
}

.tool-event-name {
  font-weight: 700;
  font-size: 13px;
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

/* Approval Panel */
.approval-panel {
  display: flex;
  justify-content: space-between;
  gap: 24px;
  padding: 20px 24px;
  margin: 16px 0;
  border-radius: 20px;
  background: #fff5db;
  border: 1px solid #f2d48a;
  max-width: 800px;
  margin-left: 60px;
}

.approval-content h3,
.approval-content p {
  margin: 0;
}

.approval-content h3 {
  margin-top: 4px;
  margin-bottom: 8px;
  font-size: 16px;
}

.approval-content code {
  display: inline-block;
  margin-top: 8px;
  padding: 6px 10px;
  border-radius: 10px;
  background: rgba(28, 36, 48, 0.08);
  font-family: var(--font-mono);
  font-size: 12px;
}

.approval-actions {
  display: flex;
  gap: 10px;
  align-items: center;
}

.approval-actions button {
  padding: 10px 20px;
  border: none;
  border-radius: 999px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s ease;
}

.approval-actions button:first-child {
  background: var(--accent-orange);
  color: white;
}

.approval-actions button.secondary {
  background: rgba(28, 36, 48, 0.12);
  color: var(--ink);
}

.approval-actions button:disabled {
  opacity: 0.6;
  cursor: wait;
}

/* Composer */
.composer-wrapper {
  display: flex;
  gap: 16px;
  padding: 20px 64px 32px 80px;
  background: var(--bg-card);
  border-top: 1px solid var(--border-subtle);
  position: sticky;
  bottom: 0;
  z-index: 10;
}

.composer {
  flex: 1;
  position: relative;
}

.composer textarea {
  width: 100%;
  resize: vertical;
  padding: 16px 20px;
  border-radius: 24px;
  border: 1px solid var(--border-light);
  background: white;
  font-family: var(--font-body);
  font-size: 14px;
  line-height: 1.5;
  transition: all 0.2s ease;
}

.composer textarea:focus {
  outline: none;
  border-color: var(--accent-orange);
  box-shadow: 0 0 0 4px var(--accent-orange-subtle);
}

.composer-hint {
  position: absolute;
  bottom: -20px;
  left: 20px;
  font-size: 11px;
  color: var(--text-placeholder);
  margin: 0;
}

.send-btn {
  display: flex;
  align-items: center;
  gap: 8px;
  width: var(--send-btn-width);
  padding: 16px 28px;
  border: none;
  border-radius: 999px;
  background: var(--accent-orange);
  color: white;
  font-weight: 600;
  font-size: 14px;
  cursor: pointer;
  transition: all 0.2s ease;
  align-self: flex-end;
  justify-content: center;
}

.send-btn:hover {
  background: #EA580C;
  transform: translateY(-1px);
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
  background: rgba(28, 36, 48, 0.48);
  backdrop-filter: blur(8px);
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
  }

  .sidebar {
    display: none;
  }

  .chat-container {
    padding: 24px 24px;
    margin: 0 auto;
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

  .header {
    flex-direction: column;
    gap: 16px;
    align-items: flex-start;
    padding: 16px 24px;
  }

  .header-right {
    width: 100%;
    flex-direction: column;
    align-items: stretch;
  }

  .workspace-field input {
    width: 100%;
  }
}
</style>
