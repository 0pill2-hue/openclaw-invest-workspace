const state = {
  activeTab: "ops",
  ops: null,
  stage1: null,
  stage2: null,
  pollingTimer: null,
};

const qs = (sel) => document.querySelector(sel);

function formatNumber(v) {
  if (v === null || v === undefined || v === "") return "-";
  const num = Number(v);
  if (Number.isNaN(num)) return String(v);
  return num.toLocaleString("ko-KR");
}

function formatDate(v) {
  if (!v) return "-";
  const d = new Date(v);
  if (Number.isNaN(d.getTime())) return String(v);
  return d.toLocaleString("ko-KR");
}

function ratioPct(used, total, pct) {
  if (pct !== null && pct !== undefined && pct !== "") {
    const n = Number(pct);
    if (!Number.isNaN(n)) return Math.max(0, Math.min(100, n));
  }
  const u = Number(used);
  const t = Number(total);
  if (!Number.isNaN(u) && !Number.isNaN(t) && t > 0) {
    return Math.max(0, Math.min(100, (u / t) * 100));
  }
  return 0;
}

async function fetchJson(url) {
  const res = await fetch(url, { cache: "no-store" });
  if (!res.ok) throw new Error(`${url} (${res.status})`);
  return res.json();
}

function el(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined && text !== null) node.textContent = text;
  return node;
}

function setUpdatedAt(ts) {
  qs("#last-updated").textContent = `last updated ${formatDate(ts)}`;
}

function setGlobalStatus(ops) {
  const badge = qs("#global-status");
  const guards = ops?.guards || {};
  const states = Object.values(guards).map((g) => String(g?.state || "").toLowerCase());
  const hasAlert = states.some((s) => ["fail", "warning", "alert"].includes(s));
  if (hasAlert) {
    badge.textContent = "degraded";
    badge.className = "pill state-badge warning";
  } else {
    badge.textContent = "healthy";
    badge.className = "pill state-badge ok";
  }
}

function clearNode(node) {
  while (node.firstChild) node.removeChild(node.firstChild);
}

function renderTaskList(containerId, countId, tasks) {
  const root = qs(containerId);
  clearNode(root);
  qs(countId).textContent = String(tasks.length);

  if (!tasks.length) {
    root.appendChild(el("div", "meta-line", "항목 없음"));
    return;
  }

  tasks.forEach((task) => {
    const card = el("button", "task-card");
    card.type = "button";

    const top = el("div", "task-top");
    top.appendChild(el("span", `lamp ${task.lamp || "white"}`));
    top.appendChild(el("div", "task-title", task.title || task.ticketId));
    card.appendChild(top);

    card.appendChild(el("div", "task-ticket", task.ticketId || "-"));
    card.appendChild(el("div", "meta-line", `status: ${task.status || "-"} · priority: ${task.priority || "-"}`));

    const chips = el("div", "meta-chip-row");
    chips.appendChild(el("span", "meta-chip", task.assignee ? `assignee ${task.assignee}` : "assignee -"));
    chips.appendChild(el("span", "meta-chip", task.owner ? `owner ${task.owner}` : "owner -"));
    if (task.reviewStatus) chips.appendChild(el("span", "meta-chip", `review ${task.reviewStatus}`));
    card.appendChild(chips);

    card.addEventListener("click", () => loadTaskDetail(task.ticketId));
    root.appendChild(card);
  });
}

function progressBlock(title, used, total, pct, source, extraText) {
  const wrap = el("div", "progress-block");
  const top = el("div", "progress-row");
  top.appendChild(el("span", "", title));
  const summary = `${formatNumber(used)} / ${formatNumber(total)} (${ratioPct(used, total, pct).toFixed(1)}%)`;
  top.appendChild(el("span", "", summary));
  wrap.appendChild(top);

  const track = el("div", "progress-track");
  const fill = el("div", "progress-fill");
  fill.style.width = `${ratioPct(used, total, pct)}%`;
  track.appendChild(fill);
  wrap.appendChild(track);

  if (extraText) wrap.appendChild(el("div", "meta-line", extraText));
  if (source) wrap.appendChild(el("div", "path-line", `source: ${source}`));
  return wrap;
}

function renderBrainCards(brains) {
  const root = qs("#brain-cards");
  clearNode(root);

  const main = brains?.main || {};
  const local = brains?.local || {};

  const mainCard = el("div", "status-card");
  const head = el("div", "status-head");
  head.appendChild(el("h3", "", "메인브레인 상태"));
  mainCard.appendChild(head);

  const c = main.context || {};
  mainCard.appendChild(progressBlock("Context", c.used, c.total, c.pct, c.source, ""));

  const q5 = main.quota5h || {};
  mainCard.appendChild(progressBlock("Quota 5h", q5.used, q5.total, null, q5.source, `remaining ${formatNumber(q5.remaining)} · reset ${formatDate(q5.resetAt)}`));

  const qw = main.quotaWeek || {};
  mainCard.appendChild(progressBlock("Quota Week", qw.used, qw.total, null, qw.source, `remaining ${formatNumber(qw.remaining)} · reset ${formatDate(qw.resetAt)}`));
  root.appendChild(mainCard);

  const localCard = el("div", "status-card");
  const lhead = el("div", "status-head");
  lhead.appendChild(el("h3", "", "로컬브레인 상태"));
  localCard.appendChild(lhead);
  const lc = local.context || {};
  localCard.appendChild(progressBlock("Context", lc.used, lc.total, lc.pct, lc.source, ""));
  root.appendChild(localCard);
}

function guardBadgeClass(state) {
  const s = String(state || "unavailable").toLowerCase();
  if (["fail", "warning", "alert"].includes(s)) return "state-badge warning";
  if (["ok", "idle", "running"].includes(s)) return "state-badge ok";
  return "state-badge";
}

function renderGuardCards(guards) {
  const root = qs("#guard-cards");
  clearNode(root);

  const labels = {
    mainBrainGuard: "메인브레인가드",
    localBrainGuard: "로컬브레인가드",
    watchdog: "watchdog",
    autoDispatch: "auto-dispatch",
  };

  Object.entries(labels).forEach(([key, label]) => {
    const g = guards?.[key] || {};
    const card = el("div", "status-card");
    const head = el("div", "status-head");
    head.appendChild(el("h3", "", label));
    head.appendChild(el("span", guardBadgeClass(g.state), g.state || "unavailable"));
    card.appendChild(head);
    card.appendChild(el("div", "meta-line", g.text || ""));
    card.appendChild(el("div", "meta-line", `updated ${formatDate(g.updatedAt)}`));
    if (g.source) card.appendChild(el("div", "path-line", `source: ${g.source}`));
    root.appendChild(card);
  });
}

function renderOps(data) {
  state.ops = data;
  setGlobalStatus(data);
  setUpdatedAt(data.updatedAt);

  const tasks = data.tasks || {};
  renderTaskList("#ops-main-tasks", "#main-task-count", tasks.mainInProgress || []);
  renderTaskList("#ops-subagent-tasks", "#subagent-task-count", tasks.subagentInProgress || []);
  renderTaskList("#ops-remaining-tasks", "#remaining-task-count", tasks.remaining || []);

  renderBrainCards(data.brains || {});
  renderGuardCards(data.guards || {});
}

function detailField(label, value) {
  const card = el("div", "detail-field");
  card.appendChild(el("div", "label", label));
  card.appendChild(el("div", "", value === null || value === undefined || value === "" ? "-" : String(value)));
  return card;
}

function renderDetail(kicker, title, fields, sections = []) {
  qs("#detail-kicker").textContent = kicker;
  qs("#detail-title").textContent = title;

  const body = qs("#detail-body");
  body.classList.remove("empty");
  clearNode(body);

  if (fields?.length) {
    const grid = el("div", "detail-grid");
    fields.forEach((f) => grid.appendChild(detailField(f.label, f.value)));
    body.appendChild(grid);
  }

  sections.forEach((section) => {
    const sec = el("div", "detail-section");
    sec.appendChild(el("div", "label", section.label));
    if (section.code) {
      sec.appendChild(el("pre", "code-block", section.value || "-"));
    } else {
      sec.appendChild(el("div", "", section.value || "-"));
    }
    body.appendChild(sec);
  });
}

async function loadTaskDetail(ticketId) {
  try {
    const data = await fetchJson(`/api/tasks/${encodeURIComponent(ticketId)}`);
    const fields = [
      { label: "ticket_id", value: data.ticketId },
      { label: "status", value: data.status },
      { label: "priority", value: data.priority },
      { label: "bucket", value: data.bucket },
      { label: "assignee", value: data.assignee },
      { label: "owner", value: data.owner },
      { label: "review", value: data.reviewStatus },
      { label: "current_goal", value: data.currentGoal },
      { label: "last_completed_step", value: data.lastCompletedStep },
      { label: "next_action", value: data.nextAction },
      { label: "latest_proof", value: data.latestProof },
      { label: "touched_paths", value: (data.touchedPaths || []).join(", ") },
    ];

    const sections = [
      { label: "scope", value: data.scope || "-", code: false },
      { label: "report_preview", value: data.reportPreview || "-", code: true },
    ];

    renderDetail("TASK DETAIL", `${data.ticketId} · ${data.title || ""}`, fields, sections);
  } catch (err) {
    renderDetail("TASK DETAIL", ticketId, [{ label: "error", value: String(err?.message || err) }], []);
  }
}

function renderDatasetCards(containerId, datasets, sourceLabel) {
  const root = qs(containerId);
  clearNode(root);

  if (!datasets?.length) {
    root.appendChild(el("div", "meta-line", "데이터셋 없음"));
    return;
  }

  datasets.forEach((d) => {
    const card = el("button", "dataset-card");
    card.type = "button";

    const top = el("div", "dataset-top");
    top.appendChild(el("div", "dataset-title", d.name || d.id));
    card.appendChild(top);

    card.appendChild(el("div", "meta-line", `${formatNumber(d.count)} ${d.countUnit || ""}`));
    card.appendChild(el("div", "path-line", d.sourcePath || "-"));

    const stats = el("div", "dataset-stats");
    const statA = el("div", "dataset-stat");
    statA.appendChild(el("div", "label", "시작"));
    statA.appendChild(el("div", "", d.startDate || "-"));
    stats.appendChild(statA);

    const statB = el("div", "dataset-stat");
    statB.appendChild(el("div", "label", "종료"));
    statB.appendChild(el("div", "", d.endDate || "-"));
    stats.appendChild(statB);

    const statC = el("div", "dataset-stat");
    statC.appendChild(el("div", "label", "마지막 실행"));
    statC.appendChild(el("div", "", formatDate(d.lastSyncAt || d.lastRunAt)));
    stats.appendChild(statC);

    const statD = el("div", "dataset-stat");
    statD.appendChild(el("div", "label", "source"));
    statD.appendChild(el("div", "", sourceLabel));
    stats.appendChild(statD);

    card.appendChild(stats);

    card.addEventListener("click", () => {
      const detailsObj = {
        ...(d.details || {}),
        configProvenance: d.configProvenance || null,
      };
      renderDetail(
        sourceLabel,
        `${d.name || d.id}`,
        [
          { label: "id", value: d.id },
          { label: "count", value: `${formatNumber(d.count)} ${d.countUnit || ""}` },
          { label: "startDate", value: d.startDate },
          { label: "endDate", value: d.endDate },
          { label: "lastRun", value: d.lastSyncAt || d.lastRunAt },
          { label: "sourcePath", value: d.sourcePath },
        ],
        [
          {
            label: "details",
            value: JSON.stringify(detailsObj, null, 2),
            code: true,
          },
        ]
      );
    });

    root.appendChild(card);
  });
}

function renderStage1(data) {
  state.stage1 = data;
  setUpdatedAt(data.updatedAt);
  renderDatasetCards("#stage1-grid", data.datasets || [], "Stage1");
}

function renderStage2(data) {
  state.stage2 = data;
  setUpdatedAt(data.updatedAt);
  renderDatasetCards("#stage2-grid", data.datasets || [], "Stage2");
}

function showError(message) {
  renderDetail("ERROR", "데이터 로드 실패", [{ label: "message", value: message }], []);
}

async function refresh() {
  try {
    const ops = await fetchJson("/api/ops/overview");
    renderOps(ops);
  } catch (err) {
    showError(String(err?.message || err));
    return;
  }

  try {
    if (state.activeTab === "stage1") {
      const data = await fetchJson("/api/stage1/summary");
      renderStage1(data);
    }
    if (state.activeTab === "stage2") {
      const data = await fetchJson("/api/stage2/summary");
      renderStage2(data);
    }
  } catch (err) {
    showError(String(err?.message || err));
  }
}

function activateTab(tabName) {
  state.activeTab = tabName;
  document.querySelectorAll(".tab").forEach((tab) => {
    tab.classList.toggle("is-active", tab.dataset.tab === tabName);
  });
  document.querySelectorAll(".tab-panel").forEach((panel) => {
    panel.classList.toggle("is-active", panel.dataset.panel === tabName);
  });

  if (tabName === "stage1" && !state.stage1) {
    fetchJson("/api/stage1/summary").then(renderStage1).catch((e) => showError(String(e?.message || e)));
  }
  if (tabName === "stage2" && !state.stage2) {
    fetchJson("/api/stage2/summary").then(renderStage2).catch((e) => showError(String(e?.message || e)));
  }
}

function init() {
  document.querySelectorAll(".tab").forEach((tab) => {
    tab.addEventListener("click", () => activateTab(tab.dataset.tab));
  });

  qs("#detail-close").addEventListener("click", () => {
    qs("#detail-kicker").textContent = "DETAIL";
    qs("#detail-title").textContent = "항목을 선택하세요";
    const body = qs("#detail-body");
    body.className = "detail-body empty";
    body.textContent = "좌측 카드나 데이터셋을 클릭하면 상세가 표시됩니다.";
  });

  refresh();
  state.pollingTimer = setInterval(refresh, 4000);
}

init();
