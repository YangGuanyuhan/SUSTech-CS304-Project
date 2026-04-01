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
        <button :disabled="loading" @click="loadCourses">Load Blackboard Courses</button>
      </header>

      <div class="messages">
        <article
          v-for="message in activeConversation.messages"
          :key="message.id"
          :class="['message', message.role]"
        >
          <div class="meta">
            <span class="role">{{ message.role }}</span>
            <span v-if="message.elapsedLabel" class="elapsed">{{ message.elapsedLabel }}</span>
          </div>
          <div
            class="markdown-body"
            v-html="renderMarkdown(message.content)"
          />
        </article>
      </div>

      <form class="composer" @submit.prevent="submitMessage">
        <textarea
          v-model="draft"
          rows="4"
          placeholder="Ask about courses, search, or saved memory..."
        />
        <div class="actions">
          <button :disabled="loading || !draft.trim()" type="submit">
            {{ loading ? "Streaming..." : "Send" }}
          </button>
        </div>
      </form>
    </section>
  </section>
</template>

<script setup>
import MarkdownIt from "markdown-it";
import { computed, onBeforeUnmount, reactive, ref, watch } from "vue";
import { getCourses, streamChat } from "../api/client";

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
    messages: [
      reactive({
        id: crypto.randomUUID(),
        role: "assistant",
        content: "UI is connected to the backend contract. Start here or continue a previous session.",
        elapsedLabel: ""
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
        messages: (conversation.messages || []).map((message) => reactive(message))
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
let activeTimer = null;

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
      elapsedLabel: ""
    })
  );
  activeConversation.value.updatedAt = Date.now();
}

async function loadCourses() {
  loading.value = true;
  try {
    const response = await getCourses();
    const courses = response.data?.data ?? [];
    const summary = courses.map((item) => `- ${item.name} (${item.code})`).join("\n");
    appendMessage("assistant", summary || "No courses returned.");
  } catch (error) {
    appendMessage("assistant", `Course request failed: ${error.message}`);
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
    content: "Waiting for model response...",
    elapsedLabel: ""
  });
  conversation.messages.push(assistantMessage);
  conversation.updatedAt = Date.now();
  updateConversationTitle(conversation);
  draft.value = "";
  loading.value = true;
  const stopTimer = startTimer(assistantMessage);

  try {
    await streamChat(
      { message: content, session_id: conversation.id },
      {
        onChunk(chunk) {
          if (assistantMessage.content === "Waiting for model response...") {
            assistantMessage.content = "";
          }
          assistantMessage.content += chunk;
        },
        onDone() {
          assistantMessage.content = assistantMessage.content.trim();
        }
      }
    );
  } catch (error) {
    assistantMessage.content = `Chat failed: ${error.message}`;
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

.message {
  padding: 14px 16px;
  border-radius: 20px;
  background: rgba(255, 255, 255, 0.75);
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
  margin-top: 12px;
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
  .sidebar-head,
  .conversation-card,
  .conversation-title-row,
  .conversation-actions {
    flex-direction: column;
  }
}
</style>
