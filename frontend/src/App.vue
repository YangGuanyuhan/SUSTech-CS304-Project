<template>
  <main class="shell">
    <section class="hero">
      <div>
        <p class="eyebrow">Software Engineering Project</p>
        <h1>Student Productivity Agent</h1>
        <p>
          Blackboard mock mode, email confirmation flow, memory persistence, and streaming chat
          are wired into one inspection UI.
        </p>
      </div>
      <aside class="status-card">
        <span>Status</span>
        <strong>{{ status }}</strong>
        <div class="status-actions">
          <button :disabled="checking" @click="checkHealth">
            {{ checking ? "Checking..." : "Check Backend" }}
          </button>
          <button class="secondary" @click="settingsOpen = true">Configure APIs</button>
        </div>
      </aside>
    </section>
    <ChatWindow />

    <div v-if="settingsOpen" class="overlay" @click.self="settingsOpen = false">
      <div class="overlay-panel">
        <SettingsPanel @close="settingsOpen = false" />
      </div>
    </div>
  </main>
</template>

<script setup>
import { onMounted, ref } from "vue";
import ChatWindow from "./components/ChatWindow.vue";
import SettingsPanel from "./components/SettingsPanel.vue";
import { getHealth } from "./api/client";

const status = ref("Unknown");
const checking = ref(false);
const settingsOpen = ref(false);

async function checkHealth() {
  checking.value = true;
  try {
    const response = await getHealth();
    status.value = response.data?.status === "ok" ? "Backend healthy" : "Unexpected response";
  } catch (error) {
    status.value = `Unavailable: ${error.message}`;
  } finally {
    checking.value = false;
  }
}

onMounted(() => {
  checkHealth();
});
</script>

<style>
:root {
  color-scheme: light;
  --bg: #f3efe5;
  --ink: #1c2430;
  --accent: #1f6f78;
  --card: rgba(255, 255, 255, 0.82);
  --muted: #54606e;
}

body {
  margin: 0;
  font-family: "IBM Plex Sans", "Noto Sans", sans-serif;
  background:
    radial-gradient(circle at top left, rgba(31, 111, 120, 0.2), transparent 30%),
    linear-gradient(160deg, var(--bg), #efe3c5);
  color: var(--ink);
}

.shell {
  min-height: 100vh;
  padding: 40px 20px;
}

.hero {
  max-width: 960px;
  margin: 0 auto 24px;
  display: grid;
  grid-template-columns: 1.5fr 0.8fr;
  gap: 20px;
  align-items: stretch;
}

.hero h1 {
  margin: 0 0 8px;
  font-family: "Space Grotesk", "IBM Plex Sans", sans-serif;
  font-size: clamp(2rem, 4vw, 3.4rem);
}

.hero p {
  margin: 0;
  max-width: 60ch;
  color: var(--muted);
}

.eyebrow {
  margin-bottom: 10px;
  text-transform: uppercase;
  letter-spacing: 0.14em;
  font-size: 0.78rem;
  color: var(--accent);
}

.status-card {
  padding: 20px;
  border-radius: 24px;
  background: rgba(28, 36, 48, 0.92);
  color: white;
  display: grid;
  gap: 10px;
  align-content: start;
}

.status-card span {
  text-transform: uppercase;
  letter-spacing: 0.12em;
  font-size: 0.78rem;
  opacity: 0.7;
}

.status-card strong {
  font-size: 1.3rem;
}

.status-card button {
  justify-self: start;
  border: 0;
  border-radius: 999px;
  padding: 10px 16px;
  background: #f0b429;
  color: #1c2430;
  font-weight: 700;
  cursor: pointer;
}

.status-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}

.status-card button.secondary {
  background: rgba(255, 255, 255, 0.15);
  color: white;
}

.overlay {
  position: fixed;
  inset: 0;
  background: rgba(28, 36, 48, 0.48);
  backdrop-filter: blur(8px);
  padding: 24px;
  overflow: auto;
}

.overlay-panel {
  max-width: 1040px;
  margin: 32px auto;
}

@media (max-width: 700px) {
  .hero {
    grid-template-columns: 1fr;
  }
}
</style>
