<template>
  <section class="workspace">
    <aside class="sidebar">
      <div class="sidebar-head">
        <div>
          <p class="eyebrow">Conversations</p>
          <h2>Sessions</h2>
        </div>
        <button class="new-chat" @click="createConversation">New Chat</button>
      </div>

      <div class="conversation-list">
        <article
          v-for="conversation in sortedConversations"
          :key="conversation.id"
          :class="['conversation-card', { active: conversation.id === activeConversationId }]"
          @click="selectConversation(conversation.id)"
        >
          <div class="conversation-copy">
            <div class="conversation-title-row">
              <strong v-if="editingConversationId !== conversation.id">{{ conversation.title }}</strong>
              <input
                v-else
                v-model="editingTitle"
                class="rename-input"
                @click.stop
                @keydown.enter.prevent="confirmRename(conversation.id)"
                @keydown.esc.prevent="cancelRename"
              />
              <span class="updated-at">{{ formatConversationTime(conversation.updatedAt) }}</span>
            </div>
            <p>{{ previewConversation(conversation) }}</p>
          </div>
          <div class="conversation-actions">
            <button
              v-if="editingConversationId !== conversation.id"
              class="small-btn"
              title="Rename conversation"
              @click.stop="beginRename(conversation)"
            >
              Rename
            </button>
            <button
              v-else
              class="small-btn"
              title="Save title"
              @click.stop="confirmRename(conversation.id)"
            >
              Save
            </button>
            <button
              class="delete-btn"
              title="Delete conversation"
              @click.stop="deleteConversation(conversation.id)"
            >
              Delete
            </button>
          </div>
        </article>
      </div>
    </aside>

    <section class="chat-card">
      <header class="toolbar">
        <div>
          <h2>{{ activeConversation.title }}</h2>
          <p>Continue any saved session or start a new one. Responses render in Markdown.</p>
        </div>
        <div class="toolbar-actions">
          <label class="workspace-field">
            <span>Workspace Root</span>
            <input
              v-model="activeConversation.workspaceRoot"
              type="text"
              placeholder="/path/to/your/project"
            />
          </label>
          <button :disabled="loading" @click="loadCourses">Load Blackboard Courses</button>
        </div>
      </header>

      <div ref="messagesViewport" class="messages">
        <article
          v-for="message in activeConversation.messages"
          :key="message.id"
          :class="['message', message.role, { streaming: message.isStreaming }]"
        >
          <div class="meta">
            <span class="role">{{ message.role }}</span>
            <span v-if="message.elapsedLabel" class="elapsed">{{ message.elapsedLabel }}</span>
          </div>
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
                  <strong>Input</strong>
                  <pre>{{ formatToolPayload(toolEvent.arguments) }}</pre>
                </div>
                <div v-if="toolEvent.output" class="tool-event-block">
                  <strong>Output</strong>
                  <pre>{{ formatToolPayload(toolEvent.output) }}</pre>
                </div>
              </div>
            </details>
          </div>
          <details v-if="message.thinking" class="thinking-block" open>
            <summary class="thinking-summary">
              <span class="thinking-label">思考过程</span>
            </summary>
            <div class="markdown-body thinking-content" v-html="renderMarkdown(message.thinking)" />
          </details>
          <div
            v-if="message.content && message.isStreaming"
            class="streaming-body"
          >
            {{ message.content }}
          </div>
          <div
            v-else-if="message.content"
            class="markdown-body"
            v-html="renderMarkdown(message.content)"
          />
          <span v-if="message.isStreaming" class="stream-cursor" aria-hidden="true"></span>
          <template
            v-for="(toolEvent, index) in message.toolEvents?.filter((event) => event.tool_name === 'create_quiz') || []"
            :key="`${message.id}-quiz-${index}`"
          >
            <QuizPanel
              v-if="tryParseToolOutput(toolEvent.output)?.quiz_session"
              :quiz="tryParseToolOutput(toolEvent.output).quiz_session"
            />
          </template>
        </article>
      </div>

      <section v-if="activeConversation.pendingApproval" class="approval-panel">
        <div>
          <p class="eyebrow">Approval Required</p>
          <h3>{{ activeConversation.pendingApproval.tool_name }}</h3>
          <p>{{ activeConversation.pendingApproval.summary }}</p>
          <code v-if="activeConversation.pendingApproval.workspace_root">
            {{ activeConversation.pendingApproval.workspace_root }}
          </code>
        </div>
        <div class="approval-actions">
          <button :disabled="loading" @click="resolveApproval(true)">Approve</button>
          <button class="secondary" :disabled="loading" @click="resolveApproval(false)">Deny</button>
        </div>
      </section>

      <form class="composer" @submit.prevent="submitMessage">
        <textarea
          v-model="draft"
          rows="4"
          placeholder="Ask about courses, search, or saved memory..."
        />
        <div class="actions">
          <button
            v-if="chatStreaming"
            class="stop-btn"
            type="button"
            @click="stopActiveChat"
          >
            Stop
          </button>
          <button v-else :disabled="loading || !draft.trim()" type="submit">
            {{ loading ? "Streaming..." : "Send" }}
          </button>
        </div>
      </form>
    </section>
  </section>
</template>

<script setup>
import MarkdownIt from "markdown-it";
import { computed, nextTick, onBeforeUnmount, reactive, ref, watch } from "vue";
import QuizPanel from "./QuizPanel.vue";
import { getCourses, streamApprovalDecision, streamChat } from "../api/client";

const CHAT_CONVERSATIONS_KEY = "spa-conversations";
const ACTIVE_CONVERSATION_KEY = "spa-active-conversation-id";

const markdown = new MarkdownIt({
  html: false,
  breaks: true,
  linkify: true
});

function makeConversation(title = "New Conversation") {
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
        content: "UI is connected to the backend contract. Start here or continue a previous session.",
        thinking: "",
        elapsedLabel: "",
        isStreaming: false,
        toolEvents: []
      })
    ]
  });
}

function restoreConversations() {
  try {
    const raw = JSON.parse(window.localStorage.getItem(CHAT_CONVERSATIONS_KEY) || "null");
    if (!Array.isArray(raw) || raw.length === 0) {
      return [makeConversation("Welcome Chat")];
    }
    return raw.map((conversation) =>
      reactive({
        ...conversation,
        workspaceRoot: conversation.workspaceRoot || "",
        pendingApproval: conversation.pendingApproval || null,
        messages: (conversation.messages || []).map((message) =>
          reactive({
            ...message,
            isStreaming: false,
            toolEvents: message.toolEvents || []
          })
        )
      })
    );
  } catch {
    return [makeConversation("Welcome Chat")];
  }
}

const conversations = ref(restoreConversations());
const activeConversationId = ref(
  window.localStorage.getItem(ACTIVE_CONVERSATION_KEY) || conversations.value[0].id
);
const editingConversationId = ref("");
const editingTitle = ref("");
const draft = ref("Show my Blackboard courses");
const loading = ref(false);
const chatStreaming = ref(false);
const messagesViewport = ref(null);
let activeTimer = null;
let activeChatAbortController = null;
let chatStopRequested = false;

const sortedConversations = computed(() =>
  [...conversations.value].sort((left, right) => (right.updatedAt || 0) - (left.updatedAt || 0))
);

const activeConversation = computed(() => {
  const conversation =
    conversations.value.find((item) => item.id === activeConversationId.value) || conversations.value[0];
  if (!conversation) {
    const fallback = makeConversation("Recovered Chat");
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

function scrollMessagesToBottom() {
  nextTick(() => {
    const viewport = messagesViewport.value;
    if (!viewport) return;
    viewport.scrollTop = viewport.scrollHeight;
  });
}

function renderMarkdown(content) {
  return markdown.render(content || "");
}

function previewConversation(conversation) {
  const lastMessage = conversation.messages[conversation.messages.length - 1];
  return lastMessage?.content?.slice(0, 70) || "No messages yet.";
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
  if (status === "running") return "Running";
  if (status === "completed") return "Completed";
  if (status === "failed") return "Failed";
  if (status === "denied") return "Denied";
  if (status === "awaiting_approval") return "Awaiting Approval";
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
  conversation.title = firstUserMessage.content.slice(0, 32) || conversation.title;
}

function createConversation() {
  const conversation = makeConversation(`New Chat ${conversations.value.length + 1}`);
  conversations.value.unshift(conversation);
  activeConversationId.value = conversation.id;
  editingConversationId.value = "";
  draft.value = "";
  persistConversations();
}

function selectConversation(id) {
  activeConversationId.value = id;
  persistConversations();
}

function deleteConversation(id) {
  const remaining = conversations.value.filter((conversation) => conversation.id !== id);
  conversations.value = remaining.length ? remaining : [makeConversation("Welcome Chat")];
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
      isStreaming: false,
      toolEvents: []
    })
  );
  activeConversation.value.updatedAt = Date.now();
  scrollMessagesToBottom();
}

async function loadCourses() {
  loading.value = true;
  try {
    const response = await getCourses();
    const courses = response.data?.data ?? [];
    const summary = courses
      .map((item) => {
        const courseCode = item.blackboard_course_id || item.course_id || item.code;
        return `- ${item.name} (${courseCode})`;
      })
      .join("\n");
    appendMessage("assistant", summary || "No courses returned.");
  } catch (error) {
    appendMessage("assistant", `Course request failed: ${error.message}`);
  } finally {
    loading.value = false;
  }
}

async function submitMessage() {
  if (loading.value) return;

  const content = draft.value.trim();
  if (!content) return;

  const conversation = activeConversation.value;
  const waitingMessage = "Waiting for model response...";
  conversation.messages.push(
    reactive({
      id: crypto.randomUUID(),
      role: "user",
      content,
      elapsedLabel: "",
      isStreaming: false
    })
  );
  const assistantMessage = reactive({
    id: crypto.randomUUID(),
    role: "assistant",
    content: waitingMessage,
    thinking: "",
    elapsedLabel: "",
    isStreaming: true,
    toolEvents: []
  });
  conversation.messages.push(assistantMessage);
  conversation.updatedAt = Date.now();
  conversation.pendingApproval = null;
  updateConversationTitle(conversation);
  draft.value = "";
  loading.value = true;
  chatStreaming.value = true;
  chatStopRequested = false;
  activeChatAbortController = new AbortController();
  scrollMessagesToBottom();
  const stopTimer = startTimer(assistantMessage);

  try {
    await streamChat(
      {
        message: content,
        session_id: conversation.id,
        workspace_root: conversation.workspaceRoot?.trim() || null
      },
      {
        onChunk(chunk) {
          if (assistantMessage.content === waitingMessage) {
            assistantMessage.content = "";
          }
          assistantMessage.content += chunk;
          scrollMessagesToBottom();
        },
        onReasoning(chunk) {
          assistantMessage.thinking = (assistantMessage.thinking || "") + chunk;
          scrollMessagesToBottom();
        },
        onToolEvents(toolEvents) {
          assistantMessage.toolEvents = toolEvents || assistantMessage.toolEvents || [];
          scrollMessagesToBottom();
        },
        onApprovalRequired(approval) {
          assistantMessage.content = "Tool invocation is waiting for your approval.";
          assistantMessage.isStreaming = false;
          assistantMessage.toolEvents = approval.tool_events || [];
          conversation.pendingApproval = approval;
          scrollMessagesToBottom();
        },
        onDone(payload) {
          const finalContent = assistantMessage.content.trim();
          assistantMessage.content = finalContent === waitingMessage ? "" : finalContent;
          assistantMessage.thinking = (assistantMessage.thinking || "").trim();
          assistantMessage.isStreaming = false;
          assistantMessage.toolEvents = payload.tool_events || assistantMessage.toolEvents || [];
          scrollMessagesToBottom();
        }
      },
      {
        signal: activeChatAbortController.signal
      }
    );
  } catch (error) {
    const aborted = chatStopRequested || error?.name === "AbortError";
    if (aborted) {
      const partial = assistantMessage.content === waitingMessage ? "" : assistantMessage.content.trim();
      assistantMessage.content = partial ? `${partial}\n\n[Stopped generating]` : "Generation stopped.";
    } else {
      assistantMessage.content = `Chat failed: ${error.message}`;
    }
    assistantMessage.isStreaming = false;
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

  const assistantMessage = reactive({
    id: crypto.randomUUID(),
    role: "assistant",
    content: approved ? "Executing approved action..." : "Approval denied. Letting the agent continue...",
    thinking: "",
    elapsedLabel: "",
    isStreaming: true,
    toolEvents: []
  });
  conversation.messages.push(assistantMessage);
  conversation.pendingApproval = null;
  conversation.updatedAt = Date.now();
  loading.value = true;
  scrollMessagesToBottom();
  const stopTimer = startTimer(assistantMessage);

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
            assistantMessage.content === "Executing approved action..." ||
            assistantMessage.content === "Approval denied. Letting the agent continue..."
          ) {
            assistantMessage.content = "";
          }
          assistantMessage.content += chunk;
          scrollMessagesToBottom();
        },
        onReasoning(chunk) {
          assistantMessage.thinking = (assistantMessage.thinking || "") + chunk;
          scrollMessagesToBottom();
        },
        onToolEvents(toolEvents) {
          assistantMessage.toolEvents = toolEvents || assistantMessage.toolEvents || [];
          scrollMessagesToBottom();
        },
        onApprovalRequired(nextApproval) {
          assistantMessage.content = "Another action is waiting for your approval.";
          assistantMessage.isStreaming = false;
          assistantMessage.toolEvents = nextApproval.tool_events || [];
          conversation.pendingApproval = nextApproval;
          scrollMessagesToBottom();
        },
        onDone(payload) {
          assistantMessage.content = assistantMessage.content.trim();
          assistantMessage.thinking = (assistantMessage.thinking || "").trim();
          assistantMessage.isStreaming = false;
          assistantMessage.toolEvents = payload.tool_events || assistantMessage.toolEvents || [];
          scrollMessagesToBottom();
        }
      }
    );
  } catch (error) {
    assistantMessage.content = `Approval flow failed: ${error.message}`;
    assistantMessage.isStreaming = false;
  } finally {
    conversation.updatedAt = Date.now();
    stopTimer();
    loading.value = false;
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
</script>

<style scoped>
.workspace {
  max-width: 1180px;
  margin: 0 auto;
  display: grid;
  grid-template-columns: 320px minmax(0, 1fr);
  gap: 22px;
  align-items: start;
}

.sidebar,
.chat-card {
  border-radius: 28px;
  background: var(--card);
  box-shadow: 0 20px 50px rgba(28, 36, 48, 0.12);
  backdrop-filter: blur(12px);
}

.sidebar {
  padding: 22px;
  position: sticky;
  top: 24px;
}

.sidebar-head {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: start;
  margin-bottom: 18px;
}

.eyebrow {
  margin: 0 0 6px;
  text-transform: uppercase;
  letter-spacing: 0.12em;
  font-size: 0.78rem;
  color: var(--accent);
}

.sidebar-head h2 {
  margin: 0;
  font-family: "Space Grotesk", "IBM Plex Sans", sans-serif;
}

.new-chat {
  border: 0;
  border-radius: 999px;
  padding: 10px 14px;
  background: var(--accent);
  color: white;
  font-weight: 700;
  cursor: pointer;
}

.conversation-list {
  display: grid;
  gap: 10px;
}

.conversation-card {
  padding: 14px;
  border-radius: 18px;
  background: rgba(255, 255, 255, 0.72);
  border: 1px solid transparent;
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: start;
  cursor: pointer;
}

.conversation-card.active {
  border-color: rgba(31, 111, 120, 0.4);
  background: rgba(31, 111, 120, 0.1);
}

.conversation-copy strong {
  display: block;
  margin-bottom: 4px;
}

.conversation-title-row {
  display: flex;
  align-items: center;
  gap: 10px;
  justify-content: space-between;
  margin-bottom: 4px;
}

.conversation-copy p {
  margin: 0;
  color: var(--muted);
  font-size: 0.92rem;
}

.updated-at {
  flex-shrink: 0;
  font-size: 0.78rem;
  color: var(--muted);
}

.delete-btn {
  border: 0;
  border-radius: 999px;
  padding: 8px 10px;
  background: rgba(28, 36, 48, 0.1);
  color: var(--ink);
  cursor: pointer;
}

.conversation-actions {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.small-btn {
  border: 0;
  border-radius: 999px;
  padding: 8px 10px;
  background: rgba(31, 111, 120, 0.12);
  color: var(--accent);
  cursor: pointer;
}

.rename-input {
  width: 100%;
  min-width: 0;
  padding: 6px 10px;
  border-radius: 12px;
  border: 1px solid rgba(28, 36, 48, 0.16);
  font: inherit;
}

.chat-card {
  padding: 28px;
}

.toolbar {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  align-items: start;
  margin-bottom: 20px;
}

.toolbar-actions {
  display: flex;
  align-items: end;
  gap: 12px;
}

.workspace-field {
  display: grid;
  gap: 4px;
  min-width: 360px;
}

.workspace-field span {
  font-size: 0.78rem;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: var(--muted);
}

.workspace-field input {
  border-radius: 14px;
  border: 1px solid rgba(28, 36, 48, 0.12);
  padding: 12px 14px;
  background: rgba(255, 255, 255, 0.88);
  font: inherit;
}

.toolbar h2 {
  margin: 0;
  font-family: "Space Grotesk", "IBM Plex Sans", sans-serif;
}

.toolbar p {
  margin: 6px 0 0;
  opacity: 0.75;
}

.toolbar button,
.actions button {
  border: 0;
  border-radius: 999px;
  padding: 12px 18px;
  background: var(--accent);
  color: white;
  font-weight: 700;
  cursor: pointer;
}

.toolbar button:disabled,
.actions button:disabled {
  opacity: 0.6;
  cursor: wait;
}

.messages {
  display: grid;
  gap: 14px;
  margin-bottom: 18px;
  max-height: 560px;
  overflow: auto;
}

.approval-panel {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  padding: 16px;
  margin-bottom: 16px;
  border-radius: 20px;
  background: #fff5db;
  border: 1px solid #f2d48a;
}

.approval-panel h3,
.approval-panel p {
  margin: 0;
}

.approval-panel h3 {
  margin-top: 4px;
  margin-bottom: 6px;
}

.approval-panel code {
  display: inline-block;
  margin-top: 8px;
  padding: 6px 8px;
  border-radius: 10px;
  background: rgba(28, 36, 48, 0.08);
}

.approval-actions {
  display: flex;
  gap: 10px;
  align-items: center;
}

.approval-actions .secondary {
  background: rgba(28, 36, 48, 0.12);
  color: var(--ink);
}

.message {
  padding: 14px 16px;
  border-radius: 20px;
  background: rgba(255, 255, 255, 0.75);
}

.message.streaming {
  box-shadow: inset 0 0 0 1px rgba(31, 111, 120, 0.16);
}

.message.user {
  background: rgba(31, 111, 120, 0.12);
}

.meta {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: center;
  margin-bottom: 8px;
}

.role {
  display: inline-block;
  font-size: 0.8rem;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  opacity: 0.7;
}

.elapsed {
  font-size: 0.82rem;
  color: var(--muted);
  white-space: nowrap;
}

.markdown-body {
  color: var(--ink);
  line-height: 1.65;
}

.streaming-body {
  color: var(--ink);
  line-height: 1.65;
  white-space: pre-wrap;
  word-break: break-word;
}

.stream-cursor {
  display: inline-block;
  width: 0.68ch;
  height: 1.05em;
  margin-top: 6px;
  border-radius: 3px;
  background: var(--accent);
  animation: stream-blink 1s steps(1) infinite;
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
  background: rgba(28, 36, 48, 0.08);
  font-family: "IBM Plex Mono", monospace;
  font-size: 0.92em;
}

.markdown-body :deep(pre) {
  margin: 0 0 12px;
  padding: 14px;
  border-radius: 16px;
  overflow: auto;
  background: rgba(28, 36, 48, 0.92);
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

.tool-events {
  display: grid;
  gap: 10px;
  margin-top: 14px;
}

.tool-event {
  border: 1px solid rgba(28, 36, 48, 0.12);
  border-radius: 16px;
  background: rgba(255, 255, 255, 0.96);
  overflow: hidden;
}

.tool-event-summary {
  display: flex;
  justify-content: space-between;
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
}

.tool-event-status {
  border-radius: 999px;
  padding: 6px 12px;
  font-size: 0.82rem;
  font-weight: 700;
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
  background: rgba(28, 36, 48, 0.94);
  color: #f8fafc;
  font-family: "IBM Plex Mono", monospace;
  font-size: 0.9rem;
  line-height: 1.55;
}

.thinking-block {
  margin: 8px 0;
  border: 1px solid rgba(139, 92, 246, 0.2);
  border-radius: 16px;
  background: linear-gradient(135deg, rgba(139, 92, 246, 0.04), rgba(99, 102, 241, 0.02));
  overflow: hidden;
}

.thinking-summary {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 14px;
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

.thinking-block[open] .thinking-summary {
  border-bottom: 1px solid rgba(139, 92, 246, 0.1);
}

.thinking-content {
  padding: 12px 14px;
  border-left: 3px solid rgba(139, 92, 246, 0.18);
}

.composer textarea {
  width: 100%;
  box-sizing: border-box;
  resize: vertical;
  padding: 16px;
  border-radius: 20px;
  border: 1px solid rgba(28, 36, 48, 0.12);
  background: rgba(255, 255, 255, 0.88);
  font: inherit;
}

.actions {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
  margin-top: 12px;
}

.stop-btn {
  background: #b42318;
}

@keyframes stream-blink {
  0%,
  49% {
    opacity: 1;
  }

  50%,
  100% {
    opacity: 0;
  }
}

@media (max-width: 980px) {
  .workspace {
    grid-template-columns: 1fr;
  }

  .sidebar {
    position: static;
  }
}

@media (max-width: 700px) {
  .toolbar,
  .toolbar-actions,
  .sidebar-head,
  .conversation-card,
  .conversation-title-row,
  .conversation-actions {
    flex-direction: column;
  }
}
</style>
