<template>
  <section class="history-panel">
    <header class="history-header">
      <div>
        <p class="eyebrow">Quiz History</p>
        <h2>Practice Review</h2>
        <p>Recent attempts, weak areas, and personalized study analysis.</p>
      </div>
      <div class="history-actions">
        <button :disabled="loading" @click="refreshHistory">
          {{ loading ? "Loading..." : "Refresh" }}
        </button>
        <button class="secondary" @click="$emit('close')">Close</button>
      </div>
    </header>

    <section v-if="error" class="history-empty">
      <strong>Failed to load quiz history</strong>
      <p>{{ error }}</p>
    </section>

    <section v-else-if="!history || history.total_attempts === 0" class="history-empty">
      <strong>No quiz attempts yet</strong>
      <p>Generate a quiz in chat and submit at least one attempt to build a practice history.</p>
    </section>

    <template v-else>
      <section class="history-summary">
        <article class="summary-card">
          <span>Total Attempts</span>
          <strong>{{ history.total_attempts }}</strong>
        </article>
        <article class="summary-card">
          <span>Average Score</span>
          <strong>{{ history.average_score }}%</strong>
        </article>
        <article class="summary-card summary-analysis">
          <span>Personalized Analysis</span>
          <p>{{ history.personalized_analysis }}</p>
        </article>
      </section>

      <section class="attempt-list">
        <article v-for="attempt in history.attempts" :key="attempt.attempt_id" class="attempt-card">
          <div class="attempt-head">
            <div>
              <strong>{{ attempt.title }}</strong>
              <p>{{ attempt.topic }}</p>
            </div>
            <div class="attempt-score">
              <span>{{ attempt.score }} / {{ attempt.total_points }}</span>
              <small>{{ formatTime(attempt.submitted_at) }}</small>
            </div>
          </div>

          <div v-if="attempt.weak_areas?.length" class="weak-area-list">
            <span>Weak areas</span>
            <ul>
              <li v-for="(item, index) in attempt.weak_areas" :key="`${attempt.attempt_id}-${index}`">
                {{ item }}
              </li>
            </ul>
          </div>
        </article>
      </section>
    </template>
  </section>
</template>

<script setup>
import { onMounted, ref } from "vue";
import { getQuizHistory } from "../api/client";

defineEmits(["close"]);

const history = ref(null);
const loading = ref(false);
const error = ref("");

function formatTime(timestamp) {
  return new Date(timestamp).toLocaleString([], {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit"
  });
}

async function refreshHistory() {
  loading.value = true;
  error.value = "";
  try {
    const response = await getQuizHistory(10);
    history.value = response.data;
  } catch (err) {
    error.value = err.message;
  } finally {
    loading.value = false;
  }
}

onMounted(() => {
  refreshHistory();
});
</script>

<style scoped>
.history-panel {
  display: grid;
  gap: 20px;
  padding: 28px;
  border-radius: 28px;
  background: rgba(255, 255, 255, 0.96);
  box-shadow: 0 24px 60px rgba(28, 36, 48, 0.18);
}

.history-header {
  display: flex;
  justify-content: space-between;
  gap: 18px;
  align-items: start;
}

.history-header h2,
.history-header p {
  margin: 0;
}

.history-actions {
  display: flex;
  gap: 10px;
}

.history-actions button {
  border: 0;
  border-radius: 999px;
  padding: 10px 16px;
  background: var(--accent);
  color: white;
  font-weight: 700;
  cursor: pointer;
}

.history-actions button.secondary {
  background: rgba(28, 36, 48, 0.12);
  color: var(--ink);
}

.history-summary {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 14px;
}

.summary-card {
  display: grid;
  gap: 8px;
  padding: 18px;
  border-radius: 20px;
  background: rgba(31, 111, 120, 0.08);
}

.summary-card span {
  text-transform: uppercase;
  letter-spacing: 0.08em;
  font-size: 0.78rem;
  color: var(--muted);
}

.summary-card strong {
  font-size: 1.6rem;
}

.summary-analysis {
  grid-column: span 1;
}

.summary-analysis p {
  margin: 0;
  line-height: 1.6;
}

.attempt-list {
  display: grid;
  gap: 14px;
}

.attempt-card {
  display: grid;
  gap: 12px;
  padding: 18px;
  border-radius: 20px;
  background: rgba(243, 239, 229, 0.78);
}

.attempt-head {
  display: flex;
  justify-content: space-between;
  gap: 14px;
  align-items: start;
}

.attempt-head strong,
.attempt-head p {
  margin: 0;
}

.attempt-head p {
  color: var(--muted);
}

.attempt-score {
  display: grid;
  justify-items: end;
  gap: 4px;
}

.attempt-score span {
  font-weight: 700;
}

.attempt-score small {
  color: var(--muted);
}

.weak-area-list {
  display: grid;
  gap: 8px;
}

.weak-area-list span {
  font-size: 0.82rem;
  font-weight: 700;
  color: var(--muted);
}

.weak-area-list ul {
  margin: 0;
  padding-left: 20px;
}

.history-empty {
  display: grid;
  gap: 8px;
  padding: 20px;
  border-radius: 20px;
  background: rgba(243, 239, 229, 0.72);
}

.history-empty p,
.history-empty strong {
  margin: 0;
}

@media (max-width: 820px) {
  .history-summary {
    grid-template-columns: 1fr;
  }

  .history-header,
  .attempt-head {
    flex-direction: column;
  }

  .attempt-score {
    justify-items: start;
  }
}
</style>
