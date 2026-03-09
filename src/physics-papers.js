const state = {
  papers: [],
};

const levelFilter = document.getElementById("paperLevelFilter");
const yearFilter = document.getElementById("paperYearFilter");
const sessionFilter = document.getElementById("paperSessionFilter");
const tzFilter = document.getElementById("paperTzFilter");
const selectionLabel = document.getElementById("paperSelectionLabel");
const paperButtons = document.getElementById("paperButtons");

function inferLevel(q) {
  if (q.level === "SL" || q.level === "HL") {
    return q.level;
  }
  const sourceFile = (q.source && q.source.paper_file ? q.source.paper_file : "").toLowerCase();
  if (sourceFile.includes("_sl")) {
    return "SL";
  }
  return "HL";
}

function parsePaperLabel(paperLabel) {
  const m = String(paperLabel || "").match(
    /^(May|November)\s+(\d{4})(?:\s+Physics)?\s+Paper\s+([123](?:[AB])?)(?:\s+(TZ\d))?\s+(HL|SL)$/i
  );
  if (!m) {
    return null;
  }
  return {
    session: m[1],
    year: Number(m[2]),
    paperCode: String(m[3]).toUpperCase(),
    paperNo: Number(String(m[3]).replace(/[^0-9]/g, "")),
    timezone: m[4] || "NTZ",
    level: m[5].toUpperCase(),
    paperLabel,
  };
}

function normalizeTimezone(value) {
  const tz = String(value || "").trim().toUpperCase();
  if (!tz || tz === "NO TZ") {
    return "NTZ";
  }
  return tz;
}

function fileNameFromPath(pathText) {
  const text = String(pathText || "").trim();
  if (!text) {
    return "";
  }
  const parts = text.split("/");
  return parts[parts.length - 1] || "";
}

async function loadData() {
  const [res, manualRes] = await Promise.all([
    window.assetFetch("/data/physics/processed/questions.json"),
    window.assetFetch("/data/physics/processed/manual_papers.json").catch(() => null),
  ]);
  if (!res.ok) {
    throw new Error(`HTTP ${res.status}`);
  }
  const payload = await res.json();
  const questions = Array.isArray(payload.questions) ? payload.questions : [];
  const manualPayload = manualRes && manualRes.ok ? await manualRes.json() : { papers: [] };
  const manualPapers = Array.isArray(manualPayload.papers) ? manualPayload.papers : [];

  const byPaper = new Map();

  questions.forEach((q) => {
    const parsed = parsePaperLabel(q.paper);
    if (!parsed) {
      return;
    }
    parsed.level = inferLevel(q);
    const key = parsed.paperLabel;
    if (!byPaper.has(key)) {
      byPaper.set(key, parsed);
    }
  });

  manualPapers.forEach((paper) => {
    const label = String(paper.paperLabel || "").trim();
    if (!label) {
      return;
    }
    const parsed = parsePaperLabel(label);
    const paperCode = String(paper.paperCode || parsed?.paperCode || "").toUpperCase();
    const paperNo = Number(String(paperCode).replace(/[^0-9]/g, "")) || Number(paper.paperNo || parsed?.paperNo || 0);
    byPaper.set(label, {
      session: String(paper.session || parsed?.session || "").trim(),
      year: Number(paper.year || parsed?.year || 0),
      paperCode,
      paperNo,
      timezone: normalizeTimezone(paper.timezone || parsed?.timezone || "NTZ"),
      level: String(paper.level || parsed?.level || "").toUpperCase(),
      paperLabel: label,
      paperFile: fileNameFromPath(paper.paper_path || ""),
      paperPath: String(paper.paper_path || "").trim(),
      hasMarkscheme: paper.has_markscheme !== false,
      isManual: true,
    });
  });

  state.papers = [...byPaper.values()].filter((p) => p.level && p.year && p.session && p.paperCode).sort((a, b) => {
    if (a.year !== b.year) {
      return b.year - a.year;
    }
    if (a.session !== b.session) {
      return a.session === "May" ? -1 : 1;
    }
    if (a.timezone !== b.timezone) {
      return a.timezone.localeCompare(b.timezone);
    }
    if (a.paperNo !== b.paperNo) {
      return a.paperNo - b.paperNo;
    }
    return a.paperCode.localeCompare(b.paperCode);
  });
}

function setOptions(selectEl, values, placeholder) {
  selectEl.innerHTML = "";
  const defaultOption = document.createElement("option");
  defaultOption.value = "";
  defaultOption.textContent = placeholder;
  selectEl.appendChild(defaultOption);
  values.forEach((value) => {
    const opt = document.createElement("option");
    opt.value = String(value);
    opt.textContent = String(value);
    selectEl.appendChild(opt);
  });
}

function filteredPapers() {
  const level = levelFilter.value;
  const year = yearFilter.value ? Number(yearFilter.value) : null;
  const session = sessionFilter.value;
  const timezone = tzFilter.value;

  return state.papers.filter((p) => {
    const levelMatch = !level || p.level === level;
    const yearMatch = !year || p.year === year;
    const sessionMatch = !session || p.session === session;
    const tzMatch = !timezone || p.timezone === timezone;
    return levelMatch && yearMatch && sessionMatch && tzMatch;
  });
}

function refreshYearOptions() {
  const level = levelFilter.value;
  const years = [...new Set(state.papers.filter((p) => !level || p.level === level).map((p) => p.year))].sort((a, b) => b - a);
  const previous = yearFilter.value;
  setOptions(yearFilter, years, "Choose year");
  if (years.some((y) => String(y) === previous)) {
    yearFilter.value = previous;
  }
}

function refreshSessionOptions() {
  const level = levelFilter.value;
  const year = yearFilter.value ? Number(yearFilter.value) : null;
  const sessions = [
    ...new Set(
      state.papers
        .filter((p) => (!level || p.level === level) && (!year || p.year === year))
        .map((p) => p.session)
    ),
  ];
  const previous = sessionFilter.value;
  setOptions(sessionFilter, sessions, "Choose session");
  if (sessions.includes(previous)) {
    sessionFilter.value = previous;
  }
}

function refreshTimezoneOptions() {
  const level = levelFilter.value;
  const year = yearFilter.value ? Number(yearFilter.value) : null;
  const session = sessionFilter.value;
  const timezones = [
    ...new Set(
      state.papers
        .filter((p) => (!level || p.level === level) && (!year || p.year === year) && (!session || p.session === session))
        .map((p) => p.timezone)
    ),
  ].sort((a, b) => a.localeCompare(b));

  const previous = tzFilter.value;
  setOptions(tzFilter, timezones, "Choose timezone");
  if (timezones.includes(previous)) {
    tzFilter.value = previous;
  }
}

function getExamDurationMinutes(level, paperCode, year) {
  const lvl = String(level || "").toUpperCase();
  const code = String(paperCode || "").toUpperCase();
  const y = Number(year);
  const isNewSyllabus = Number.isFinite(y) && y >= 2025;

  if (isNewSyllabus) {
    if (lvl === "SL") {
      if (code === "1A" || code === "1B") {
        return 90;
      }
      if (code === "2") {
        return 90;
      }
      return null;
    }
    if (lvl === "HL") {
      if (code === "1A" || code === "1B") {
        return 120;
      }
      if (code === "2") {
        return 150;
      }
      return null;
    }
    return null;
  }

  if (lvl === "SL") {
    if (code === "1") {
      return 45;
    }
    if (code === "2") {
      return 75;
    }
    if (code === "3") {
      return 60;
    }
    return null;
  }
  if (lvl === "HL") {
    if (code === "1") {
      return 60;
    }
    if (code === "2") {
      return 135;
    }
    if (code === "3") {
      return 75;
    }
  }
  return null;
}

function buildBaseParams(paper) {
  const params = new URLSearchParams();
  params.set("bundle", "1");
  params.set("level", paper.level);
  params.set("year", String(paper.year));
  params.set("session", paper.session);
  params.set("tz", paper.timezone === "NTZ" ? "No TZ" : paper.timezone);
  params.set("paperNo", String(paper.paperNo));
  params.set("paperCode", paper.paperCode);
  return params;
}

function openPaperInExamMode(paper) {
  const duration = getExamDurationMinutes(paper.level, paper.paperCode, paper.year);
  const params = buildBaseParams(paper);
  if (paper.isManual && paper.paperFile) {
    params.set("sourcePaper", paper.paperFile);
    if (paper.paperPath) {
      params.set("sourcePaperPath", paper.paperPath);
    }
    if (paper.hasMarkscheme === false) {
      params.set("noMs", "1");
    }
  }
  if (duration) {
    params.set("exam", "1");
    params.set("durationMin", String(duration));
  }
  window.location.href = `physics/index.html?${params.toString()}`;
}

function renderPaperButtons() {
  paperButtons.innerHTML = "";
  const items = filteredPapers();

  const level = levelFilter.value || "any level";
  const year = yearFilter.value || "any year";
  const session = sessionFilter.value || "any session";
  const tz = tzFilter.value || "any timezone";
  selectionLabel.textContent = `Showing ${items.length} paper(s) for ${level} | ${year} | ${session} | ${tz}`;

  if (items.length === 0) {
    const msg = document.createElement("p");
    msg.className = "count-line";
    msg.textContent = "No papers match this combination yet.";
    paperButtons.appendChild(msg);
    return;
  }

  items.forEach((paper) => {
    const wrapper = document.createElement("article");
    wrapper.className = "paper-open-card";

    const head = document.createElement("p");
    head.className = "paper-open-head";
    head.textContent = `${paper.session} ${paper.year} ${paper.timezone}`;

    const sub = document.createElement("p");
    sub.className = "paper-open-sub";
    sub.textContent = `Paper ${paper.paperCode} • ${paper.level}`;

    const actions = document.createElement("div");
    actions.className = "paper-open-actions";

    const examBtn = document.createElement("button");
    examBtn.type = "button";
    examBtn.className = "paper-exam-btn";
    const duration = getExamDurationMinutes(paper.level, paper.paperCode, paper.year);
    if (duration) {
      examBtn.textContent = `Start exam mode (${duration}m)`;
      examBtn.addEventListener("click", () => openPaperInExamMode(paper));
    } else {
      examBtn.textContent = "Exam mode unavailable";
      examBtn.disabled = true;
    }

    if ((paper.paperCode === "1A" || paper.paperCode === "1B") && paper.year >= 2025) {
      const note = document.createElement("p");
      note.className = "paper-open-note";
      note.textContent = "Duration uses official Paper 1 total time (Paper 1A + 1B).";
      wrapper.appendChild(note);
    } else if (paper.hasMarkscheme === false) {
      const note = document.createElement("p");
      note.className = "paper-open-note";
      note.textContent = "No markscheme available";
      wrapper.appendChild(note);
    }

    actions.appendChild(examBtn);
    wrapper.appendChild(head);
    wrapper.appendChild(sub);
    wrapper.appendChild(actions);
    paperButtons.appendChild(wrapper);
  });
}

function bindEvents() {
  levelFilter.addEventListener("change", () => {
    refreshYearOptions();
    refreshSessionOptions();
    refreshTimezoneOptions();
    renderPaperButtons();
  });

  yearFilter.addEventListener("change", () => {
    refreshSessionOptions();
    refreshTimezoneOptions();
    renderPaperButtons();
  });

  sessionFilter.addEventListener("change", () => {
    refreshTimezoneOptions();
    renderPaperButtons();
  });

  tzFilter.addEventListener("change", () => {
    renderPaperButtons();
  });
}

async function start() {
  try {
    await loadData();
    setOptions(levelFilter, ["SL", "HL"], "Choose level");
    refreshYearOptions();
    refreshSessionOptions();
    refreshTimezoneOptions();
    bindEvents();
    renderPaperButtons();
  } catch (error) {
    paperButtons.innerHTML = `<p>Failed to load papers: ${error.message}</p>`;
  }
}

start();
