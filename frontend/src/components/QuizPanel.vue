<template>
  <section class="quiz-panel">
    <header class="quiz-header">
      <div>
        <p class="eyebrow">Interactive Quiz</p>
        <h3>{{ quiz.title }}</h3>
        <p>{{ quiz.topic }}</p>
      </div>
      <button :disabled="submitting" @click="submitAnswers">
        {{ submitting ? "Submitting..." : "Submit Quiz" }}
      </button>
    </header>

    <section v-if="submitError" class="quiz-error">
      <strong>Submission failed</strong>
      <p>{{ submitError }}</p>
    </section>

    <article
      v-for="(question, index) in quiz.questions"
      :key="question.id"
      class="quiz-question"
    >
      <div class="quiz-question-head">
        <strong>Q{{ index + 1 }}</strong>
        <span>{{ labelForType(question.question_type) }}</span>
      </div>
      <p class="quiz-prompt">{{ question.prompt }}</p>

      <div v-if="question.question_type === 'single_choice'" class="quiz-options">
        <label v-for="option in question.options" :key="option" class="quiz-option">
          <input v-model="answers[question.id]" type="radio" :name="question.id" :value="option" />
          <span>{{ option }}</span>
        </label>
      </div>

      <div v-else-if="question.question_type === 'true_false'" class="quiz-options">
        <label v-for="option in ['True', 'False']" :key="option" class="quiz-option">
          <input v-model="answers[question.id]" type="radio" :name="question.id" :value="option" />
          <span>{{ option }}</span>
        </label>
      </div>

      <textarea
        v-else
        v-model="answers[question.id]"
        rows="4"
        class="quiz-textarea"
        placeholder="Write your answer here..."
      />

      <div v-if="resultMap[question.id]" class="quiz-result">
        <span :class="['quiz-badge', resultMap[question.id].is_correct === false ? 'wrong' : 'right']">
          {{ scoreLabel(resultMap[question.id]) }}
        </span>
        <p><strong>Feedback:</strong> {{ resultMap[question.id].feedback }}</p>
        <p><strong>Reference:</strong> {{ resultMap[question.id].correct_answer }}</p>
      </div>
    </article>

    <footer v-if="attemptResult" class="quiz-summary">
      <strong>Score: {{ attemptResult.score }} / {{ attemptResult.total_points }}</strong>
      <p>{{ attemptResult.summary }}</p>
    </footer>
  </section>
</template>

<script setup>
import { computed, reactive, ref } from "vue";
import { submitQuizAttempt } from "../api/client";

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
  if (type === "single_choice") return "Single Choice";
  if (type === "true_false") return "True / False";
  return "Short Answer";
}

function scoreLabel(result) {
  if (result.is_correct === true) return "Correct";
  if (result.is_correct === false) return "Incorrect";
  return `${result.score} / ${result.max_score}`;
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
  padding: 18px;
  border-radius: 20px;
  background: rgba(255, 255, 255, 0.88);
  border: 1px solid rgba(31, 111, 120, 0.14);
}

.quiz-header {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  align-items: start;
}

.quiz-header h3,
.quiz-header p {
  margin: 0;
}

.quiz-header button {
  border: 0;
  border-radius: 999px;
  padding: 10px 16px;
  background: var(--accent);
  color: white;
  font-weight: 700;
  cursor: pointer;
}

.quiz-question {
  display: grid;
  gap: 10px;
  padding: 14px;
  border-radius: 18px;
  background: rgba(243, 239, 229, 0.65);
}

.quiz-error {
  display: grid;
  gap: 6px;
  padding: 14px;
  border-radius: 16px;
  background: rgba(239, 68, 68, 0.1);
  color: #991b1b;
}

.quiz-error p,
.quiz-error strong {
  margin: 0;
}

.quiz-question-head {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: center;
}

.quiz-question-head span {
  font-size: 0.82rem;
  color: var(--muted);
}

.quiz-prompt {
  margin: 0;
  font-weight: 600;
}

.quiz-options {
  display: grid;
  gap: 8px;
}

.quiz-option {
  display: flex;
  gap: 10px;
  align-items: start;
}

.quiz-textarea {
  width: 100%;
  box-sizing: border-box;
  resize: vertical;
  padding: 12px 14px;
  border-radius: 14px;
  border: 1px solid rgba(28, 36, 48, 0.14);
  font: inherit;
}

.quiz-result {
  display: grid;
  gap: 6px;
  margin-top: 6px;
}

.quiz-result p {
  margin: 0;
}

.quiz-badge {
  justify-self: start;
  border-radius: 999px;
  padding: 6px 12px;
  font-size: 0.82rem;
  font-weight: 700;
}

.quiz-badge.right {
  background: rgba(34, 197, 94, 0.12);
  color: #15803d;
}

.quiz-badge.wrong {
  background: rgba(239, 68, 68, 0.12);
  color: #b91c1c;
}

.quiz-summary {
  display: grid;
  gap: 6px;
  padding: 14px;
  border-radius: 16px;
  background: rgba(31, 111, 120, 0.08);
}

.quiz-summary p,
.quiz-summary strong {
  margin: 0;
}
</style>
