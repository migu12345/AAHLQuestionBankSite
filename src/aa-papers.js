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
  const m = String(paperLabel || "").match(/^(May|November)\s+(\d{4})\s+Paper\s+([123])(?:\s+(TZ\d))?\s+(HL|SL)$/i);
  if (!m) {
    return null;
  }
  return {
    session: m[1],
    year: Number(m[2]),
    paperNo: Number(m[3]),
    timezone: m[4] || "No TZ",
    level: m[5].toUpperCase(),
    paperLabel,
  };
}

async function loadData() {
  const res = await fetch("/data/processed/questions.json");
  if (!res.ok) {
    throw new Error(`HTTP ${res.status}`);
  }
  const payload = await res.json();
  const questions = Array.isArray(payload.questions) ? payload.questions : [];

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

  state.papers = [...byPaper.values()].sort((a, b) => {
    if (a.year !== b.year) {
      return b.year - a.year;
    }
    if (a.session !== b.session) {
      return a.session === "May" ? -1 : 1;
    }
    if (a.timezone !== b.timezone) {
      return a.timezone.localeCompare(b.timezone);
    }
    return a.paperNo - b.paperNo;
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

function openPaper(paper) {
  const params = new URLSearchParams();
  params.set("level", paper.level);
  params.set("paperType", `Paper ${paper.paperNo}`);
  params.set("paper", paper.paperLabel);
  window.location.href = `aa-bank.html?${params.toString()}`;
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
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "paper-open-btn";
    btn.innerHTML = `<strong>${paper.session} ${paper.year} ${paper.timezone}</strong><span>Paper ${paper.paperNo} • ${paper.level}</span>`;
    btn.addEventListener("click", () => openPaper(paper));
    paperButtons.appendChild(btn);
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
