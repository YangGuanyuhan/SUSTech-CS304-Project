<template>
  <div class="email-preview-card">
    <div class="email-field">
      <span class="label">To:</span>
      <span>{{ to }}</span>
    </div>
    <div class="email-field">
      <span class="label">Subject:</span>
      <span>{{ subject }}</span>
    </div>
    <pre class="email-body">{{ body }}</pre>
  </div>
</template>

<script setup>
defineProps({
  to: { type: String, required: true },
  subject: { type: String, required: true },
  body: { type: String, required: true },
});
</script>

<style scoped>
.email-preview-card {
  margin-top: 10px;
  border: 1px solid var(--border-color, #e0e0e0);
  border-radius: 8px;
  padding: 12px 14px;
  background: var(--surface-color, #fafafa);
}

.email-field {
  display: flex;
  gap: 8px;
  margin-bottom: 6px;
  font-size: 14px;
  line-height: 1.4;
}

.email-field .label {
  font-weight: 600;
  color: var(--text-secondary, #666);
  min-width: 60px;
}

.email-body {
  margin: 8px 0 0;
  padding: 10px;
  background: var(--bg-color, #fff);
  border-radius: 6px;
  font-family: inherit;
  font-size: 14px;
  line-height: 1.6;
  white-space: pre-wrap;
  word-break: break-word;
  max-height: 200px;
  overflow-y: auto;
}
</style>
