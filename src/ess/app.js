const state = {
  allQuestions: [],
  topics: [],
  filteredQuestions: [],
  visibleCount: 0,
  userActions: {},
};
const PAGE_SIZE = 10;
const USER_ACTIONS_KEY = "ess_bank_user_actions_v1";

const paperTypeFilter = document.getElementById("paperTypeFilter");
const paperFilter = document.getElementById("paperFilter");
const difficultyFilter = document.getElementById("difficultyFilter");
const savedFilter = document.getElementById("savedFilter");
const topicFilter = document.getElementById("topicFilter");
const subtopicFilter = document.getElementById("subtopicFilter");
const searchInput = document.getElementById("searchInput");
const searchToggle = document.getElementById("searchToggle");
const heroSearch = document.getElementById("heroSearch");
const questionList = document.getElementById("questionList");
const resultCount = document.getElementById("resultCount");
const questionTemplate = document.getElementById("questionTemplate");
const loadMoreWrap = document.getElementById("loadMoreWrap");
const loadMoreBtn = document.getElementById("loadMoreBtn");
const compareModal = document.getElementById("compareModal");
const compareBackdrop = document.getElementById("compareBackdrop");
const compareCloseBtn = document.getElementById("compareCloseBtn");
const compareTitle = document.getElementById("compareTitle");
const compareQuestionBody = document.getElementById("compareQuestionBody");
const compareMarkschemeBody = document.getElementById("compareMarkschemeBody");

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
  } catch (_error) {}
}

function getUserAction(qid) {
  return state.userActions[qid] || { saved: false, done: false };
}

async function loadData() {
  const [questionRes, topicRes] = await Promise.all([
    window.assetFetch("/data/ess/processed/questions.json"),
    window.assetFetch("/data/ess/topic-map.json"),
  ]);
  if (!questionRes.ok || !topicRes.ok) {
    throw new Error(`HTTP ${questionRes.status}/${topicRes.status}`);
  }
  const questionData = await questionRes.json();
  const topicData = await topicRes.json();
  state.allQuestions = questionData.questions || [];
  state.topics = topicData.topics || [];
}

function hydrateFilters() {
  const paperTypes = [...new Set(state.allQuestions.map((q) => q.paper_type).filter(Boolean))].sort();
  paperTypes.forEach((pt) => {
    const opt = document.createElement("option");
    opt.value = pt;
    opt.textContent = pt;
    paperTypeFilter.appendChild(opt);
  });

  const papers = [...new Set(state.allQuestions.map((q) => q.paper).filter(Boolean))].sort();
  papers.forEach((paper) => {
    const opt = document.createElement("option");
    opt.value = paper;
    opt.textContent = paper;
    paperFilter.appendChild(opt);
  });

  state.topics.forEach((topic) => {
    const opt = document.createElement("option");
    opt.value = topic.name;
    opt.textContent = topic.name;
    topicFilter.appendChild(opt);
  });

  updateSubtopicOptions();
}

function updateSubtopicOptions() {
  const selectedTopic = topicFilter.value;
  const previousValue = subtopicFilter.value;
  subtopicFilter.innerHTML = '<option value="">All subtopics</option>';
  const sourceTopics = selectedTopic
    ? state.topics.filter((t) => t.name === selectedTopic)
    : state.topics;
  const subtopics = [...new Set(sourceTopics.flatMap((t) => t.subtopics || []))].sort();
  subtopics.forEach((subtopic) => {
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

function matchesSearchToken(q, token, normalizedHaystack) {
  if (!token) return true;
  const paperMatch = token.match(/^(?:paper|p)([12])$/);
  if (paperMatch) {
    return normalizeForSearch(q.paper_type || "").includes(`paper ${paperMatch[1]}`);
  }
  const questionMatch = token.match(/^q(\d{1,3})$/);
  if (questionMatch) return String(q.question_number || "") === questionMatch[1];
  return normalizedHaystack.includes(token);
}

function matchesSearchQuery(q, rawQuery) {
  const query = normalizeForSearch(rawQuery);
  if (!query) return true;
  const tokens = query.split(/\s+/).filter(Boolean);
  const normalizedHaystack = normalizeForSearch(
    [q.title, q.question_text, q.paper, q.paper_type, q.topic, q.subtopic, q.question_number].join(" ")
  );
  return tokens.every((token) => matchesSearchToken(q, token, normalizedHaystack));
}

function inferDifficulty(q) {
  const marks = Number(q?.marks || 0);
  if (!marks) return "";
  const paperType = String(q?.paper_type || "").toLowerCase();
  const paperMatch = paperType.match(/paper\s*([12])/);
  const paperNo = paperMatch ? Number(paperMatch[1]) : 0;
  let score = 0;
  if (marks >= 11) score += 2;
  else if (marks >= 7) score += 1;
  if (paperNo === 2) score += 0.5;
  if (marks <= 4 && paperNo === 1) score -= 1;
  if (score <= 0) return "Easy";
  if (score <= 2) return "Medium";
  return "Hard";
}

function filterQuestions() {
  const selectedPaperType = paperTypeFilter.value;
  const selectedPaper = paperFilter.value;
  const selectedDifficulty = difficultyFilter.value;
  const selectedSaved = savedFilter.value;
  const selectedTopic = topicFilter.value;
  const selectedSubtopic = subtopicFilter.value;
  const searchTerm = searchInput.value.trim();

  return state.allQuestions.filter((q) => {
    const paperTypeMatch = !selectedPaperType || q.paper_type === selectedPaperType;
    const paperMatch = !selectedPaper || q.paper === selectedPaper;
    const difficultyMatch = !selectedDifficulty || inferDifficulty(q) === selectedDifficulty;
    const action = getUserAction(q.id);
    const savedMatch = !selectedSaved || (selectedSaved === "saved" ? action.saved : action.done);
    const topicMatch = !selectedTopic || q.topic === selectedTopic;
    const subtopicMatch = !selectedSubtopic || q.subtopic === selectedSubtopic;
    const searchMatch = matchesSearchQuery(q, searchTerm);
    return paperTypeMatch && paperMatch && difficultyMatch && savedMatch && topicMatch && subtopicMatch && searchMatch;
  });
}

function shuffleArray(arr) {
  for (let i = arr.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [arr[i], arr[j]] = [arr[j], arr[i]];
  }
}

function cleanPreviewText(text) {
  return String(text || "")
    .replace(/\s+/g, " ")
    .replace(/\/g\d+/gi, " ")
    .replace(/\.{3,}/g, "...")
    .trim();
}

function getNormalizedMarks(q) {
  const numeric = Number(q?.marks);
  return Number.isFinite(numeric) && numeric > 0 ? numeric : null;
}

function createImageWithFallback(relPath, altText) {
  const img = document.createElement("img");
  img.alt = altText;
  img.loading = "lazy";
  img.src = window.assetUrl(`/data/ess/processed/${relPath}`);
  return img;
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

  const normalizedMarks = getNormalizedMarks(q);
  const marks = normalizedMarks ? `${normalizedMarks} marks` : "marks n/a";
  node.querySelector(".meta").textContent = `${q.paper || "Unknown paper"} | ${q.topic || "Unsorted"} | ${marks}`;

  const qImages = Array.isArray(q.question_image_paths) ? q.question_image_paths : [];
  const msImages = Array.isArray(q.markscheme_image_paths) ? q.markscheme_image_paths : [];
  const questionNumber = `${q.question_number || ""}`.trim();
  const fallbackTitle = questionNumber ? `Q${questionNumber}` : "Question";
  titleEl.textContent = qImages.length > 0 ? fallbackTitle : cleanPreviewText(q.title || "") || fallbackTitle;

  const difficulty = inferDifficulty(q);
  if (tagsEl && difficulty) {
    const badge = document.createElement("span");
    badge.className = `difficulty-tag difficulty-${difficulty.toLowerCase()}`;
    badge.textContent = difficulty;
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

  const textBookletPath = q.text_booklet_path || "";
  if (textBookletPath) {
    const tbBtn = document.createElement("a");
    tbBtn.className = "btn-case-study";
    tbBtn.textContent = "View Case Study";
    tbBtn.href = window.assetUrl(`/data/ess/processed/${textBookletPath}`);
    tbBtn.target = "_blank";
    tbBtn.rel = "noopener noreferrer";
    node.querySelector(".question-actions").after(tbBtn);
  }

  if (qImages.length > 0) {
    qImages.forEach((imgPath, index) => {
      questionImagesEl.appendChild(createImageWithFallback(imgPath, `Question ${questionNumber} image ${index + 1}`));
    });
    questionTextEl.hidden = true;
  } else {
    questionTextEl.textContent = q.question_text || "Question screenshot is being prepared.";
    questionTextEl.hidden = false;
  }

  if (msImages.length > 0) {
    msImages.forEach((imgPath, index) => {
      markschemeImagesEl.appendChild(createImageWithFallback(imgPath, `Markscheme ${questionNumber} image ${index + 1}`));
    });
    answerTextEl.hidden = true;
  } else {
    answerTextEl.textContent = "No markscheme available.";
    answerTextEl.hidden = false;
  }

  return node;
}

function openCompareModal(q) {
  if (!compareModal || !compareQuestionBody || !compareMarkschemeBody || !compareTitle) return;
  compareQuestionBody.innerHTML = "";
  compareMarkschemeBody.innerHTML = "";

  const qImages = Array.isArray(q.question_image_paths) ? q.question_image_paths : [];
  const msImages = Array.isArray(q.markscheme_image_paths) ? q.markscheme_image_paths : [];

  if (qImages.length > 0) {
    qImages.forEach((imgPath, index) => {
      compareQuestionBody.appendChild(createImageWithFallback(imgPath, `Question ${q.question_number || ""} image ${index + 1}`));
    });
  } else {
    const p = document.createElement("p");
    p.className = "compare-fallback";
    p.textContent = q.question_text || "Question screenshot is being prepared.";
    compareQuestionBody.appendChild(p);
  }

  if (msImages.length > 0) {
    msImages.forEach((imgPath, index) => {
      compareMarkschemeBody.appendChild(createImageWithFallback(imgPath, `Markscheme ${q.question_number || ""} image ${index + 1}`));
    });
  } else {
    const p = document.createElement("p");
    p.className = "compare-fallback";
    p.textContent = "No markscheme available.";
    compareMarkschemeBody.appendChild(p);
  }

  const qLabel = `${q.question_number || ""}`.trim();
  compareTitle.textContent = qLabel ? `Side by side — Q${qLabel}` : "Side by side view";
  compareQuestionBody.scrollTop = 0;
  compareMarkschemeBody.scrollTop = 0;
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
    shuffleArray(state.filteredQuestions);
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
  paperTypeFilter.addEventListener("change", () => renderQuestions(true));
  paperFilter.addEventListener("change", () => renderQuestions(true));
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
    questionList.innerHTML = `<p>Failed to load data: ${error.message}</p>`;
  }
}

start();
