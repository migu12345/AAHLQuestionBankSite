const state = {
  allQuestions: [],
  markschemesById: {},
  markschemeLatexById: {},
  markschemeImagesById: {},
  filteredQuestions: [],
  visibleCount: 0,
  userActions: {},
  topicSubtopicMap: {},
  shuffled: false,
};
const PAGE_SIZE = 10;
const USER_ACTIONS_KEY = "math_bank_user_actions_v1";

const searchInput = document.getElementById("searchInput");
const searchToggle = document.getElementById("searchToggle");
const heroSearch = document.getElementById("heroSearch");
const levelFilter = document.getElementById("levelFilter");
const paperTypeFilter = document.getElementById("paperTypeFilter");
const difficultyFilter = document.getElementById("difficultyFilter");
const savedFilter = document.getElementById("savedFilter");
const topicFilter = document.getElementById("topicFilter");
const subtopicFilter = document.getElementById("subtopicFilter");
const resultCount = document.getElementById("resultCount");
const questionList = document.getElementById("questionList");
const questionTemplate = document.getElementById("questionTemplate");
const loadMoreWrap = document.getElementById("loadMoreWrap");
const loadMoreBtn = document.getElementById("loadMoreBtn");
const shuffleBtn = document.getElementById("shuffleBtn");
const compareModal = document.getElementById("compareModal");
const compareBackdrop = document.getElementById("compareBackdrop");
const compareCloseBtn = document.getElementById("compareCloseBtn");
const compareTitle = document.getElementById("compareTitle");
const compareQuestionBody = document.getElementById("compareQuestionBody");
const compareMarkschemeBody = document.getElementById("compareMarkschemeBody");

function renderKatex(el) {
  if (window.renderMathInElement) {
    window.renderMathInElement(el, {
      delimiters: [
        { left: "$$", right: "$$", display: true },
        { left: "\\(", right: "\\)", display: false },
        { left: "\\[", right: "\\]", display: true },
      ],
      throwOnError: false,
    });
  } else {
    document.addEventListener("katex-ready", () => renderKatex(el), { once: true });
  }
}

function loadUserActions() {
  try {
    const raw = window.localStorage.getItem(USER_ACTIONS_KEY);
    state.userActions = raw ? JSON.parse(raw) : {};
  } catch (_error) {
    state.userActions = {};
  }
}

function persistUserActions() {
  try {
    window.localStorage.setItem(USER_ACTIONS_KEY, JSON.stringify(state.userActions));
  } catch (_error) {
    // Ignore storage failures in private/restricted mode.
  }
}

function getUserAction(qid) {
  return state.userActions[qid] || { saved: false, done: false };
}

async function loadData() {
  const [qRes, msRes] = await Promise.all([
    window.assetFetch("/data/tutoring/processed/questions.json"),
    window.assetFetch("/data/tutoring/processed/markschemes.json"),
  ]);
  const qData = await qRes.json();
  const msData = await msRes.json();

  state.allQuestions = Array.isArray(qData.questions) ? qData.questions : [];
  const markschemes = Array.isArray(msData.questions) ? msData.questions : [];
  state.markschemesById = Object.fromEntries(
    markschemes.map((entry) => [entry.id, entry.worked_solution_text || ""])
  );
  state.markschemeLatexById = Object.fromEntries(
    markschemes.filter((entry) => entry.latex_solution).map((entry) => [entry.id, entry.latex_solution])
  );
  state.markschemeImagesById = Object.fromEntries(
    markschemes.map((entry) => [entry.id, Array.isArray(entry.markscheme_image_paths) ? entry.markscheme_image_paths : []])
  );

  // Build topic → subtopics map for dynamic filter update.
  state.topicSubtopicMap = {};
  state.allQuestions.forEach((q) => {
    const topic = q.unit || q.topic || "";
    const subtopic = q.subtopic || "";
    if (!topic) return;
    if (!state.topicSubtopicMap[topic]) state.topicSubtopicMap[topic] = new Set();
    if (subtopic) state.topicSubtopicMap[topic].add(subtopic);
  });
}

function inferLevel(q) {
  if (q.level === "SL" || q.level === "HL") return q.level;
  const src = String(q.source_file || "").toLowerCase();
  if (src.includes("_hl") || src.includes("hl_")) return "HL";
  if (src.includes("_sl") || src.includes("sl_") || src.includes("math_sl")) return "SL";
  // Induction & complex numbers are HL-only in IB AA.
  const subtopic = String(q.subtopic || "").toLowerCase();
  if (subtopic.includes("induction") || subtopic.includes("complex")) return "HL";
  return "";
}

function inferDifficulty(q) {
  const marks = Number(q.marks || 0);
  if (marks === 0) return "";
  const level = inferLevel(q);
  const paperType = String(q.paper_type || "").toLowerCase();
  const paperMatch = paperType.match(/paper\s*([123])/);
  const paperNo = paperMatch ? Number(paperMatch[1]) : 0;

  let score = 0;
  if (marks >= 11) score += 2;
  else if (marks >= 7) score += 1;
  if (level === "HL") score += 1;
  if (paperNo === 2) score += 0.5;
  if (marks <= 4 && level === "SL" && paperNo <= 1) score -= 1;

  if (score <= 0) return "Easy";
  if (score <= 2) return "Medium";
  return "Hard";
}

function hydrateFilters() {
  const levels = [...new Set(state.allQuestions.map(inferLevel).filter(Boolean))].sort();
  levels.forEach((level) => {
    const opt = document.createElement("option");
    opt.value = level;
    opt.textContent = level;
    levelFilter.appendChild(opt);
  });

  const paperTypes = [...new Set(state.allQuestions.map((q) => q.paper_type).filter(Boolean))].sort();
  paperTypes.forEach((pt) => {
    const opt = document.createElement("option");
    opt.value = pt;
    opt.textContent = pt;
    paperTypeFilter.appendChild(opt);
  });

  const topics = Object.keys(state.topicSubtopicMap).sort();
  topics.forEach((topic) => {
    const opt = document.createElement("option");
    opt.value = topic;
    opt.textContent = topic;
    topicFilter.appendChild(opt);
  });

  updateSubtopicOptions();
}

function updateSubtopicOptions() {
  const selectedTopic = topicFilter.value;
  const previousValue = subtopicFilter.value;

  subtopicFilter.innerHTML = '<option value="">All subtopics</option>';

  const subtopics = selectedTopic
    ? [...(state.topicSubtopicMap[selectedTopic] || [])]
    : [...new Set(Object.values(state.topicSubtopicMap).flatMap((s) => [...s]))];

  subtopics.sort().forEach((subtopic) => {
    const opt = document.createElement("option");
    opt.value = subtopic;
    opt.textContent = subtopic;
    subtopicFilter.appendChild(opt);
  });

  if ([...subtopicFilter.options].some((o) => o.value === previousValue)) {
    subtopicFilter.value = previousValue;
  }
}

function normalizeForSearch(value) {
  return String(value || "")
    .toLowerCase()
    .normalize("NFKD")
    .replace(/[̀-ͯ]/g, "")
    .replace(/[^a-z0-9]+/g, " ")
    .trim();
}

function matchesSearchToken(q, token, normalizedHaystack, level) {
  if (!token) return true;
  if (token === "hl" || token === "sl") return level.toLowerCase() === token;
  const paperMatch = token.match(/^(?:paper|p)([123])$/);
  if (paperMatch) {
    const n = paperMatch[1];
    return normalizeForSearch(q.paper_type || "").includes(`paper ${n}`);
  }
  const questionMatch = token.match(/^q(\d{1,3})$/);
  if (questionMatch) return String(q.question_number || "") === questionMatch[1];
  return normalizedHaystack.includes(token);
}

function matchesSearchQuery(q, rawQuery, level) {
  const query = normalizeForSearch(rawQuery);
  if (!query) return true;
  const tokens = query.split(/\s+/).filter(Boolean);
  const normalizedHaystack = normalizeForSearch(
    [q.title, q.question_text, q.unit, q.topic, q.subtopic, q.source_file, q.question_number, q.paper_type].join(" ")
  );
  return tokens.every((token) => matchesSearchToken(q, token, normalizedHaystack, level));
}

function shuffleArray(arr) {
  for (let i = arr.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [arr[i], arr[j]] = [arr[j], arr[i]];
  }
}

function filterQuestions() {
  const selectedLevel = levelFilter.value;
  const selectedPaperType = paperTypeFilter.value;
  const selectedDifficulty = difficultyFilter.value;
  const selectedSaved = savedFilter.value;
  const selectedTopic = topicFilter.value;
  const selectedSubtopic = subtopicFilter.value;
  const searchTerm = searchInput.value.trim();

  return state.allQuestions.filter((q) => {
    const level = inferLevel(q);
    const difficulty = inferDifficulty(q);
    const action = getUserAction(q.id);
    const topic = q.unit || q.topic || "";

    const levelMatch = !selectedLevel || level === selectedLevel;
    const paperTypeMatch = !selectedPaperType || q.paper_type === selectedPaperType;
    const difficultyMatch = !selectedDifficulty || difficulty === selectedDifficulty;
    const savedMatch = !selectedSaved || (selectedSaved === "saved" ? action.saved : action.done);
    const topicMatch = !selectedTopic || topic === selectedTopic;
    const subtopicMatch = !selectedSubtopic || q.subtopic === selectedSubtopic;
    const searchMatch = matchesSearchQuery(q, searchTerm, level);

    return levelMatch && paperTypeMatch && difficultyMatch && savedMatch && topicMatch && subtopicMatch && searchMatch;
  });
}

function legacyImageRelPath(relPath) {
  return String(relPath || "").replace(/_(sl|hl)(?=(_p\d+)?\.png$)/i, "");
}

function createImageWithFallback(relPath, altText) {
  const img = document.createElement("img");
  img.alt = altText;
  img.loading = "lazy";
  img.src = window.assetUrl(`/data/tutoring/processed/${relPath}`);
  const legacyRelPath = legacyImageRelPath(relPath);
  if (legacyRelPath !== relPath) {
    img.addEventListener(
      "error",
      () => { img.src = window.assetUrl(`/data/tutoring/processed/${legacyRelPath}`); },
      { once: true }
    );
  }
  return img;
}

function cleanPreviewText(text) {
  return String(text || "")
    .replace(/\s+/g, " ")
    .replace(/\/g\d+/gi, " ")
    .replace(/\.{3,}/g, "...")
    .trim();
}

function buildQuestionNode(q) {
  const node = questionTemplate.content.cloneNode(true);
  const questionImagesEl = node.querySelector(".question-images");
  const markschemeImagesEl = node.querySelector(".markscheme-images");
  const questionTextEl = node.querySelector(".question");
  const answerTextEl = node.querySelector(".answer");
  const titleEl = node.querySelector(".title");
  const tagsEl = node.querySelector(".card-tags");
  const saveBtn = node.querySelector(".save-btn");
  const doneBtn = node.querySelector(".done-btn");
  const sideBySideBtn = node.querySelector(".side-by-side-btn");

  const level = inferLevel(q);
  const difficulty = inferDifficulty(q);
  const marks = Number.isFinite(Number(q.marks)) && q.marks ? `${q.marks} marks` : null;
  const topic = q.unit || q.topic || "Unsorted";
  const metaParts = [topic, q.subtopic, marks, q.paper_type, level].filter(Boolean);
  node.querySelector(".meta").textContent = metaParts.join(" | ");

  const questionNumber = `${q.question_number || ""}`.trim();
  const fallbackTitle = questionNumber ? `Q${questionNumber}` : "Question";
  const qImages = Array.isArray(q.question_image_paths) ? q.question_image_paths : [];
  titleEl.textContent = qImages.length > 0 ? fallbackTitle : cleanPreviewText(q.title || "") || fallbackTitle;

  if (difficulty && tagsEl) {
    const badge = document.createElement("span");
    badge.className = `difficulty-tag difficulty-${difficulty.toLowerCase()}`;
    badge.textContent = difficulty;
    tagsEl.appendChild(badge);
  }
  if (level && tagsEl) {
    const badge = document.createElement("span");
    badge.className = "difficulty-tag difficulty-medium";
    badge.textContent = level;
    tagsEl.appendChild(badge);
  }

  const action = getUserAction(q.id);
  if (action.saved && tagsEl) {
    const badge = document.createElement("span");
    badge.className = "difficulty-tag difficulty-medium";
    badge.textContent = "Saved";
    tagsEl.appendChild(badge);
  }
  if (action.done && tagsEl) {
    const badge = document.createElement("span");
    badge.className = "difficulty-tag difficulty-easy";
    badge.textContent = "Done";
    tagsEl.appendChild(badge);
  }

  if (saveBtn) {
    saveBtn.textContent = action.saved ? "Saved" : "Save";
    if (action.saved) saveBtn.classList.add("active");
    saveBtn.addEventListener("click", () => {
      const current = getUserAction(q.id);
      state.userActions[q.id] = { ...current, saved: !current.saved };
      persistUserActions();
      renderQuestions(true);
    });
  }
  if (doneBtn) {
    doneBtn.textContent = action.done ? "Done" : "Mark done";
    if (action.done) doneBtn.classList.add("active");
    doneBtn.addEventListener("click", () => {
      const current = getUserAction(q.id);
      state.userActions[q.id] = { ...current, done: !current.done };
      persistUserActions();
      renderQuestions(true);
    });
  }

  sideBySideBtn.addEventListener("click", () => openCompareModal(q));

  if (qImages.length > 0) {
    qImages.forEach((imgPath, index) => {
      questionImagesEl.appendChild(createImageWithFallback(imgPath, `Question ${questionNumber} image ${index + 1}`));
    });
    questionTextEl.hidden = true;
  } else {
    questionTextEl.textContent = q.question_text || "";
    questionTextEl.hidden = false;
  }

  const msImages = state.markschemeImagesById[q.id] || [];
  const latex = state.markschemeLatexById[q.id];
  if (latex) {
    answerTextEl.hidden = false;
    answerTextEl.innerHTML = latex;
    renderKatex(answerTextEl);
  } else if (msImages.length > 0) {
    msImages.forEach((imgPath, index) => {
      markschemeImagesEl.appendChild(createImageWithFallback(imgPath, `Markscheme ${questionNumber} image ${index + 1}`));
    });
    answerTextEl.hidden = true;
  } else {
    const msText = state.markschemesById[q.id] || q.answer_text || "";
    answerTextEl.textContent = msText || "No markscheme available yet.";
    answerTextEl.hidden = false;
  }

  return node;
}

function openCompareModal(q) {
  if (!compareModal || !compareQuestionBody || !compareMarkschemeBody || !compareTitle) return;

  compareQuestionBody.innerHTML = "";
  compareMarkschemeBody.innerHTML = "";

  const qImages = Array.isArray(q.question_image_paths) ? q.question_image_paths : [];
  const msImages = state.markschemeImagesById[q.id] || [];

  if (qImages.length > 0) {
    qImages.forEach((imgPath, index) => {
      compareQuestionBody.appendChild(createImageWithFallback(imgPath, `Question ${q.question_number || ""} image ${index + 1}`));
    });
  } else {
    const p = document.createElement("p");
    p.className = "compare-fallback";
    p.textContent = q.question_text || "No extracted question text.";
    compareQuestionBody.appendChild(p);
  }

  const msLatex = state.markschemeLatexById[q.id];
  if (msLatex) {
    const p = document.createElement("div");
    p.className = "compare-fallback";
    p.innerHTML = msLatex;
    compareMarkschemeBody.appendChild(p);
    renderKatex(p);
  } else if (msImages.length > 0) {
    msImages.forEach((imgPath, index) => {
      compareMarkschemeBody.appendChild(createImageWithFallback(imgPath, `Markscheme ${q.question_number || ""} image ${index + 1}`));
    });
  } else {
    const p = document.createElement("div");
    p.className = "compare-fallback";
    p.textContent = state.markschemesById[q.id] || q.answer_text || "No markscheme available yet.";
    compareMarkschemeBody.appendChild(p);
  }

  const qLabel = `${q.question_number || ""}`.trim();
  compareTitle.textContent = qLabel ? `Side by side — Q${qLabel}` : "Side by side view";
  compareModal.hidden = false;
  document.body.style.overflow = "hidden";
}

function closeCompareModal() {
  if (!compareModal || !compareQuestionBody || !compareMarkschemeBody) return;
  compareModal.hidden = true;
  compareQuestionBody.innerHTML = "";
  compareMarkschemeBody.innerHTML = "";
  document.body.style.overflow = "";
}

function updateResultSummary() {
  const total = state.filteredQuestions.length;
  const shown = Math.min(state.visibleCount, total);
  resultCount.textContent = total === 0 ? "0 question(s)" : `Showing ${shown} of ${total} question(s)`;
  loadMoreWrap.style.display = shown < total ? "block" : "none";
}

function renderQuestions(reset = true) {
  if (reset) {
    state.filteredQuestions = filterQuestions();
    if (state.shuffled) shuffleArray(state.filteredQuestions);
    state.visibleCount = Math.min(PAGE_SIZE, state.filteredQuestions.length);
    questionList.innerHTML = "";

    if (state.filteredQuestions.length === 0) {
      resultCount.textContent = "0 question(s)";
      questionList.innerHTML = "<p>No matches found.</p>";
      loadMoreWrap.style.display = "none";
      return;
    }

    state.filteredQuestions.slice(0, state.visibleCount).forEach((q) => {
      questionList.appendChild(buildQuestionNode(q));
    });
    updateResultSummary();
    return;
  }

  const currentShown = Math.min(state.visibleCount, state.filteredQuestions.length);
  const newShown = Math.min(currentShown + PAGE_SIZE, state.filteredQuestions.length);
  state.filteredQuestions.slice(currentShown, newShown).forEach((q) => {
    questionList.appendChild(buildQuestionNode(q));
  });
  state.visibleCount = newShown;
  updateResultSummary();
}

function bindEvents() {
  levelFilter.addEventListener("change", () => renderQuestions(true));
  paperTypeFilter.addEventListener("change", () => renderQuestions(true));
  difficultyFilter.addEventListener("change", () => renderQuestions(true));
  savedFilter.addEventListener("change", () => renderQuestions(true));
  topicFilter.addEventListener("change", () => {
    updateSubtopicOptions();
    renderQuestions(true);
  });
  subtopicFilter.addEventListener("change", () => renderQuestions(true));
  searchInput.addEventListener("input", () => renderQuestions(true));

  if (searchToggle && heroSearch) {
    searchToggle.addEventListener("click", () => {
      const expanded = heroSearch.classList.toggle("expanded");
      searchToggle.setAttribute("aria-expanded", expanded ? "true" : "false");
      if (expanded) {
        searchInput.focus();
      } else {
        if (searchInput.value) {
          searchInput.value = "";
          renderQuestions(true);
        }
      }
    });
    searchInput.addEventListener("keydown", (event) => {
      if (event.key === "Escape") {
        heroSearch.classList.remove("expanded");
        searchToggle.setAttribute("aria-expanded", "false");
        searchInput.value = "";
        renderQuestions(true);
        searchToggle.focus();
      }
    });
  }

  loadMoreBtn.addEventListener("click", () => renderQuestions(false));

  shuffleBtn.addEventListener("click", () => {
    state.shuffled = !state.shuffled;
    shuffleBtn.classList.toggle("active", state.shuffled);
    shuffleBtn.textContent = state.shuffled ? "Shuffled" : "Shuffle";
    renderQuestions(true);
  });

  if (compareBackdrop) compareBackdrop.addEventListener("click", closeCompareModal);
  if (compareCloseBtn) compareCloseBtn.addEventListener("click", closeCompareModal);
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && compareModal && !compareModal.hidden) closeCompareModal();
  });
}

async function start() {
  try {
    loadUserActions();
    await loadData();
    hydrateFilters();
    bindEvents();
    renderQuestions(true);
  } catch (error) {
    questionList.innerHTML = `<p>Failed to load questions: ${error.message}</p>`;
  }
}

start();
