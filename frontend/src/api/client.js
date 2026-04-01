const API_BASE = "http://127.0.0.1:8000/api";

async function parseJson(response) {
  if (!response.ok) {
    let detail = `Request failed with status ${response.status}`;
    try {
      const payload = await response.json();
      detail = payload.detail || payload.error || detail;
    } catch {
      // Ignore parse failure and fall back to status-only messaging.
    }
    throw new Error(detail);
  }
  return response.json();
}

export async function getHealth() {
  const response = await fetch(`${API_BASE}/health`);
  return parseJson(response);
}

export async function getLLMSettings() {
  const response = await fetch(`${API_BASE}/settings/llm`);
  return parseJson(response);
}

export async function updateLLMSettings(payload) {
  const response = await fetch(`${API_BASE}/settings/llm`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  });
  return parseJson(response);
}

export async function testLLMSettings(payload) {
  const response = await fetch(`${API_BASE}/settings/llm/test`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  });
  return parseJson(response);
}

export async function getLLMProfiles() {
  const response = await fetch(`${API_BASE}/settings/llm/profiles`);
  return parseJson(response);
}

export async function saveLLMProfile(payload) {
  const response = await fetch(`${API_BASE}/settings/llm/profiles`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  });
  return parseJson(response);
}

export async function deleteLLMProfile(name) {
  const response = await fetch(`${API_BASE}/settings/llm/profiles/${encodeURIComponent(name)}`, {
    method: "DELETE"
  });
  return parseJson(response);
}

export async function applyLLMProfile(name) {
  const response = await fetch(`${API_BASE}/settings/llm/profiles/${encodeURIComponent(name)}/apply`, {
    method: "POST"
  });
  return parseJson(response);
}

export async function getCourses() {
  const response = await fetch(`${API_BASE}/blackboard/courses`);
  return parseJson(response);
}

export async function createEmailDraft(payload) {
  const response = await fetch(`${API_BASE}/email/draft`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  });
  return parseJson(response);
}

export async function streamChat(payload, handlers) {
  const response = await fetch(`${API_BASE}/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  });

  if (!response.ok || !response.body) {
    throw new Error(`Chat request failed with status ${response.status}`);
  }

  const decoder = new TextDecoder();
  const reader = response.body.getReader();
  let buffer = "";

  while (true) {
    const { value, done } = await reader.read();
    if (done) {
      break;
    }

    buffer += decoder.decode(value, { stream: true }).replace(/\r\n/g, "\n");
    const events = buffer.split("\n\n");
    buffer = events.pop() ?? "";

    for (const rawEvent of events) {
      const lines = rawEvent
        .split("\n")
        .map((line) => line.trimEnd())
        .filter((line) => line.length > 0);
      let eventName = "message";
      let data = "";

      for (const line of lines) {
        if (line.startsWith(":")) {
          continue;
        }
        if (line.startsWith("event:")) {
          eventName = line.slice(6).trim();
        }
        if (line.startsWith("data:")) {
          data += line.slice(5).trim();
        }
      }

      if (!data) {
        continue;
      }

      const parsed = JSON.parse(data);
      if (eventName === "message") {
        handlers.onChunk?.(parsed.chunk);
      }
      if (eventName === "done") {
        handlers.onDone?.(parsed);
      }
    }
  }

  const trailing = buffer.trim();
  if (trailing) {
    const lines = trailing.split("\n").map((line) => line.trimEnd());
    let eventName = "message";
    let data = "";
    for (const line of lines) {
      if (line.startsWith(":") || !line) continue;
      if (line.startsWith("event:")) eventName = line.slice(6).trim();
      if (line.startsWith("data:")) data += line.slice(5).trim();
    }
    if (data) {
      const parsed = JSON.parse(data);
      if (eventName === "message") handlers.onChunk?.(parsed.chunk);
      if (eventName === "done") handlers.onDone?.(parsed);
    }
  }
}
