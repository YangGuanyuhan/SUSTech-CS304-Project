<template>
  <section class="history-panel">
    <header class="history-header">
      <div>
        <p class="eyebrow">测验历史</p>
        <h2>练习回顾</h2>
        <p>最近的尝试、薄弱环节和个性化学习分析。</p>
      </div>
      <div class="history-actions">
        <button class="refresh-btn" :disabled="loading" @click="refreshHistory">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M23 4v6h-6"/>
            <path d="M1 20v-6h6"/>
            <path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"/>
          </svg>
          {{ loading ? '加载中...' : '刷新' }}
        </button>
        <button class="close-btn" @click="$emit('close')">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <line x1="18" y1="6" x2="6" y2="18"/>
            <line x1="6" y1="6" x2="18" y2="18"/>
          </svg>
          关闭
        </button>
      </div>
    </header>

    <!-- Error State -->
    <section v-if="error" class="history-empty error">
      <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <circle cx="12" cy="12" r="10"/>
        <line x1="12" y1="8" x2="12" y2="12"/>
        <line x1="12" y1="16" x2="12.01" y2="16"/>
      </svg>
      <div>
        <strong>加载测验历史失败</strong>
        <p>{{ error }}</p>
      </div>
    </section>

    <!-- Empty State -->
    <section v-else-if="!history || history.total_attempts === 0" class="history-empty">
      <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
        <circle cx="12" cy="12" r="10"/>
        <path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3"/>
        <line x1="12" y1="17" x2="12.01" y2="17"/>
      </svg>
      <strong>暂无测验记录</strong>
      <p>在聊天中生成测验并提交至少一次，以建立练习历史。</p>
    </section>

    <!-- History Content -->
    <template v-else>
      <!-- Summary Cards -->
      <section class="history-summary">
        <article class="summary-card">
          <div class="summary-icon">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M12 20V10"/>
              <path d="M18 20V4"/>
              <path d="M6 20v-4"/>
            </svg>
          </div>
          <div class="summary-content">
            <span>总尝试次数</span>
            <strong>{{ history.total_attempts }}</strong>
          </div>
        </article>
        <article class="summary-card">
          <div class="summary-icon">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/>
              <polyline points="22 4 12 14.01 9 11.01"/>
            </svg>
          </div>
          <div class="summary-content">
            <span>平均分数</span>
            <strong>{{ history.average_score }}%</strong>
          </div>
        </article>
        <article class="summary-card analysis">
          <div class="summary-icon">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"/>
              <polyline points="3.27 6.96 12 12.01 20.73 6.96"/>
              <line x1="12" y1="22.08" x2="12" y2="12"/>
            </svg>
          </div>
          <div class="summary-content">
            <span>个性化分析</span>
            <p>{{ history.personalized_analysis }}</p>
          </div>
        </article>
      </section>

      <!-- Attempt List -->
      <section class="attempt-list">
        <h3 class="list-title">最近尝试</h3>
        <article
          v-for="attempt in history.attempts"
          :key="attempt.attempt_id"
          :class="['attempt-card', { expanded: expandedAttempt === attempt.attempt_id }]"
          @click="toggleAttempt(attempt)"
        >
          <div class="attempt-head">
            <div class="attempt-info">
              <strong>{{ attempt.title }}</strong>
              <p>{{ attempt.topic }}</p>
            </div>
            <div class="attempt-score">
              <span class="score-value">{{ attempt.score }}</span>
              <span class="score-divider">/</span>
              <span class="score-total">{{ attempt.total_points }}</span>
              <small>{{ formatTime(attempt.submitted_at) }}</small>
            </div>
            <div class="expand-chevron">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <polyline points="6 9 12 15 18 9"/>
              </svg>
            </div>
          </div>

          <div v-if="attempt.weak_areas?.length" class="weak-area-list">
            <span class="weak-label">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/>
                <line x1="12" y1="9" x2="12" y2="13"/>
                <line x1="12" y1="17" x2="12.01" y2="17"/>
              </svg>
              薄弱环节
            </span>
            <ul>
              <li v-for="(item, index) in attempt.weak_areas" :key="`${attempt.attempt_id}-${index}`">
                {{ item }}
              </li>
            </ul>
          </div>

          <!-- Expanded Detail -->
          <div v-if="expandedAttempt === attempt.attempt_id" class="attempt-detail" @click.stop>
            <div v-if="detailLoading" class="detail-loading">
              <span class="spinner"></span>
              加载答题详情...
            </div>
            <div v-else-if="attemptDetail?.error" class="detail-error">
              {{ attemptDetail.error }}
            </div>
            <div v-else-if="attemptDetail" class="detail-answers">
              <article
                v-for="answer in attemptDetail.answers"
                :key="answer.question_id"
                class="detail-answer-card"
              >
                <div class="detail-answer-head">
                  <strong class="detail-prompt">{{ answer.prompt }}</strong>
                  <span :class="['quiz-badge', isResultCorrect(answer) ? 'right' : 'wrong']">
                    <svg v-if="isResultCorrect(answer)" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
                      <polyline points="20 6 9 17 4 12"/>
                    </svg>
                    <svg v-else width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
                      <line x1="18" y1="6" x2="6" y2="18"/>
                      <line x1="6" y1="6" x2="18" y2="18"/>
                    </svg>
                    {{ scoreLabel(answer) }}
                  </span>
                </div>
                <div class="detail-answer-body">
                  <!-- Options list for single_choice / true_false -->
                  <div v-if="answer.options?.length" class="options-list">
                    <div
                      v-for="(option, oIndex) in answer.options"
                      :key="`${answer.question_id}-${oIndex}`"
                      :class="optionItemClass(option, oIndex, answer)"
                    >
                      <span class="option-marker">{{ optionLetter(oIndex) }}</span>
                      <span class="option-text">{{ option }}</span>
                      <svg v-if="isCorrectOption(option, answer)" class="option-icon correct" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
                        <polyline points="20 6 9 17 4 12"/>
                      </svg>
                      <svg v-else-if="isSelectedWrongOption(option, oIndex, answer)" class="option-icon wrong" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
                        <line x1="18" y1="6" x2="6" y2="18"/>
                        <line x1="6" y1="6" x2="18" y2="18"/>
                      </svg>
                    </div>
                  </div>

                  <!-- Short answer: show your answer + correct answer rows -->
                  <template v-else>
                    <div class="detail-row">
                      <span class="detail-label">你的回答</span>
                      <span class="detail-value">{{ answer.submitted_answer || '(未作答)' }}</span>
                    </div>
                    <div class="detail-row">
                      <span class="detail-label">参考答案</span>
                      <span class="detail-value correct">{{ answer.correct_answer }}</span>
                    </div>
                  </template>

                  <div v-if="answer.feedback" class="detail-feedback markdown-body" v-html="renderMarkdown(answer.feedback)" />
                </div>
              </article>
            </div>
          </div>
        </article>
      </section>
    </template>
  </section>
</template>

<script setup>
import { onMounted, ref } from "vue";
import { getQuizHistory, getQuizAttemptDetail } from "../api/client";
import { renderMarkdown } from "../utils/markdown.js";

defineEmits(["close"]);

const history = ref(null);
const loading = ref(false);
const error = ref("");
const expandedAttempt = ref(null);
const attemptDetail = ref(null);
const detailLoading = ref(false);

function formatTime(timestamp) {
  return new Date(timestamp).toLocaleString([], {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit"
  });
}

function scoreLabel(result) {
  if (result.is_correct === true) return "正确";
  if (result.is_correct === false) return "错误";
  return `${result.score} / ${result.max_score}`;
}

function isResultCorrect(result) {
  if (!result) return false;
  if (result.is_correct === true) return true;
  if (result.is_correct === false) return false;
  const score = Number(result.score ?? 0);
  const maxScore = Number(result.max_score ?? 0);
  return Math.abs(score - maxScore) < 1e-6;
}

function normalizeText(value) {
  return (value || "").trim().toLowerCase();
}

function optionLetter(index) {
  return String.fromCharCode(65 + index);
}

function isCorrectOption(option, answer) {
  return normalizeText(option) === normalizeText(answer.correct_answer);
}

function isSelectedWrongOption(option, index, answer) {
  if (isCorrectOption(option, answer)) return false;
  const submitted = (answer.submitted_answer || "").trim();
  return (
    normalizeText(option) === normalizeText(submitted) ||
    optionLetter(index) === submitted.toUpperCase()
  );
}

function optionItemClass(option, index, answer) {
  const correct = isCorrectOption(option, answer);
  const selectedWrong = isSelectedWrongOption(option, index, answer);
  if (correct && !selectedWrong) return "option-correct";
  if (selectedWrong) return "option-wrong";
  if (correct) return "option-correct";
  return "option-neutral";
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

async function toggleAttempt(attempt) {
  if (expandedAttempt.value === attempt.attempt_id) {
    expandedAttempt.value = null;
    attemptDetail.value = null;
    return;
  }
  expandedAttempt.value = attempt.attempt_id;
  detailLoading.value = true;
  attemptDetail.value = null;
  try {
    const response = await getQuizAttemptDetail(attempt.attempt_id);
    attemptDetail.value = response.data;
  } catch (err) {
    attemptDetail.value = { error: err.message };
  } finally {
    detailLoading.value = false;
  }
}

onMounted(() => {
  refreshHistory();
});
</script>

<style scoped>
.history-panel {
  display: grid;
  gap: 24px;
  padding: 28px;
  border-radius: 16px;
  background: rgba(255, 255, 255, 0.96);
  box-shadow: 0 24px 60px rgba(28, 36, 48, 0.18);
  max-width: 900px;
  margin: 0 auto;
  max-height: 80vh;
  overflow-y: auto;
}

.history-header {
  display: flex;
  justify-content: space-between;
  gap: 18px;
  align-items: flex-start;
}

.history-header h2 {
  margin: 4px 0 4px;
  font-family: var(--font-heading);
  font-size: 24px;
  color: var(--text-primary);
}

.history-header p {
  margin: 0;
  font-size: 13px;
  color: var(--text-muted);
}

.history-actions {
  display: flex;
  gap: 10px;
}

.refresh-btn, .close-btn {
  display: flex;
  align-items: center;
  gap: 6px;
  border: 0;
  border-radius: 999px;
  padding: 10px 18px;
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s ease;
}

.refresh-btn {
  background: var(--accent-orange);
  color: white;
}

.refresh-btn:hover {
  background: #EA580C;
}

.refresh-btn:disabled {
  opacity: 0.6;
  cursor: wait;
}

.close-btn {
  background: var(--bg-hover);
  color: var(--text-primary);
}

.close-btn:hover {
  background: var(--border-subtle);
}

/* Summary Cards */
.history-summary {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 16px;
}

.summary-card {
  display: flex;
  align-items: flex-start;
  gap: 14px;
  padding: 20px;
  border-radius: 20px;
  background: var(--bg-main);
}

.summary-card.analysis {
  grid-column: span 1;
}

.summary-icon {
  width: 44px;
  height: 44px;
  border-radius: 14px;
  background: var(--accent-orange-subtle);
  color: var(--accent-orange);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.summary-content {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.summary-content span {
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: var(--text-muted);
}

.summary-content strong {
  font-size: 1.8rem;
  font-family: var(--font-heading);
  color: var(--text-primary);
}

.summary-content p {
  margin: 4px 0 0;
  font-size: 13px;
  color: var(--text-secondary);
  line-height: 1.5;
}

/* Attempt List */
.list-title {
  margin: 0 0 16px;
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
}

.attempt-list {
  display: grid;
  gap: 14px;
}

.attempt-card {
  display: grid;
  gap: 14px;
  padding: 20px;
  border-radius: 18px;
  background: white;
  border: 1px solid var(--border-light);
}

.attempt-head {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  align-items: flex-start;
}

.attempt-info strong {
  display: block;
  font-size: 15px;
  color: var(--text-primary);
  margin-bottom: 4px;
}

.attempt-info p {
  margin: 0;
  font-size: 13px;
  color: var(--text-muted);
}

.attempt-score {
  display: flex;
  align-items: baseline;
  gap: 4px;
  text-align: right;
}

.score-value {
  font-size: 1.5rem;
  font-family: var(--font-heading);
  font-weight: 700;
  color: var(--accent-orange);
}

.score-divider {
  font-size: 1rem;
  color: var(--text-muted);
}

.score-total {
  font-size: 1rem;
  color: var(--text-muted);
}

.attempt-score small {
  display: block;
  margin-top: 4px;
  font-size: 11px;
  color: var(--text-muted);
}

/* Weak Areas */
.weak-area-list {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
  padding-top: 12px;
  border-top: 1px solid var(--border-light);
}

.weak-label {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 11px;
  font-weight: 600;
  color: #d97706;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.weak-area-list ul {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin: 0;
  padding: 0;
  list-style: none;
}

.weak-area-list li {
  padding: 4px 12px;
  border-radius: 999px;
  background: rgba(217, 119, 6, 0.1);
  font-size: 12px;
  color: #b45309;
}

/* Empty State */
.history-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
  padding: 48px;
  border-radius: 20px;
  background: var(--bg-main);
  text-align: center;
}

.history-empty svg {
  color: var(--text-muted);
}

.history-empty strong {
  font-size: 16px;
  color: var(--text-primary);
}

.history-empty p {
  margin: 0;
  font-size: 13px;
  color: var(--text-muted);
  max-width: 320px;
}

.history-empty.error {
  flex-direction: row;
  justify-content: flex-start;
  padding: 20px;
  background: rgba(239, 68, 68, 0.08);
  text-align: left;
}

.history-empty.error svg {
  color: #dc2626;
  flex-shrink: 0;
}

.history-empty.error strong {
  color: #dc2626;
}

/* Expandable */
.attempt-card {
  cursor: pointer;
  transition: box-shadow 0.2s ease;
}

.attempt-card:hover {
  box-shadow: 0 2px 12px rgba(28, 36, 48, 0.08);
}

.expand-chevron {
  display: flex;
  align-items: center;
  color: var(--text-muted);
  transition: transform 0.25s ease;
  flex-shrink: 0;
}

.attempt-card.expanded .expand-chevron {
  transform: rotate(180deg);
}

/* Detail Section */
.attempt-detail {
  border-top: 1px solid var(--border-light);
  padding-top: 14px;
}

.detail-loading {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 20px;
  font-size: 13px;
  color: var(--text-muted);
}

.spinner {
  width: 18px;
  height: 18px;
  border: 2px solid var(--border-light);
  border-top-color: var(--accent-orange);
  border-radius: 50%;
  animation: spin 0.6s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.detail-error {
  padding: 14px;
  border-radius: 12px;
  background: rgba(239, 68, 68, 0.08);
  color: #dc2626;
  font-size: 13px;
}

.detail-answers {
  display: grid;
  gap: 12px;
}

.detail-answer-card {
  display: grid;
  gap: 10px;
  padding: 14px;
  border-radius: 14px;
  background: var(--bg-main);
}

.detail-answer-head {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 12px;
}

.detail-prompt {
  font-size: 14px;
  color: var(--text-primary);
  line-height: 1.5;
  flex: 1;
}

.quiz-badge {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  border-radius: 999px;
  padding: 5px 12px;
  font-size: 12px;
  font-weight: 600;
  white-space: nowrap;
  flex-shrink: 0;
}

.quiz-badge.right {
  background: rgba(34, 197, 94, 0.12);
  color: #16a34a;
}

.quiz-badge.wrong {
  background: rgba(239, 68, 68, 0.12);
  color: #dc2626;
}

.detail-answer-body {
  display: grid;
  gap: 8px;
}

.detail-row {
  display: grid;
  grid-template-columns: 80px 1fr;
  gap: 8px;
  align-items: baseline;
}

.detail-label {
  font-size: 11px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--text-muted);
}

.detail-value {
  font-size: 13px;
  color: var(--text-primary);
}

.detail-value.correct {
  color: #16a34a;
  font-weight: 500;
}

.detail-feedback {
  margin-top: 4px;
  padding: 10px 14px;
  border-radius: 10px;
  background: rgba(28, 36, 48, 0.04);
  font-size: 13px;
  color: var(--text-secondary);
}

/* Options List */
.options-list {
  display: grid;
  gap: 6px;
}

.options-list > div {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 14px;
  border-radius: 10px;
  border: 1px solid var(--border-light);
  font-size: 13px;
  transition: background 0.15s ease;
}

.option-marker {
  width: 22px;
  height: 22px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 11px;
  font-weight: 700;
  flex-shrink: 0;
  background: rgba(28, 36, 48, 0.06);
  color: var(--text-muted);
}

.option-text {
  flex: 1;
  color: var(--text-primary);
}

.option-icon {
  flex-shrink: 0;
}

.option-icon.correct {
  color: #16a34a;
}

.option-icon.wrong {
  color: #dc2626;
}

.option-correct {
  background: rgba(34, 197, 94, 0.08);
  border-color: rgba(34, 197, 94, 0.25);
}

.option-correct .option-marker {
  background: rgba(34, 197, 94, 0.15);
  color: #16a34a;
}

.option-correct .option-text {
  color: #16a34a;
  font-weight: 500;
}

.option-wrong {
  background: rgba(239, 68, 68, 0.06);
  border-color: rgba(239, 68, 68, 0.2);
}

.option-wrong .option-marker {
  background: rgba(239, 68, 68, 0.12);
  color: #dc2626;
}

.option-wrong .option-text {
  color: #dc2626;
}

.option-neutral {
  background: transparent;
}

@media (max-width: 820px) {
  .history-summary {
    grid-template-columns: 1fr;
  }

  .history-header {
    flex-direction: column;
  }

  .history-actions {
    width: 100%;
  }

  .attempt-head {
    flex-direction: column;
  }

  .attempt-score {
    text-align: left;
  }
}
</style>