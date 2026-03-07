const state = {
  papers: [],
};

const levelFilter = document.getElementById("physicsLevelFilter");
const paperFilter = document.getElementById("physicsPaperFilter");
const tzFilter = document.getElementById("physicsTzFilter");
const selectionLabel = document.getElementById("physicsSelectionLabel");
const paperButtons = document.getElementById("physicsPaperButtons");

function sortPaperCode(a, b) {
  const order = { "1A": 1, "1B": 2, "2": 3 };
  return (order[a] || 99) - (order[b] || 99);
}

async function loadData() {
  const res = await fetch("/data/physics/processed/manual_papers.json");
  if (!res.ok) {
    throw new Error(`HTTP ${res.status}`);
  }
  const payload = await res.json();
  const papers = Array.isArray(payload.papers) ? payload.papers : [];

  state.papers = papers.sort((a, b) => {
    if (a.year !== b.year) {
      return Number(b.year) - Number(a.year);
    }
    if (a.timezone !== b.timezone) {
      return String(a.timezone || "").localeCompare(String(b.timezone || ""));
    }
    if (a.paperCode !== b.paperCode) {
      return sortPaperCode(a.paperCode, b.paperCode);
    }
    return String(a.level || "").localeCompare(String(b.level || ""));
  });
}

function setOptions(selectEl, values, placeholder) {
  selectEl.innerHTML = "";
  const defaultOption = document.createElement("option");
  defaultOption.value = "";
  defaultOption.textContent = placeholder;
  selectEl.appendChild(defaultOption);

  values.forEach((value) => {
    const option = document.createElement("option");
    option.value = value;
    option.textContent = value;
    selectEl.appendChild(option);
  });
}

function hydrateFilters() {
  const levels = [...new Set(state.papers.map((p) => String(p.level || "")).filter(Boolean))].sort();
  const paperCodes = [...new Set(state.papers.map((p) => String(p.paperCode || "")).filter(Boolean))].sort(sortPaperCode);
  const timezones = [...new Set(state.papers.map((p) => String(p.timezone || "")).filter(Boolean))].sort();

  setOptions(levelFilter, levels, "All levels");
  setOptions(paperFilter, paperCodes, "All papers");
  setOptions(tzFilter, timezones, "All timezones");
}

function filteredPapers() {
  const level = levelFilter.value;
  const paperCode = paperFilter.value;
  const timezone = tzFilter.value;

  return state.papers.filter((p) => {
    const levelMatch = !level || p.level === level;
    const paperMatch = !paperCode || p.paperCode === paperCode;
    const tzMatch = !timezone || p.timezone === timezone;
    return levelMatch && paperMatch && tzMatch;
  });
}

function openPdf(path) {
  if (!path) {
    return;
  }
  window.open(`/data/${path}`, "_blank", "noopener,noreferrer");
}

function renderPapers() {
  const items = filteredPapers();
  paperButtons.innerHTML = "";
  selectionLabel.textContent = `Showing ${items.length} paper(s)`;

  if (items.length === 0) {
    const msg = document.createElement("p");
    msg.className = "count-line";
    msg.textContent = "No papers match this filter combination.";
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

    const openPaperBtn = document.createElement("button");
    openPaperBtn.type = "button";
    openPaperBtn.className = "paper-open-btn";
    openPaperBtn.textContent = "Open paper";
    openPaperBtn.addEventListener("click", () => openPdf(paper.paper_path));

    const openMsBtn = document.createElement("button");
    openMsBtn.type = "button";
    openMsBtn.className = "paper-open-btn";
    if (paper.markscheme_path) {
      openMsBtn.textContent = "Open markscheme";
      openMsBtn.addEventListener("click", () => openPdf(paper.markscheme_path));
    } else {
      openMsBtn.textContent = "No markscheme";
      openMsBtn.disabled = true;
    }

    actions.appendChild(openPaperBtn);
    actions.appendChild(openMsBtn);
    wrapper.appendChild(head);
    wrapper.appendChild(sub);
    wrapper.appendChild(actions);
    paperButtons.appendChild(wrapper);
  });
}

function bindEvents() {
  levelFilter.addEventListener("change", renderPapers);
  paperFilter.addEventListener("change", renderPapers);
  tzFilter.addEventListener("change", renderPapers);
}

async function init() {
  try {
    await loadData();
    hydrateFilters();
    bindEvents();
    renderPapers();
  } catch (err) {
    selectionLabel.textContent = `Failed to load physics papers: ${err.message}`;
  }
}

init();
