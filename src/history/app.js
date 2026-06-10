const state = {
  allQuestions: [],
  filteredQuestions: [],
  visibleCount: 0,
  userActions: {},
};
const PAGE_SIZE = 20;
const USER_ACTIONS_KEY = "history_bank_user_actions_v1";

const paperTypeFilter = document.getElementById("paperTypeFilter");
const topicFilter = document.getElementById("topicFilter");
const sectionFilter = document.getElementById("sectionFilter");
const paperFilter = document.getElementById("paperFilter");
const savedFilter = document.getElementById("savedFilter");
const searchInput = document.getElementById("searchInput");
const searchToggle = document.getElementById("searchToggle");
const heroSearch = document.getElementById("heroSearch");
const questionList = document.getElementById("questionList");
const resultCount = document.getElementById("resultCount");
const questionTemplate = document.getElementById("questionTemplate");
const loadMoreWrap = document.getElementById("loadMoreWrap");
const loadMoreBtn = document.getElementById("loadMoreBtn");

function loadUserActions() {
  try {
    const raw = window.localStorage.getItem(USER_ACTIONS_KEY);
    state.userActions = raw ? JSON.parse(raw) : {};
  } catch (_e) {
    state.userActions = {};
  }
}

function persistUserActions() {
  try {
    window.localStorage.setItem(USER_ACTIONS_KEY, JSON.stringify(state.userActions));
  } catch (_e) {}
}

function getUserAction(qid) {
  return state.userActions[qid] || { saved: false, done: false };
}

async function loadData() {
  const res = await window.assetFetch("/data/history/processed/questions.json");
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  state.allQuestions = await res.json();
}

function topicLabel(q) {
  if (q.paper_type === "Paper 2") return q.topic || "";
  if (q.paper_type === "Paper 3") return q.region ? `History of ${q.region}` : "";
  if (q.paper_type === "Paper 1") return q.topic || "";
  return q.topic || "";
}

function hydrateFilters() {
  // Topic / Region filter — built from Paper 2 topics and Paper 3 regions + Paper 1 subjects
  const topics = [
    ...new Set(state.allQuestions.map((q) => topicLabel(q)).filter(Boolean)),
  ].sort((a, b) => {
    // P2 topics sort by numeric prefix; others alphabetically
    const na = parseInt(a) || 999;
    const nb = parseInt(b) || 999;
    if (na !== nb) return na - nb;
    return a.localeCompare(b);
  });

  topics.forEach((t) => {
    const opt = document.createElement("option");
    opt.value = t;
    opt.textContent = t;
    topicFilter.appendChild(opt);
  });

  updateSectionOptions();
  updatePaperOptions();
}

function updateSectionOptions() {
  const selectedPaperType = paperTypeFilter.value;
  const selectedTopic = topicFilter.value;
  sectionFilter.innerHTML = '<option value="">All sections</option>';

  let pool = state.allQuestions;
  if (selectedPaperType) pool = pool.filter((q) => q.paper_type === selectedPaperType);
  if (selectedTopic) pool = pool.filter((q) => topicLabel(q) === selectedTopic);

  const sections = [
    ...new Set(
      pool
        .map((q) => q.section || (q.paper_type === "Paper 1" ? q.topic : null))
        .filter(Boolean)
    ),
  ].sort();

  sections.forEach((s) => {
    const opt = document.createElement("option");
    opt.value = s;
    opt.textContent = s;
    sectionFilter.appendChild(opt);
  });
}

function updatePaperOptions() {
  const selectedPaperType = paperTypeFilter.value;
  const selectedTopic = topicFilter.value;
  paperFilter.innerHTML = '<option value="">All papers</option>';

  let pool = state.allQuestions;
  if (selectedPaperType) pool = pool.filter((q) => q.paper_type === selectedPaperType);
  if (selectedTopic) pool = pool.filter((q) => topicLabel(q) === selectedTopic);

  const papers = [...new Set(pool.map((q) => q.session).filter(Boolean))].sort((a, b) => {
    // Sort by year desc, then session
    const [sa, ya] = a.split(" ");
    const [sb, yb] = b.split(" ");
    if (ya !== yb) return parseInt(yb) - parseInt(ya);
    return sa.localeCompare(sb);
  });

  papers.forEach((p) => {
    const opt = document.createElement("option");
    opt.value = p;
    opt.textContent = p;
    paperFilter.appendChild(opt);
  });
}

function applyFilters() {
  const pt = paperTypeFilter.value;
  const topic = topicFilter.value;
  const section = sectionFilter.value;
  const paper = paperFilter.value;
  const saved = savedFilter.value;
  const q = searchInput.value.trim().toLowerCase();

  state.filteredQuestions = state.allQuestions.filter((item) => {
    if (pt && item.paper_type !== pt) return false;
    if (topic && topicLabel(item) !== topic) return false;
    if (section) {
      const sec = item.section || (item.paper_type === "Paper 1" ? item.topic : null) || "";
      if (sec !== section) return false;
    }
    if (paper && item.session !== paper) return false;

    const ua = getUserAction(item.id);
    if (saved === "saved" && !ua.saved) return false;
    if (saved === "done" && !ua.done) return false;

    if (q) {
      const haystack = [
        item.question_text || "",
        item.paper || "",
        item.topic || "",
        item.section || "",
        item.region || "",
        item.paper_type || "",
        String(item.question_number || ""),
      ]
        .join(" ")
        .toLowerCase();
      if (!haystack.includes(q)) return false;
    }

    return true;
  });

  state.visibleCount = 0;
  renderQuestions(true);
  updateResultCount();
}

function updateResultCount() {
  const total = state.filteredQuestions.length;
  const shown = Math.min(state.visibleCount, total);
  resultCount.textContent = `Showing ${shown} of ${total} question${total !== 1 ? "s" : ""}`;
}

function renderQuestions(reset) {
  if (reset) {
    questionList.innerHTML = "";
  }

  const batch = state.filteredQuestions.slice(
    state.visibleCount,
    state.visibleCount + PAGE_SIZE
  );

  if (batch.length === 0 && state.visibleCount === 0) {
    questionList.innerHTML = "<p>No questions match the current filters.</p>";
    loadMoreWrap.hidden = true;
    return;
  }

  batch.forEach((q) => {
    const card = questionTemplate.content.cloneNode(true);
    const article = card.querySelector("article");

    // Meta line
    const metaParts = [q.paper];
    if (q.tz) metaParts.push(q.tz);
    if (q.marks) metaParts.push(`[${q.marks} marks]`);
    article.querySelector(".meta").textContent = metaParts.join(" · ");

    // Tags
    const tagsEl = article.querySelector(".card-tags");
    const addTag = (text, cls) => {
      const span = document.createElement("span");
      span.className = `tag${cls ? " " + cls : ""}`;
      span.textContent = text;
      tagsEl.appendChild(span);
    };

    addTag(q.paper_type);
    if (q.paper_type === "Paper 2" && q.topic) addTag(q.topic);
    if (q.paper_type === "Paper 3" && q.region) addTag(`History of ${q.region}`);
    if (q.paper_type === "Paper 1" && q.topic) addTag(q.topic);
    if (q.section) addTag(q.section, "tag-subtle");
    addTag(`Q${q.question_number}`);

    // Question text
    article.querySelector(".question-text-body").textContent = q.question_text || "";

    // Save / Done buttons
    const ua = getUserAction(q.id);
    const saveBtn = article.querySelector(".save-btn");
    const doneBtn = article.querySelector(".done-btn");

    if (ua.saved) {
      saveBtn.classList.add("active");
      saveBtn.textContent = "Saved";
    }
    if (ua.done) {
      doneBtn.classList.add("active");
      doneBtn.textContent = "Done";
      article.classList.add("is-done");
    }

    saveBtn.addEventListener("click", () => {
      const a = getUserAction(q.id);
      a.saved = !a.saved;
      state.userActions[q.id] = a;
      persistUserActions();
      saveBtn.classList.toggle("active", a.saved);
      saveBtn.textContent = a.saved ? "Saved" : "Save";
    });

    doneBtn.addEventListener("click", () => {
      const a = getUserAction(q.id);
      a.done = !a.done;
      state.userActions[q.id] = a;
      persistUserActions();
      doneBtn.classList.toggle("active", a.done);
      doneBtn.textContent = a.done ? "Done" : "Mark done";
      article.classList.toggle("is-done", a.done);
    });

    questionList.appendChild(card);
  });

  state.visibleCount += batch.length;
  loadMoreWrap.hidden = state.visibleCount >= state.filteredQuestions.length;
  updateResultCount();
}

// Filter change handlers
paperTypeFilter.addEventListener("change", () => {
  updateSectionOptions();
  updatePaperOptions();
  applyFilters();
});
topicFilter.addEventListener("change", () => {
  updateSectionOptions();
  updatePaperOptions();
  applyFilters();
});
sectionFilter.addEventListener("change", applyFilters);
paperFilter.addEventListener("change", applyFilters);
savedFilter.addEventListener("change", applyFilters);
searchInput.addEventListener("input", applyFilters);

loadMoreBtn.addEventListener("click", () => {
  renderQuestions(false);
});

// Search toggle
searchToggle.addEventListener("click", () => {
  const expanded = heroSearch.classList.toggle("search-open");
  searchToggle.setAttribute("aria-expanded", String(expanded));
  if (expanded) searchInput.focus();
});

async function init() {
  loadUserActions();
  try {
    await loadData();
    hydrateFilters();
    applyFilters();
  } catch (err) {
    questionList.innerHTML = `<p class="error">Failed to load questions: ${err.message}</p>`;
    resultCount.textContent = "";
  }
}

init();
