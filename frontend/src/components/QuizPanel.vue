<template>
  <section class="quiz-panel">
    <header class="quiz-header">
      <div class="quiz-title-area">
        <p class="eyebrow">互动测验</p>
        <h3>{{ quiz.title }}</h3>
        <p class="quiz-topic">{{ quiz.topic }}</p>
      </div>
      <button class="submit-btn" :disabled="submitting" @click="submitAnswers">
        {{ submitting ? '提交中...' : '提交测验' }}
      </button>
    </header>

    <section v-if="submitError" class="quiz-error">
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <circle cx="12" cy="12" r="10"/>
        <line x1="12" y1="8" x2="12" y2="12"/>
        <line x1="12" y1="16" x2="12.01" y2="16"/>
      </svg>
      <div>
        <strong>提交失败</strong>
        <p>{{ submitError }}</p>
      </div>
    </section>

    <div class="questions-list">
      <article
        v-for="(question, index) in quiz.questions"
        :key="question.id"
        class="quiz-question"
      >
        <div class="quiz-question-head">
          <div class="question-badge">
            <strong>Q{{ index + 1 }}</strong>
            <span>{{ labelForType(question.question_type) }}</span>
          </div>
        </div>
        <div class="markdown-body quiz-prompt" v-html="renderMarkdown(question.prompt)" />

        <!-- Single Choice -->
        <div v-if="question.question_type === 'single_choice'" class="quiz-options">
          <label
            v-for="option in question.options"
            :key="option"
            :class="['quiz-option', { selected: answers[question.id] === option }]"
          >
            <input v-model="answers[question.id]" type="radio" :name="question.id" :value="option" />
            <span class="option-indicator"></span>
            <span class="option-text markdown-body" v-html="renderMarkdown(option)" />
          </label>
        </div>

        <!-- True/False -->
        <div v-else-if="question.question_type === 'true_false'" class="quiz-options true-false">
          <label :class="['quiz-option', { selected: answers[question.id] === 'True' }]">
            <input v-model="answers[question.id]" type="radio" :name="question.id" value="True" />
            <span class="option-indicator"></span>
            <span class="option-text">正确</span>
          </label>
          <label :class="['quiz-option', { selected: answers[question.id] === 'False' }]">
            <input v-model="answers[question.id]" type="radio" :name="question.id" value="False" />
            <span class="option-indicator"></span>
            <span class="option-text">错误</span>
          </label>
        </div>

        <!-- Short Answer -->
        <textarea
          v-else
          v-model="answers[question.id]"
          rows="3"
          class="quiz-textarea"
          placeholder="在这里写下你的答案..."
        />

        <!-- Result -->
        <div v-if="resultMap[question.id]" class="quiz-result">
          <span :class="['quiz-badge', isResultCorrect(resultMap[question.id]) ? 'right' : 'wrong']">
            <svg v-if="isResultCorrect(resultMap[question.id])" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
              <polyline points="20 6 9 17 4 12"/>
            </svg>
            <svg v-else width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
              <line x1="18" y1="6" x2="6" y2="18"/>
              <line x1="6" y1="6" x2="18" y2="18"/>
            </svg>
            {{ scoreLabel(resultMap[question.id]) }}
          </span>
          <div class="feedback markdown-body"><strong>反馈：</strong><span v-html="renderMarkdown(resultMap[question.id].feedback)" /></div>
          <div class="reference markdown-body"><strong>正确答案：</strong><span v-html="renderMarkdown(resultMap[question.id].correct_answer)" /></div>
        </div>
      </article>
    </div>

    <!-- Summary -->
    <footer v-if="attemptResult" class="quiz-summary">
      <div class="score-display">
        <span class="score-label">得分</span>
        <strong class="score-value">{{ attemptResult.score }} / {{ attemptResult.total_points }}</strong>
      </div>
      <p>{{ attemptResult.summary }}</p>
    </footer>
  </section>
</template>

<script setup>
import { computed, reactive, ref } from "vue";
import { submitQuizAttempt } from "../api/client";
import { renderMarkdown } from "../utils/markdown.js";

const props = defineProps({
  quiz: {
    type: Object,
    required: true
  }
});

const answers = reactive(
  Object.fromEntries((props.quiz.questions || []).map((question) => [question.id, ""]))
);
const submitting = ref(false);
const attemptResult = ref(null);
const submitError = ref("");

const resultMap = computed(() =>
  Object.fromEntries((attemptResult.value?.answers || []).map((answer) => [answer.question_id, answer]))
);

function labelForType(type) {
  if (type === "single_choice") return "单选题";
  if (type === "true_false") return "判断题";
  return "简答题";
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

async function submitAnswers() {
  submitting.value = true;
  submitError.value = "";
  try {
    const response = await submitQuizAttempt(props.quiz.id, {
      answers: props.quiz.questions.map((question) => ({
        question_id: question.id,
        answer: answers[question.id] || ""
      }))
    });
    attemptResult.value = response.data;
  } catch (error) {
    submitError.value = error.message;
  } finally {
    submitting.value = false;
  }
}
</script>

<style scoped>
.quiz-panel {
  display: grid;
  gap: 16px;
  margin-top: 16px;
  padding: 20px;
  border-radius: 20px;
  background: white;
  border: 1px solid var(--border-light);
  box-shadow: 0 4px 16px var(--shadow-sm);
}

.quiz-header {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  align-items: flex-start;
}

.quiz-title-area h3 {
  margin: 4px 0 4px;
  font-family: var(--font-heading);
  font-size: 18px;
  color: var(--text-primary);
}

.quiz-topic {
  margin: 0;
  font-size: 13px;
  color: var(--text-muted);
}

.submit-btn {
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

.submit-btn:hover {
  background: #EA580C;
  transform: translateY(-1px);
}

.submit-btn:disabled {
  opacity: 0.6;
  cursor: wait;
  transform: none;
}

.quiz-error {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  padding: 14px 16px;
  border-radius: 14px;
  background: rgba(239, 68, 68, 0.08);
  color: #dc2626;
}

.quiz-error strong {
  display: block;
  margin-bottom: 4px;
}

.quiz-error p {
  margin: 0;
  font-size: 13px;
}

.questions-list {
  display: grid;
  gap: 16px;
}

.quiz-question {
  display: grid;
  gap: 12px;
  padding: 16px;
  border-radius: 16px;
  background: var(--bg-main);
}

.quiz-question-head {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: center;
}

.question-badge {
  display: flex;
  align-items: center;
  gap: 8px;
}

.question-badge strong {
  font-size: 14px;
  color: var(--accent-orange);
}

.question-badge span {
  font-size: 11px;
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.quiz-prompt {
  margin: 0;
  font-size: 14px;
  font-weight: 500;
  color: var(--text-primary);
  line-height: 1.5;
}

.quiz-options {
  display: grid;
  gap: 8px;
}

.quiz-options.true-false {
  grid-template-columns: 1fr 1fr;
}

.quiz-option {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 16px;
  border-radius: 12px;
  background: white;
  border: 1px solid var(--border-light);
  cursor: pointer;
  transition: all 0.2s ease;
}

.quiz-option:hover {
  border-color: var(--accent-orange);
}

.quiz-option.selected {
  border-color: var(--accent-orange);
  background: var(--accent-orange-subtle);
}

.quiz-option input {
  display: none;
}

.option-indicator {
  width: 20px;
  height: 20px;
  border-radius: 50%;
  border: 2px solid var(--border-default);
  position: relative;
  flex-shrink: 0;
  transition: all 0.2s ease;
}

.quiz-option.selected .option-indicator {
  border-color: var(--accent-orange);
}

.quiz-option.selected .option-indicator::after {
  content: '';
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  width: 10px;
  height: 10px;
  border-radius: 50%;
  background: var(--accent-orange);
}

.option-text {
  font-size: 13px;
  color: var(--text-primary);
}

.quiz-textarea {
  width: 100%;
  box-sizing: border-box;
  resize: vertical;
  padding: 14px 16px;
  border-radius: 14px;
  border: 1px solid var(--border-light);
  background: white;
  font-size: 14px;
  line-height: 1.5;
  transition: all 0.2s ease;
}

.quiz-textarea:focus {
  outline: none;
  border-color: var(--accent-orange);
  box-shadow: 0 0 0 4px var(--accent-orange-subtle);
}

.quiz-result {
  display: grid;
  gap: 8px;
  margin-top: 8px;
  padding-top: 12px;
  border-top: 1px solid var(--border-light);
}

.quiz-badge {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  border-radius: 999px;
  padding: 6px 14px;
  font-size: 12px;
  font-weight: 600;
}

.quiz-badge.right {
  background: rgba(34, 197, 94, 0.12);
  color: #16a34a;
}

.quiz-badge.wrong {
  background: rgba(239, 68, 68, 0.12);
  color: #dc2626;
}

.feedback, .reference {
  margin: 0;
  font-size: 13px;
  color: var(--text-secondary);
}

.quiz-summary {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 16px;
  padding: 16px 20px;
  border-radius: 16px;
  background: var(--accent-orange-subtle);
}

.score-display {
  display: flex;
  flex-direction: column;
}

.score-label {
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.1em;
  color: var(--text-muted);
}

.score-value {
  font-size: 24px;
  font-family: var(--font-heading);
  color: var(--accent-orange);
}

.quiz-summary p {
  margin: 0;
  font-size: 13px;
  color: var(--text-secondary);
}

.markdown-body :deep(p) {
  margin: 0 0 8px;
}

.markdown-body :deep(p:last-child) {
  margin-bottom: 0;
}

.markdown-body :deep(ul),
.markdown-body :deep(ol) {
  margin: 0 0 8px 16px;
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
  margin: 0 0 8px;
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
  color: var(--accent-orange);
}

@media (max-width: 600px) {
  .quiz-header {
    flex-direction: column;
  }

  .quiz-options.true-false {
    grid-template-columns: 1fr;
  }
}
</style>