<template>
  <section class="database-panel">
    <header class="panel-header">
      <div>
        <p class="eyebrow">Persistence Dashboard</p>
        <h2>Database Overview</h2>
      </div>
      <button class="close-button" type="button" @click="$emit('close')">Close</button>
    </header>

    <p v-if="loading" class="state">Loading database summary...</p>
    <p v-else-if="error" class="state error">{{ error }}</p>

    <template v-else-if="overview">
      <section class="metric-grid">
        <article v-for="metric in metrics" :key="metric.label" class="metric-card">
          <span>{{ metric.label }}</span>
          <strong>{{ metric.value }}</strong>
        </article>
      </section>

      <section class="content-grid">
        <article class="panel-card">
          <h3>Memory Categories</h3>
          <ul v-if="overview.memory_categories.length" class="stat-list">
            <li v-for="item in overview.memory_categories" :key="item.category">
              <span>{{ item.category }}</span>
              <strong>{{ item.count }}</strong>
            </li>
          </ul>
          <p v-else class="empty">No memory records yet.</p>
        </article>

        <article class="panel-card">
          <h3>Session Activity</h3>
          <ul v-if="overview.session_activity.length" class="stat-list">
            <li v-for="item in overview.session_activity" :key="item.session_id">
              <span>{{ item.session_id }}</span>
              <strong>{{ item.message_count }}</strong>
            </li>
          </ul>
          <p v-else class="empty">No chat history yet.</p>
        </article>

        <article class="panel-card wide">
          <h3>Recent History</h3>
          <ul v-if="overview.recent_history.length" class="history-list">
            <li v-for="item in overview.recent_history" :key="item.id">
              <div>
                <strong>{{ item.session_id }}</strong>
                <span>{{ formatTime(item.created_at) }}</span>
              </div>
              <p>{{ item.user_input_preview || "No user input preview." }}</p>
              <small>Tools: {{ item.tools_used.length ? item.tools_used.join(", ") : "none" }}</small>
            </li>
          </ul>
          <p v-else class="empty">No task history persisted yet.</p>
        </article>

        <article class="panel-card">
          <h3>Latest Quiz Attempt</h3>
          <template v-if="overview.latest_quiz_attempt">
            <p class="quiz-title">{{ overview.latest_quiz_attempt.title }}</p>
            <p>{{ overview.latest_quiz_attempt.topic }}</p>
            <strong>
              {{ overview.latest_quiz_attempt.score }}/{{ overview.latest_quiz_attempt.total_points }}
            </strong>
          </template>
          <p v-else class="empty">No quiz attempts recorded.</p>
        </article>

        <article class="panel-card">
          <h3>Schema Readiness</h3>
          <ul class="readiness-list">
            <li v-for="item in readinessItems" :key="item.label">
              <span>{{ item.label }}</span>
              <strong :class="item.ready ? 'ready' : 'pending'">
                {{ item.ready ? "ready" : "pending" }}
              </strong>
            </li>
          </ul>
        </article>
      </section>
    </template>
  </section>
</template>

<script setup>
import { computed, onMounted, ref } from "vue";
import { getDatabaseOverview } from "../api/client";

defineEmits(["close"]);

const loading = ref(true);
const error = ref("");
const overview = ref(null);

const metrics = computed(() => {
  if (!overview.value) return [];
  return [
    { label: "Memories", value: overview.value.counts.memories },
    { label: "Task History", value: overview.value.counts.task_history },
    { label: "Quiz Sessions", value: overview.value.counts.quiz_sessions },
    { label: "Quiz Attempts", value: overview.value.counts.quiz_attempts },
    { label: "Email Drafts", value: overview.value.counts.email_drafts },
    { label: "Preferences", value: overview.value.counts.user_preferences }
  ];
});

const readinessItems = computed(() => {
  if (!overview.value) return [];
  return [
    { label: "Typed JSON columns", ready: overview.value.schema_readiness.typed_json_ready },
    { label: "Quiz relationships", ready: overview.value.schema_readiness.quiz_relationships_ready },
    { label: "Conversation storage", ready: overview.value.schema_readiness.conversation_storage_ready },
    { label: "Memory embeddings", ready: overview.value.schema_readiness.memory_embedding_ready },
    { label: "Email approval history", ready: overview.value.schema_readiness.email_approval_history_ready }
  ];
});

function formatTime(value) {
  return new Date(value).toLocaleString();
}

async function loadOverview() {
  loading.value = true;
  error.value = "";
  try {
    const response = await getDatabaseOverview();
    overview.value = response.data;
  } catch (loadError) {
    error.value = loadError.message;
  } finally {
    loading.value = false;
  }
}

onMounted(loadOverview);
</script>

<style scoped>
.database-panel {
  background: rgba(255, 252, 245, 0.96);
  border-radius: 28px;
  padding: 24px;
  box-shadow: 0 24px 60px rgba(28, 36, 48, 0.18);
}

.panel-header {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  align-items: start;
  margin-bottom: 20px;
}

.panel-header h2 {
  margin: 0;
  font-family: "Space Grotesk", "IBM Plex Sans", sans-serif;
}

.eyebrow {
  margin: 0 0 6px;
  text-transform: uppercase;
  letter-spacing: 0.14em;
  font-size: 0.75rem;
  color: #1f6f78;
}

.close-button {
  border: 0;
  border-radius: 999px;
  padding: 10px 16px;
  background: #1c2430;
  color: white;
  cursor: pointer;
}

.metric-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
  gap: 12px;
  margin-bottom: 20px;
}

.metric-card,
.panel-card {
  background: white;
  border: 1px solid rgba(31, 111, 120, 0.12);
  border-radius: 20px;
  padding: 16px;
}

.metric-card span,
.panel-card h3 {
  color: #54606e;
}

.metric-card strong {
  display: block;
  margin-top: 8px;
  font-size: 1.7rem;
  color: #1c2430;
}

.content-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 16px;
}

.panel-card.wide {
  grid-column: 1 / -1;
}

.stat-list,
.history-list,
.readiness-list {
  list-style: none;
  padding: 0;
  margin: 0;
  display: grid;
  gap: 10px;
}

.stat-list li,
.readiness-list li {
  display: flex;
  justify-content: space-between;
  gap: 12px;
}

.history-list li {
  padding: 12px;
  border-radius: 16px;
  background: #f7f4ed;
}

.history-list li div {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 8px;
}

.history-list p,
.history-list small,
.panel-card p {
  margin: 0;
}

.quiz-title {
  font-weight: 700;
  margin-bottom: 6px;
}

.ready {
  color: #1e7a46;
}

.pending {
  color: #a85718;
}

.state,
.empty {
  color: #54606e;
}

.state.error {
  color: #ac3b2b;
}

@media (max-width: 780px) {
  .content-grid {
    grid-template-columns: 1fr;
  }

  .panel-header {
    flex-direction: column;
  }
}
</style>
