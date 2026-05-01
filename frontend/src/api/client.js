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

export async function getCalendarEvents({ start, end, includeBlackboard = true }) {
  const query = new URLSearchParams({
    start,
    end,
    include_blackboard: String(includeBlackboard)
  });
  const response = await fetch(`${API_BASE}/calendar/events?${query.toString()}`);
  return parseJson(response);
}

export async function createCalendarEvent(payload) {
  const response = await fetch(`${API_BASE}/calendar/events`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  });
  return parseJson(response);
}

export async function updateCalendarEvent(eventId, payload) {
  const response = await fetch(`${API_BASE}/calendar/events/${encodeURIComponent(eventId)}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  });
  return parseJson(response);
}

export async function moveCalendarEvent(eventId, payload) {
  const response = await fetch(`${API_BASE}/calendar/events/${encodeURIComponent(eventId)}/move`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  });
  return parseJson(response);
}

export async function deleteCalendarEvent(eventId) {
  const response = await fetch(`${API_BASE}/calendar/events/${encodeURIComponent(eventId)}`, {
    method: "DELETE"
  });
  return parseJson(response);
}

export async function cloneCalendarEvent(eventId) {
  const response = await fetch(`${API_BASE}/calendar/events/${encodeURIComponent(eventId)}/clone`, {
    method: "POST"
  });
  return parseJson(response);
}

export async function syncBlackboardCalendar() {
  const response = await fetch(`${API_BASE}/calendar/sync/blackboard`, {
    method: "POST"
  });
  return parseJson(response);
}

export async function getBlackboardSettings() {
  const response = await fetch(`${API_BASE}/settings/blackboard`);
  return parseJson(response);
}

export async function updateBlackboardSettings(payload) {
  const response = await fetch(`${API_BASE}/settings/blackboard`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  });
  return parseJson(response);
}

export async function testBlackboardSettings(payload) {
  const response = await fetch(`${API_BASE}/settings/blackboard/test`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  });
  return parseJson(response);
}

export async function getBBProfiles() {
  const response = await fetch(`${API_BASE}/settings/blackboard/profiles`);
  return parseJson(response);
}

export async function saveBBProfile(payload) {
  const response = await fetch(`${API_BASE}/settings/blackboard/profiles`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  });
  return parseJson(response);
}

export async function deleteBBProfile(name) {
  const response = await fetch(`${API_BASE}/settings/blackboard/profiles/${encodeURIComponent(name)}`, {
    method: "DELETE"
  });
  return parseJson(response);
}

export async function applyBBProfile(name) {
  const response = await fetch(`${API_BASE}/settings/blackboard/profiles/${encodeURIComponent(name)}/apply`, {
    method: "POST"
  });
  return parseJson(response);
}

export async function getDatabaseOverview() {
  const response = await fetch(`${API_BASE}/database/overview`);
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

export async function getQuiz(quizId) {
  const response = await fetch(`${API_BASE}/quiz/${encodeURIComponent(quizId)}`);
  return parseJson(response);
}

export async function submitQuizAttempt(quizId, payload) {
  const response = await fetch(`${API_BASE}/quiz/${encodeURIComponent(quizId)}/attempts`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  });
  return parseJson(response);
}

export async function getQuizHistory(limit = 5) {
  const response = await fetch(`${API_BASE}/quiz/history?limit=${encodeURIComponent(limit)}`);
  return parseJson(response);
}

async function consumeSSE(response, handlers) {
  if (!response.ok || !response.body) {
    let detail = `Chat request failed with status ${response.status}`;
    try {
      const payload = await response.json();
      detail = payload.detail || payload.error || detail;
    } catch {
      // Ignore parse failure and keep the status-based message.
    }
    throw new Error(detail);
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
      if (eventName === "error") {
        throw new Error(parsed.error || "Chat stream failed.");
      }
      if (eventName === "message") {
        handlers.onChunk?.(parsed.chunk);
      }
      if (eventName === "reasoning") {
        handlers.onReasoning?.(parsed.chunk);
      }
      if (eventName === "approval_required") {
        handlers.onApprovalRequired?.(parsed);
      }
      if (eventName === "tool_events") {
        handlers.onToolEvents?.(parsed.tool_events || []);
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
      if (eventName === "error") {
        throw new Error(parsed.error || "Chat stream failed.");
      }
      if (eventName === "message") handlers.onChunk?.(parsed.chunk);
      if (eventName === "reasoning") handlers.onReasoning?.(parsed.chunk);
      if (eventName === "approval_required") handlers.onApprovalRequired?.(parsed);
      if (eventName === "tool_events") handlers.onToolEvents?.(parsed.tool_events || []);
      if (eventName === "done") handlers.onDone?.(parsed);
    }
  }
}

export async function streamChat(payload, handlers, requestOptions = {}) {
  const response = await fetch(`${API_BASE}/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
    signal: requestOptions.signal
  });
  return consumeSSE(response, handlers);
}

export async function streamApprovalDecision(payload, handlers) {
  const response = await fetch(`${API_BASE}/chat/approval`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  });
  return consumeSSE(response, handlers);
}

// Generic API client for convenience
export const apiClient = {
  async get(endpoint, options = {}) {
    const url = new URL(`${API_BASE}${endpoint}`);
    if (options.params) {
      Object.entries(options.params).forEach(([key, value]) => {
        if (value !== null && value !== undefined) {
          url.searchParams.append(key, value);
        }
      });
    }
    const response = await fetch(url.toString(), {
      method: "GET",
      headers: options.headers || {}
    });
    return { data: await parseJson(response) };
  },

  async post(endpoint, data, options = {}) {
    const url = new URL(`${API_BASE}${endpoint}`);
    if (options.params) {
      Object.entries(options.params).forEach(([key, value]) => {
        if (value !== null && value !== undefined) {
          url.searchParams.append(key, value);
        }
      });
    }
    const response = await fetch(url.toString(), {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...options.headers
      },
      body: data ? JSON.stringify(data) : undefined
    });
    return { data: await parseJson(response) };
  },

  async put(endpoint, data, options = {}) {
    const url = new URL(`${API_BASE}${endpoint}`);
    if (options.params) {
      Object.entries(options.params).forEach(([key, value]) => {
        if (value !== null && value !== undefined) {
          url.searchParams.append(key, value);
        }
      });
    }
    const response = await fetch(url.toString(), {
      method: "PUT",
      headers: {
        "Content-Type": "application/json",
        ...options.headers
      },
      body: data ? JSON.stringify(data) : undefined
    });
    return { data: await parseJson(response) };
  }
};
