<template>
  <section class="calendar-panel">
    <header class="calendar-header">
      <div class="calendar-heading">
        <p class="calendar-kicker">Unified Calendar</p>
        <h2>日程</h2>
        <p>整合 Blackboard 日程和你手动维护的本地事件。</p>
      </div>

      <div class="calendar-toolbar">
        <div class="range-nav">
          <button type="button" class="ghost-btn" @click="shiftRange(-1)">上一段</button>
          <button type="button" class="ghost-btn" @click="jumpToToday">今天</button>
          <button type="button" class="ghost-btn" @click="shiftRange(1)">下一段</button>
        </div>

        <div class="view-switch">
          <button
            v-for="mode in ['day', 'month', 'year']"
            :key="mode"
            type="button"
            :class="['view-btn', { active: viewMode === mode }]"
            @click="viewMode = mode"
          >
            {{ viewLabels[mode] }}
          </button>
        </div>

        <div class="action-row">
          <button type="button" class="ghost-btn" :disabled="syncing" @click="syncBlackboard">
            {{ syncing ? "同步中..." : "同步 Blackboard" }}
          </button>
          <button type="button" class="primary-btn" @click="openCreateModal()">
            新建事件
          </button>
        </div>
      </div>
    </header>

    <div class="calendar-banner">
      <div>
        <strong>{{ rangeLabel }}</strong>
        <span>拖拽本地事件可快速改时间；Blackboard 事件为只读。</span>
      </div>
      <p v-if="statusMessage" :class="['status-chip', statusTone]">{{ statusMessage }}</p>
    </div>

    <section v-if="viewMode === 'month'" class="calendar-surface month-view">
      <div class="weekday-row">
        <span v-for="day in weekdays" :key="day">{{ day }}</span>
      </div>
      <div class="month-grid">
        <article
          v-for="cell in monthCells"
          :key="cell.iso"
          :class="['month-cell', { muted: !cell.inCurrentMonth, today: cell.isToday }]"
          @dblclick="openCreateModal(cell.date)"
          @dragover.prevent
          @drop="handleDateDrop(cell.date)"
        >
          <header class="cell-head">
            <span>{{ cell.day }}</span>
            <button type="button" class="cell-add" @click.stop="openCreateModal(cell.date)">+</button>
          </header>
          <div class="cell-events">
            <button
              v-for="event in eventsForDate(cell.date).slice(0, 4)"
              :key="event.id"
              type="button"
              :draggable="!event.is_read_only"
              :class="['event-pill', event.source, statusClass(event.status), { readonly: event.is_read_only }]"
              @click.stop="openEventModal(event)"
              @dragstart="startDrag(event)"
            >
              <span class="status-dot" />
              <span class="event-time">{{ formatShortTime(event.start_at, event.all_day) }}</span>
              <span class="event-title">{{ event.title }}</span>
            </button>
            <p v-if="eventsForDate(cell.date).length > 4" class="more-text">
              +{{ eventsForDate(cell.date).length - 4 }} more
            </p>
          </div>
        </article>
      </div>
    </section>

    <section v-else-if="viewMode === 'day'" class="calendar-surface day-view">
      <div class="day-side">
        <h3>{{ currentDate.toLocaleDateString("zh-CN", { month: "long", day: "numeric", weekday: "long" }) }}</h3>
        <p>{{ dayEvents.length }} 个事件</p>
        <button
          v-for="event in dayEvents"
          :key="event.id"
          type="button"
          :draggable="!event.is_read_only"
          :class="['agenda-card', event.source, statusClass(event.status), { readonly: event.is_read_only }]"
          @click="openEventModal(event)"
          @dragstart="startDrag(event)"
        >
          <span class="agenda-time">{{ formatDateTimeRange(event) }}</span>
          <strong>{{ event.title }}</strong>
          <em class="status-text">{{ statusLabel(event.status) }}</em>
          <small>{{ event.location || event.description || (event.source === 'blackboard' ? 'Blackboard 事件' : '本地事件') }}</small>
        </button>
      </div>

      <div class="timeline">
        <div
          v-for="hour in hours"
          :key="hour"
          class="timeline-slot"
          @dragover.prevent
          @drop="handleHourDrop(hour)"
        >
          <span class="timeline-label">{{ hour.toString().padStart(2, "0") }}:00</span>
          <div class="timeline-events">
            <button
              v-for="event in hourEvents(hour)"
              :key="`${event.id}-${hour}`"
              type="button"
              :draggable="!event.is_read_only"
              :class="['timeline-event', event.source, statusClass(event.status), { readonly: event.is_read_only }]"
              @click="openEventModal(event)"
              @dragstart="startDrag(event)"
            >
              <strong>{{ event.title }}</strong>
              <em class="status-text">{{ statusLabel(event.status) }}</em>
              <span>{{ formatDateTimeRange(event) }}</span>
            </button>
          </div>
        </div>
      </div>
    </section>

    <section v-else class="calendar-surface year-view">
      <article
        v-for="month in yearMonths"
        :key="month.key"
        class="year-card"
        @click="openMonth(month.date)"
      >
        <header>
          <strong>{{ month.label }}</strong>
          <span>{{ month.count }} 个事件</span>
        </header>
        <div class="year-mini-grid">
          <span v-for="weekday in weekdaysMini" :key="weekday" class="mini-weekday">{{ weekday }}</span>
          <span
            v-for="cell in month.cells"
            :key="cell.iso"
            :class="['mini-day', { muted: !cell.inCurrentMonth, hasEvents: cell.count > 0, today: cell.isToday }]"
          >
            {{ cell.day }}
          </span>
        </div>
      </article>
    </section>

    <div v-if="modalOpen" class="calendar-modal-backdrop" @click.self="closeModal">
      <section class="calendar-modal">
        <header class="modal-head">
          <div>
            <p class="calendar-kicker">{{ modalMode === 'create' ? 'New Event' : modalMode === 'edit' ? 'Edit Event' : 'Event Detail' }}</p>
            <h3>{{ modalMode === "create" ? "新建日程" : modalForm.title || "事件详情" }}</h3>
          </div>
          <button type="button" class="ghost-btn" @click="closeModal">关闭</button>
        </header>

        <form v-if="modalMode !== 'view'" class="modal-form" @submit.prevent="submitModal">
          <label>
            标题
            <input v-model="modalForm.title" type="text" required :disabled="modalEvent?.source === 'blackboard'" />
          </label>
          <div class="field-grid">
            <label>
              开始
              <input v-model="modalForm.start_at" type="datetime-local" required :disabled="modalEvent?.source === 'blackboard'" />
            </label>
            <label>
              结束
              <input v-model="modalForm.end_at" type="datetime-local" required :disabled="modalEvent?.source === 'blackboard'" />
            </label>
          </div>
          <div class="field-grid compact">
            <label>
              地点
              <input v-model="modalForm.location" type="text" placeholder="可选" :disabled="modalEvent?.source === 'blackboard'" />
            </label>
            <label class="checkbox-row">
              <input v-model="modalForm.all_day" type="checkbox" :disabled="modalEvent?.source === 'blackboard'" />
              全天事件
            </label>
          </div>
          <label>
            状态
            <select v-model="modalForm.status">
              <option value="not_started">还没开始</option>
              <option value="pending">进行中 / Pending</option>
              <option value="completed">已完成</option>
            </select>
          </label>
          <label>
            备注
            <textarea v-model="modalForm.description" rows="4" placeholder="补充说明、课程信息、提醒内容..." :disabled="modalEvent?.source === 'blackboard'" />
          </label>

          <div class="modal-actions">
            <button
              v-if="modalMode === 'edit' && modalEvent?.source !== 'blackboard'"
              type="button"
              class="danger-btn"
              :disabled="submitting"
              @click="deleteSelected"
            >
              删除
            </button>
            <button type="submit" class="primary-btn" :disabled="submitting">
              {{ submitting ? "保存中..." : "保存" }}
            </button>
          </div>
        </form>

        <div v-else class="modal-view">
          <div class="detail-grid">
            <div>
              <span class="detail-label">时间</span>
              <strong>{{ formatDateTimeRange(modalEvent) }}</strong>
            </div>
            <div>
              <span class="detail-label">来源</span>
              <strong>{{ modalEvent?.source === "blackboard" ? "Blackboard" : "本地事件" }}</strong>
            </div>
            <div>
              <span class="detail-label">状态</span>
              <strong>{{ statusLabel(modalEvent?.status) }}</strong>
            </div>
            <div v-if="modalEvent?.location">
              <span class="detail-label">地点</span>
              <strong>{{ modalEvent.location }}</strong>
            </div>

          </div>
          <p class="detail-copy">{{ modalEvent?.description || "暂无备注。" }}</p>
          <div class="modal-actions">
            <button
              v-if="modalEvent?.source === 'blackboard'"
              type="button"
              class="ghost-btn"
              @click="switchToEdit"
            >
              更新状态
            </button>
            <button
              v-if="modalEvent?.source === 'blackboard'"
              type="button"
              class="primary-btn"
              :disabled="submitting"
              @click="cloneSelected"
            >
              {{ submitting ? "复制中..." : "复制为本地事件" }}
            </button>
            <button
              v-else
              type="button"
              class="primary-btn"
              @click="switchToEdit"
            >
              编辑事件
            </button>
          </div>
        </div>
      </section>
    </div>
  </section>
</template>

<script setup>
import { computed, onMounted, reactive, ref, watch } from "vue";
import {
  cloneCalendarEvent,
  createCalendarEvent,
  deleteCalendarEvent,
  getCalendarEvents,
  moveCalendarEvent,
  syncBlackboardCalendar,
  updateCalendarEvent
} from "../api/client";

const emit = defineEmits(["close"]);

const weekdays = ["一", "二", "三", "四", "五", "六", "日"];
const weekdaysMini = ["一", "二", "三", "四", "五", "六", "日"];
const viewLabels = { day: "日", month: "月", year: "年" };
const hours = Array.from({ length: 24 }, (_, index) => index);

const loading = ref(false);
const syncing = ref(false);
const submitting = ref(false);
const statusMessage = ref("");
const statusTone = ref("neutral");
const viewMode = ref("month");
const currentDate = ref(new Date());
const events = ref([]);
const modalOpen = ref(false);
const modalMode = ref("create");
const modalEvent = ref(null);
const dragState = ref(null);

const modalForm = reactive({
  title: "",
  start_at: "",
  end_at: "",
  description: "",
  location: "",
  all_day: false,
  status: "not_started"
});

const currentRange = computed(() => {
  if (viewMode.value === "day") {
    return {
      start: startOfDay(currentDate.value),
      end: endOfDay(currentDate.value)
    };
  }
  if (viewMode.value === "year") {
    return {
      start: new Date(currentDate.value.getFullYear(), 0, 1, 0, 0, 0, 0),
      end: new Date(currentDate.value.getFullYear(), 11, 31, 23, 59, 59, 999)
    };
  }
  return {
    start: startOfMonthGrid(currentDate.value),
    end: endOfMonthGrid(currentDate.value)
  };
});

const rangeLabel = computed(() => {
  if (viewMode.value === "day") {
    return currentDate.value.toLocaleDateString("zh-CN", { year: "numeric", month: "long", day: "numeric", weekday: "long" });
  }
  if (viewMode.value === "year") {
    return `${currentDate.value.getFullYear()} 年总览`;
  }
  return currentDate.value.toLocaleDateString("zh-CN", { year: "numeric", month: "long" });
});

const dayEvents = computed(() =>
  events.value
    .filter((event) => eventIntersectsDate(event, currentDate.value))
    .sort((left, right) => new Date(left.start_at) - new Date(right.start_at))
);

const monthCells = computed(() => {
  const start = startOfMonthGrid(currentDate.value);
  return Array.from({ length: 42 }, (_, index) => {
    const date = addDays(start, index);
    return {
      date,
      iso: dateKey(date),
      day: date.getDate(),
      inCurrentMonth: date.getMonth() === currentDate.value.getMonth(),
      isToday: isSameDate(date, new Date())
    };
  });
});

const yearMonths = computed(() =>
  Array.from({ length: 12 }, (_, monthIndex) => {
    const date = new Date(currentDate.value.getFullYear(), monthIndex, 1);
    const cells = buildMonthCells(date).map((cell) => ({
      ...cell,
      count: eventsForDate(cell.date).length
    }));
    return {
      key: `${date.getFullYear()}-${monthIndex + 1}`,
      date,
      label: date.toLocaleDateString("zh-CN", { month: "long" }),
      count: cells.reduce((total, cell) => total + cell.count, 0),
      cells
    };
  })
);

watch(viewMode, () => {
  void fetchEvents();
});

watch(currentRange, () => {
  void fetchEvents();
});

onMounted(() => {
  void fetchEvents();
});

function setStatus(message, tone = "neutral") {
  statusMessage.value = message;
  statusTone.value = tone;
}

async function fetchEvents() {
  loading.value = true;
  try {
    const response = await getCalendarEvents({
      start: currentRange.value.start.toISOString(),
      end: currentRange.value.end.toISOString(),
      includeBlackboard: true
    });
    events.value = response.data?.events || [];
    if (!statusMessage.value) {
      setStatus(`${events.value.length} 个事件`, "neutral");
    }
  } catch (error) {
    setStatus(`加载失败：${error.message}`, "error");
  } finally {
    loading.value = false;
  }
}

function buildMonthCells(date) {
  const start = startOfMonthGrid(date);
  return Array.from({ length: 42 }, (_, index) => {
    const cellDate = addDays(start, index);
    return {
      date: cellDate,
      iso: dateKey(cellDate),
      day: cellDate.getDate(),
      inCurrentMonth: cellDate.getMonth() === date.getMonth(),
      isToday: isSameDate(cellDate, new Date())
    };
  });
}

function eventsForDate(date) {
  return events.value.filter((event) => eventIntersectsDate(event, date));
}

function hourEvents(hour) {
  return dayEvents.value.filter((event) => eventIntersectsHour(event, currentDate.value, hour));
}

function shiftRange(delta) {
  if (viewMode.value === "day") {
    currentDate.value = addDays(currentDate.value, delta);
    return;
  }
  if (viewMode.value === "year") {
    currentDate.value = new Date(currentDate.value.getFullYear() + delta, currentDate.value.getMonth(), 1);
    return;
  }
  currentDate.value = new Date(currentDate.value.getFullYear(), currentDate.value.getMonth() + delta, 1);
}

function jumpToToday() {
  currentDate.value = new Date();
}

function openMonth(date) {
  currentDate.value = new Date(date);
  viewMode.value = "month";
}

function openCreateModal(targetDate = null) {
  modalMode.value = "create";
  modalEvent.value = null;
  const baseStart = targetDate ? new Date(targetDate) : new Date(currentDate.value);
  baseStart.setHours(9, 0, 0, 0);
  const baseEnd = new Date(baseStart);
  baseEnd.setHours(baseStart.getHours() + 1);
  modalForm.title = "";
  modalForm.start_at = toLocalInput(baseStart);
  modalForm.end_at = toLocalInput(baseEnd);
  modalForm.description = "";
  modalForm.location = "";
  modalForm.all_day = false;
  modalForm.status = "not_started";
  modalOpen.value = true;
}

function openEventModal(event) {
  modalEvent.value = event;
  modalMode.value = event.source === "blackboard" ? "view" : "edit";
  modalForm.title = event.title || "";
  modalForm.start_at = toLocalInput(new Date(event.start_at));
  modalForm.end_at = toLocalInput(new Date(event.end_at));
  modalForm.description = event.description || "";
  modalForm.location = event.location || "";
  modalForm.all_day = Boolean(event.all_day);
  modalForm.status = event.status || "not_started";
  modalOpen.value = true;
}

function switchToEdit() {
  if (!modalEvent.value) return;
  modalMode.value = "edit";
  modalForm.title = modalEvent.value.title || "";
  modalForm.start_at = toLocalInput(new Date(modalEvent.value.start_at));
  modalForm.end_at = toLocalInput(new Date(modalEvent.value.end_at));
  modalForm.description = modalEvent.value.description || "";
  modalForm.location = modalEvent.value.location || "";
  modalForm.all_day = Boolean(modalEvent.value.all_day);
  modalForm.status = modalEvent.value.status || "not_started";
  modalOpen.value = true;
}

function closeModal() {
  modalOpen.value = false;
  modalEvent.value = null;
}

async function submitModal() {
  submitting.value = true;
  let payload = {
    title: modalForm.title.trim(),
    start_at: new Date(modalForm.start_at).toISOString(),
    end_at: new Date(modalForm.end_at).toISOString(),
    description: modalForm.description.trim() || null,
    location: modalForm.location.trim() || null,
    all_day: modalForm.all_day,
    timezone: Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC",
    status: modalForm.status
  };
  if (modalMode.value === "edit" && modalEvent.value?.source === "blackboard") {
    payload = { status: modalForm.status };
  }

  try {
    if (modalMode.value === "create") {
      await createCalendarEvent(payload);
      setStatus("已创建本地事件", "success");
    } else if (modalEvent.value) {
      await updateCalendarEvent(modalEvent.value.event_id, payload);
      setStatus("已更新事件", "success");
    }
    closeModal();
    await fetchEvents();
  } catch (error) {
    setStatus(`保存失败：${error.message}`, "error");
  } finally {
    submitting.value = false;
  }
}

async function deleteSelected() {
  if (!modalEvent.value) return;
  submitting.value = true;
  try {
    await deleteCalendarEvent(modalEvent.value.event_id);
    setStatus("已删除事件", "success");
    closeModal();
    await fetchEvents();
  } catch (error) {
    setStatus(`删除失败：${error.message}`, "error");
  } finally {
    submitting.value = false;
  }
}

async function cloneSelected() {
  if (!modalEvent.value) return;
  submitting.value = true;
  try {
    await cloneCalendarEvent(modalEvent.value.event_id);
    setStatus("Blackboard 事件已复制为本地事件", "success");
    closeModal();
    await fetchEvents();
  } catch (error) {
    setStatus(`复制失败：${error.message}`, "error");
  } finally {
    submitting.value = false;
  }
}

async function syncBlackboard() {
  syncing.value = true;
  try {
    const response = await syncBlackboardCalendar();
    const result = response.data || {};
    setStatus(`同步完成：${result.synced || 0} 条，新增 ${result.created || 0} 条`, "success");
    await fetchEvents();
  } catch (error) {
    setStatus(`同步失败：${error.message}`, "error");
  } finally {
    syncing.value = false;
  }
}

function startDrag(event) {
  if (event.is_read_only) return;
  dragState.value = {
    eventId: event.event_id,
    startAt: new Date(event.start_at),
    endAt: new Date(event.end_at)
  };
}

async function handleDateDrop(targetDate) {
  if (!dragState.value) return;
  const sourceStart = dragState.value.startAt;
  const sourceEnd = dragState.value.endAt;
  const durationMs = sourceEnd.getTime() - sourceStart.getTime();
  const nextStart = new Date(targetDate);
  nextStart.setHours(
    sourceStart.getHours(),
    sourceStart.getMinutes(),
    sourceStart.getSeconds(),
    sourceStart.getMilliseconds()
  );
  const nextEnd = new Date(nextStart.getTime() + durationMs);
  await moveDraggedEvent(nextStart, nextEnd);
}

async function handleHourDrop(hour) {
  if (!dragState.value) return;
  const sourceStart = dragState.value.startAt;
  const sourceEnd = dragState.value.endAt;
  const durationMs = sourceEnd.getTime() - sourceStart.getTime();
  const nextStart = new Date(currentDate.value);
  nextStart.setHours(
    hour,
    sourceStart.getMinutes(),
    sourceStart.getSeconds(),
    sourceStart.getMilliseconds()
  );
  const nextEnd = new Date(nextStart.getTime() + durationMs);
  await moveDraggedEvent(nextStart, nextEnd);
}

async function moveDraggedEvent(nextStart, nextEnd) {
  if (!dragState.value) return;
  try {
    await moveCalendarEvent(dragState.value.eventId, {
      start_at: nextStart.toISOString(),
      end_at: nextEnd.toISOString()
    });
    setStatus("已移动事件", "success");
    await fetchEvents();
  } catch (error) {
    setStatus(`移动失败：${error.message}`, "error");
  } finally {
    dragState.value = null;
  }
}

function startOfDay(date) {
  return new Date(date.getFullYear(), date.getMonth(), date.getDate(), 0, 0, 0, 0);
}

function endOfDay(date) {
  return new Date(date.getFullYear(), date.getMonth(), date.getDate(), 23, 59, 59, 999);
}

function startOfMonthGrid(date) {
  const first = new Date(date.getFullYear(), date.getMonth(), 1);
  const mondayIndex = (first.getDay() + 6) % 7;
  return addDays(first, -mondayIndex);
}

function endOfMonthGrid(date) {
  const first = startOfMonthGrid(date);
  const end = addDays(first, 41);
  end.setHours(23, 59, 59, 999);
  return end;
}

function addDays(date, amount) {
  const copy = new Date(date);
  copy.setDate(copy.getDate() + amount);
  return copy;
}

function isSameDate(left, right) {
  return left.getFullYear() === right.getFullYear()
    && left.getMonth() === right.getMonth()
    && left.getDate() === right.getDate();
}

function eventIntersectsDate(event, date) {
  const rangeStart = startOfDay(date);
  const rangeEnd = addDays(rangeStart, 1);
  return eventIntersectsRange(event, rangeStart, rangeEnd);
}

function eventIntersectsHour(event, date, hour) {
  const rangeStart = new Date(date.getFullYear(), date.getMonth(), date.getDate(), hour, 0, 0, 0);
  const rangeEnd = new Date(rangeStart.getTime() + 60 * 60 * 1000);
  return eventIntersectsRange(event, rangeStart, rangeEnd);
}

function eventIntersectsRange(event, rangeStart, rangeEnd) {
  const eventStart = new Date(event.start_at);
  const eventEnd = new Date(event.end_at);
  if (Number.isNaN(eventStart.getTime()) || Number.isNaN(eventEnd.getTime())) {
    return false;
  }
  if (eventEnd.getTime() === eventStart.getTime()) {
    return eventStart >= rangeStart && eventStart < rangeEnd;
  }
  return eventStart < rangeEnd && eventEnd > rangeStart;
}

function dateKey(date) {
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}-${String(date.getDate()).padStart(2, "0")}`;
}

function toLocalInput(date) {
  const local = new Date(date.getTime() - date.getTimezoneOffset() * 60000);
  return local.toISOString().slice(0, 16);
}

function formatShortTime(value, allDay = false) {
  if (allDay) return "全天";
  return new Date(value).toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit" });
}

function formatDateTimeRange(event) {
  if (!event) return "";
  const start = new Date(event.start_at);
  const end = new Date(event.end_at);
  const startLabel = event.all_day
    ? start.toLocaleDateString("zh-CN", { month: "short", day: "numeric" })
    : start.toLocaleString("zh-CN", { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" });
  const endLabel = event.all_day
    ? end.toLocaleDateString("zh-CN", { month: "short", day: "numeric" })
    : end.toLocaleString("zh-CN", { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" });
  return `${startLabel} - ${endLabel}`;
}

function statusLabel(status) {
  if (status === "completed") return "已完成";
  if (status === "pending") return "进行中 / Pending";
  return "还没开始";
}

function statusClass(status) {
  return `status-${status || "not_started"}`;
}
</script>

<style scoped>
.calendar-panel {
  display: flex;
  flex-direction: column;
  flex: 1;
  min-height: 0;
  gap: 20px;
  height: 100%;
  padding: 28px;
  background:
    radial-gradient(circle at top right, rgba(44, 122, 123, 0.12), transparent 28%),
    linear-gradient(180deg, #fcfdfd 0%, #f4f8f8 100%);
  overflow: hidden;
}

.calendar-header,
.calendar-banner,
.calendar-surface,
.calendar-modal {
  border: 1px solid rgba(31, 41, 55, 0.08);
  border-radius: 24px;
  background: rgba(255, 255, 255, 0.92);
  box-shadow: 0 18px 50px rgba(15, 23, 42, 0.06);
}

.calendar-header {
  display: flex;
  justify-content: space-between;
  gap: 20px;
  padding: 24px 26px;
}

.calendar-heading h2,
.modal-head h3 {
  margin: 4px 0 8px;
  font-size: 28px;
  line-height: 1.1;
  color: #132a2a;
}

.calendar-heading p,
.calendar-banner span,
.detail-copy,
.agenda-card small {
  color: #5f7272;
}

.calendar-kicker {
  margin: 0;
  font-size: 12px;
  letter-spacing: 0.18em;
  text-transform: uppercase;
  color: #2c7a7b;
}

.calendar-toolbar,
.range-nav,
.action-row,
.view-switch {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.calendar-toolbar {
  justify-content: flex-end;
}

.ghost-btn,
.primary-btn,
.view-btn,
.cell-add,
.danger-btn {
  border: 0;
  border-radius: 999px;
  cursor: pointer;
  transition: transform 0.18s ease, box-shadow 0.18s ease, background 0.18s ease;
}

.ghost-btn,
.view-btn {
  padding: 10px 16px;
  background: #edf4f3;
  color: #1a3e3e;
}

.primary-btn {
  padding: 10px 18px;
  background: linear-gradient(135deg, #2c7a7b, #215d63);
  color: #fff;
}

.danger-btn {
  padding: 10px 18px;
  background: #fbe7e5;
  color: #9c2f22;
}

.view-btn.active {
  background: #132a2a;
  color: #fff;
}

.ghost-btn:hover,
.primary-btn:hover,
.view-btn:hover,
.cell-add:hover,
.danger-btn:hover {
  transform: translateY(-1px);
}

.calendar-banner {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  align-items: center;
  padding: 16px 22px;
}

.status-chip {
  margin: 0;
  padding: 8px 12px;
  border-radius: 999px;
  font-size: 13px;
}

.status-chip.neutral {
  background: #eff5f4;
  color: #345454;
}

.status-chip.success {
  background: #e4f5ec;
  color: #1d6a44;
}

.status-chip.error {
  background: #fdecea;
  color: #a4392a;
}

.calendar-surface {
  padding: 20px;
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  overflow-y: auto;
}

.weekday-row,
.month-grid,
.year-mini-grid {
  display: grid;
  grid-template-columns: repeat(7, minmax(0, 1fr));
}

.weekday-row {
  margin-bottom: 10px;
  color: #718585;
  font-size: 13px;
  text-align: center;
}

.month-grid {
  flex: 1;
  gap: 10px;
  overflow-y: auto;
  padding-right: 4px;
}

.month-cell {
  min-height: 100px;
  display: flex;
  flex-direction: column;
  padding: 12px;
  border-radius: 18px;
  background: #f9fbfb;
  border: 1px solid rgba(31, 41, 55, 0.06);
}

.month-cell.muted {
  opacity: 0.55;
}

.month-cell.today {
  background: linear-gradient(180deg, #eef8f8 0%, #ffffff 100%);
  border-color: rgba(44, 122, 123, 0.25);
}

.cell-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 10px;
  color: #173232;
}

.cell-add {
  width: 24px;
  height: 24px;
  background: #e6efee;
  color: #2f5656;
}

.cell-events {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.event-pill,
.agenda-card,
.timeline-event {
  border: 0;
  text-align: left;
  cursor: pointer;
  border-radius: 14px;
}

.status-dot {
  width: 8px;
  height: 8px;
  border-radius: 999px;
  flex: 0 0 auto;
  background: currentColor;
}

.status-text {
  font-style: normal;
  font-size: 12px;
  color: inherit;
  opacity: 0.88;
}

.event-pill {
  display: flex;
  gap: 8px;
  align-items: center;
  padding: 8px 10px;
  background: #eff5f4;
  color: #163434;
}

.event-pill.local,
.agenda-card.local,
.timeline-event.local {
  background: linear-gradient(135deg, rgba(44, 122, 123, 0.14), rgba(44, 122, 123, 0.06));
}

.event-pill.blackboard,
.agenda-card.blackboard,
.timeline-event.blackboard {
  background: linear-gradient(135deg, rgba(245, 176, 65, 0.22), rgba(245, 176, 65, 0.1));
}

.status-not_started {
  color: #4a6470;
}

.status-pending {
  color: #9a6700;
}

.status-completed {
  color: #1f7a4c;
}

.event-pill.readonly,
.agenda-card.readonly,
.timeline-event.readonly {
  cursor: default;
}

.event-time,
.agenda-time {
  font-size: 12px;
  color: #5d7373;
}

.event-title {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.more-text {
  margin: 4px 0 0;
  font-size: 12px;
  color: #6f8282;
}

.day-view {
  display: grid;
  grid-template-columns: 320px minmax(0, 1fr);
  gap: 18px;
}

.day-side {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.day-side h3 {
  margin: 0;
  font-size: 24px;
  color: #183535;
}

.day-side p {
  margin: 0 0 8px;
  color: #6b7f7f;
}

.agenda-card {
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding: 14px;
}

.timeline {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.timeline-slot {
  display: grid;
  grid-template-columns: 72px minmax(0, 1fr);
  gap: 14px;
  min-height: 54px;
  padding: 10px 0;
  border-bottom: 1px solid rgba(31, 41, 55, 0.06);
}

.timeline-label {
  color: #607676;
  font-size: 13px;
}

.timeline-events {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}

.timeline-event {
  display: flex;
  flex-direction: column;
  gap: 4px;
  min-width: 200px;
  padding: 10px 12px;
}

.year-view {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 16px;
}

.year-card {
  padding: 16px;
  border-radius: 20px;
  background: #f9fbfb;
  cursor: pointer;
  border: 1px solid rgba(31, 41, 55, 0.06);
}

.year-card header {
  display: flex;
  justify-content: space-between;
  margin-bottom: 14px;
  color: #183535;
}

.year-card header span {
  color: #6a8080;
  font-size: 12px;
}

.year-mini-grid {
  gap: 6px;
  font-size: 12px;
}

.mini-weekday {
  text-align: center;
  color: #8ba0a0;
}

.mini-day {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 28px;
  border-radius: 10px;
  color: #2d4848;
}

.mini-day.muted {
  opacity: 0.35;
}

.mini-day.hasEvents {
  background: rgba(44, 122, 123, 0.13);
}

.mini-day.today {
  outline: 1px solid rgba(44, 122, 123, 0.45);
}

.calendar-modal-backdrop {
  position: fixed;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px;
  background: rgba(15, 23, 42, 0.36);
  backdrop-filter: blur(6px);
  z-index: 1000;
}

.calendar-modal {
  width: min(720px, 100%);
  max-height: 90vh;
  overflow-y: auto;
  padding: 24px;
}

.modal-head,
.modal-actions,
.detail-grid,
.field-grid {
  display: flex;
  gap: 14px;
}

.modal-head,
.modal-actions {
  justify-content: space-between;
  align-items: center;
}

.modal-form,
.modal-view {
  display: flex;
  flex-direction: column;
  gap: 16px;
  margin-top: 18px;
}

.modal-form label,
.field-grid label {
  display: flex;
  flex-direction: column;
  gap: 8px;
  color: #284646;
}

.modal-form input,
.modal-form textarea,
.modal-form select {
  border: 1px solid rgba(31, 41, 55, 0.12);
  border-radius: 14px;
  padding: 12px 14px;
  font: inherit;
  background: #fbfdfd;
}

.field-grid {
  align-items: flex-end;
}

.field-grid > label {
  flex: 1;
}

.field-grid.compact {
  align-items: center;
}

.checkbox-row {
  flex-direction: row !important;
  align-items: center;
  gap: 10px !important;
  padding: 12px 14px;
  border: 1px solid rgba(31, 41, 55, 0.12);
  border-radius: 14px;
  background: #fbfdfd;
}

.detail-grid {
  flex-wrap: wrap;
  margin-bottom: 12px;
}

.detail-grid > div {
  min-width: 180px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.detail-label {
  color: #6b8080;
  font-size: 12px;
  text-transform: uppercase;
  letter-spacing: 0.08em;
}

@media (max-width: 1180px) {
  .calendar-header,
  .calendar-banner {
    flex-direction: column;
    align-items: flex-start;
  }

  .day-view,
  .year-view {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 760px) {
  .calendar-panel {
    padding: 18px;
  }

  .month-grid {
    gap: 8px;
  }

  .month-cell {
    min-height: 110px;
    padding: 10px;
  }

  .calendar-modal {
    padding: 18px;
  }

  .field-grid,
  .modal-head,
  .modal-actions {
    flex-direction: column;
    align-items: stretch;
  }
}
</style>
