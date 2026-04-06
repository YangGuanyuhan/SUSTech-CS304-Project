<template>
  <section class="database-panel">
    <header class="panel-header">
      <div>
        <p class="eyebrow">持久化仪表盘</p>
        <h2>数据库概览</h2>
      </div>
      <button class="close-button" type="button" @click="$emit('close')">
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <line x1="18" y1="6" x2="6" y2="18"/>
          <line x1="6" y1="6" x2="18" y2="18"/>
        </svg>
        关闭
      </button>
    </header>

    <p v-if="loading" class="state">正在加载数据库摘要...</p>
    <p v-else-if="error" class="state error">{{ error }}</p>

    <template v-else-if="overview">
      <!-- Metrics Grid -->
      <section class="metric-grid">
        <article v-for="metric in metrics" :key="metric.label" class="metric-card">
          <span>{{ metric.label }}</span>
          <strong>{{ metric.value }}</strong>
        </article>
      </section>

      <!-- Content Grid -->
      <section class="content-grid">
        <!-- Memory Categories -->
        <article class="panel-card">
          <h3>
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M12 2L2 7l10 5 10-5-10-5z"/>
              <path d="M2 17l10 5 10-5"/>
              <path d="M2 12l10 5 10-5"/>
            </svg>
            记忆分类
          </h3>
          <ul v-if="overview.memory_categories.length" class="stat-list">
            <li v-for="item in overview.memory_categories" :key="item.category">
              <span>{{ item.category }}</span>
              <strong>{{ item.count }}</strong>
            </li>
          </ul>
          <p v-else class="empty">暂无记忆记录。</p>
        </article>

        <!-- Session Activity -->
        <article class="panel-card">
          <h3>
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>
            </svg>
            会话活动
          </h3>
          <ul v-if="overview.session_activity.length" class="stat-list">
            <li v-for="item in overview.session_activity" :key="item.session_id">
              <span class="session-id">{{ item.session_id.slice(0, 8) }}...</span>
              <strong>{{ item.message_count }} 条消息</strong>
            </li>
          </ul>
          <p v-else class="empty">暂无聊天历史。</p>
        </article>

        <!-- Recent History -->
        <article class="panel-card wide">
          <h3>
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <circle cx="12" cy="12" r="10"/>
              <polyline points="12 6 12 12 16 14"/>
            </svg>
            最近历史
          </h3>
          <ul v-if="overview.recent_history.length" class="history-list">
            <li v-for="item in overview.recent_history" :key="item.id">
              <div class="history-header">
                <strong>{{ item.session_id.slice(0, 12) }}...</strong>
                <span>{{ formatTime(item.created_at) }}</span>
              </div>
              <p class="history-preview">{{ item.user_input_preview || "无用户输入预览。" }}</p>
              <small class="tools-used">工具: {{ item.tools_used.length ? item.tools_used.join(", ") : "无" }}</small>
            </li>
          </ul>
          <p v-else class="empty">暂无任务历史。</p>
        </article>

        <!-- Latest Quiz Attempt -->
        <article class="panel-card">
          <h3>
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <circle cx="12" cy="12" r="10"/>
              <path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3"/>
              <line x1="12" y1="17" x2="12.01" y2="17"/>
            </svg>
            最近测验
          </h3>
          <template v-if="overview.latest_quiz_attempt">
            <p class="quiz-title">{{ overview.latest_quiz_attempt.title }}</p>
            <p class="quiz-topic">{{ overview.latest_quiz_attempt.topic }}</p>
            <div class="quiz-score">
              <strong>{{ overview.latest_quiz_attempt.score }}</strong>
              <span>/ {{ overview.latest_quiz_attempt.total_points }}</span>
            </div>
          </template>
          <p v-else class="empty">暂无测验记录。</p>
        </article>

        <!-- Schema Readiness -->
        <article class="panel-card">
          <h3>
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <polyline points="20 6 9 17 4 12"/>
            </svg>
            架构就绪状态
          </h3>
          <ul class="readiness-list">
            <li v-for="item in readinessItems" :key="item.label">
              <span>{{ item.label }}</span>
              <strong :class="item.ready ? 'ready' : 'pending'">
                {{ item.ready ? '就绪' : '待处理' }}
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
    { label: "记忆", value: overview.value.counts.memories },
    { label: "任务历史", value: overview.value.counts.task_history },
    { label: "测验会话", value: overview.value.counts.quiz_sessions },
    { label: "测验尝试", value: overview.value.counts.quiz_attempts },
    { label: "邮件草稿", value: overview.value.counts.email_drafts },
    { label: "用户偏好", value: overview.value.counts.user_preferences }
  ];
});

const readinessItems = computed(() => {
  if (!overview.value) return [];
  return [
    { label: "JSON 类型列", ready: overview.value.schema_readiness.typed_json_ready },
    { label: "测验关联", ready: overview.value.schema_readiness.quiz_relationships_ready },
    { label: "会话存储", ready: overview.value.schema_readiness.conversation_storage_ready },
    { label: "记忆向量", ready: overview.value.schema_readiness.memory_embedding_ready },
    { label: "邮件审批历史", ready: overview.value.schema_readiness.email_approval_history_ready }
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
  background: rgba(255, 255, 255, 0.96);
  border-radius: 28px;
  padding: 28px;
  box-shadow: 0 24px 60px rgba(28, 36, 48, 0.18);
  max-width: 900px;
  margin: 0 auto;
}

.panel-header {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  align-items: flex-start;
  margin-bottom: 24px;
}

.panel-header h2 {
  margin: 0;
  font-family: var(--font-heading);
  font-size: 24px;
  color: var(--text-primary);
}

.eyebrow {
  margin: 0 0 6px;
  text-transform: uppercase;
  letter-spacing: 0.12em;
  font-size: 11px;
  font-weight: 600;
  color: var(--accent-orange);
}

.close-button {
  display: flex;
  align-items: center;
  gap: 6px;
  border: 0;
  border-radius: 999px;
  padding: 10px 16px;
  background: var(--bg-hover);
  color: var(--text-primary);
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s ease;
}

.close-button:hover {
  background: var(--border-subtle);
}

/* Metrics */
.metric-grid {
  display: grid;
  grid-template-columns: repeat(6, 1fr);
  gap: 12px;
  margin-bottom: 24px;
}

.metric-card {
  background: white;
  border: 1px solid var(--border-light);
  border-radius: 16px;
  padding: 16px;
  text-align: center;
}

.metric-card span {
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--text-muted);
}

.metric-card strong {
  display: block;
  margin-top: 8px;
  font-size: 1.5rem;
  font-family: var(--font-heading);
  color: var(--accent-orange);
}

/* Content Grid */
.content-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 16px;
}

.panel-card {
  background: white;
  border: 1px solid var(--border-light);
  border-radius: 20px;
  padding: 20px;
}

.panel-card.wide {
  grid-column: 1 / -1;
}

.panel-card h3 {
  display: flex;
  align-items: center;
  gap: 8px;
  margin: 0 0 16px;
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
}

.panel-card h3 svg {
  color: var(--accent-orange);
}

/* Stat List */
.stat-list,
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
  padding: 8px 12px;
  border-radius: 10px;
  background: var(--bg-main);
}

.stat-list li span,
.session-id {
  font-size: 13px;
  color: var(--text-secondary);
}

.stat-list li strong {
  font-size: 13px;
  color: var(--text-primary);
}

/* History List */
.history-list {
  list-style: none;
  padding: 0;
  margin: 0;
  display: grid;
  gap: 12px;
}

.history-list li {
  padding: 14px;
  border-radius: 14px;
  background: var(--bg-main);
}

.history-header {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 8px;
}

.history-header strong {
  font-size: 13px;
  color: var(--text-primary);
}

.history-header span {
  font-size: 12px;
  color: var(--text-muted);
}

.history-preview {
  margin: 0 0 8px;
  font-size: 13px;
  color: var(--text-secondary);
  line-height: 1.4;
}

.tools-used {
  font-size: 11px;
  color: var(--text-muted);
}

/* Quiz Score */
.quiz-title {
  font-weight: 600;
  margin: 0 0 4px;
  font-size: 14px;
  color: var(--text-primary);
}

.quiz-topic {
  margin: 0 0 12px;
  font-size: 13px;
  color: var(--text-muted);
}

.quiz-score {
  display: flex;
  align-items: baseline;
  gap: 4px;
}

.quiz-score strong {
  font-size: 2rem;
  font-family: var(--font-heading);
  color: var(--accent-orange);
}

.quiz-score span {
  font-size: 14px;
  color: var(--text-muted);
}

/* Readiness */
.ready {
  color: #16a34a;
}

.pending {
  color: #d97706;
}

/* States */
.state {
  text-align: center;
  padding: 40px;
  color: var(--text-muted);
}

.state.error {
  color: #dc2626;
}

.empty {
  color: var(--text-muted);
  font-size: 13px;
}

@media (max-width: 780px) {
  .metric-grid {
    grid-template-columns: repeat(3, 1fr);
  }

  .content-grid {
    grid-template-columns: 1fr;
  }

  .panel-header {
    flex-direction: column;
  }
}

@media (max-width: 500px) {
  .metric-grid {
    grid-template-columns: repeat(2, 1fr);
  }
}
</style>