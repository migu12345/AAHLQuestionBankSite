const state = {
  allQuestions: [],
  topics: [],
  filteredQuestions: [],
  visibleCount: 0,
  slPriorityDuplicateKeys: new Set(),
  userActions: {},
  paperBundle: null,
  paperSourceFile: "",
  paperSourcePath: "",
  paperNoMarkscheme: false,
  examMode: {
    enabled: false,
    durationSeconds: 0,
    started: false,
    ended: false,
    endTs: 0,
    timerId: null,
  },
};
const PAGE_SIZE = 10;
const USER_ACTIONS_KEY = "aa_bank_user_actions_v1";

const paperTypeFilter = document.getElementById("paperTypeFilter");
const paperFilter = document.getElementById("paperFilter");
const difficultyFilter = document.getElementById("difficultyFilter");
const savedFilter = document.getElementById("savedFilter");
const topicFilter = document.getElementById("topicFilter");
const subtopicFilter = document.getElementById("subtopicFilter");
const levelFilter = document.getElementById("levelFilter");
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
const examModeBar = document.getElementById("examModeBar");
const examModeInfo = document.getElementById("examModeInfo");
const examModeStartBtn = document.getElementById("examModeStartBtn");
const examModeEndBtn = document.getElementById("examModeEndBtn");

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

async function loadData() {
  const [questionRes, topicRes] = await Promise.all([
    fetch("/data/physics/processed/questions.json"),
    fetch("/data/physics/topic-map.json"),
  ]);

  if (!questionRes.ok || !topicRes.ok) {
    throw new Error(`HTTP ${questionRes.status}/${topicRes.status}`);
  }

  const questionData = await questionRes.json();
  const topicData = await topicRes.json();

  state.allQuestions = questionData.questions || [];
  state.topics = topicData.topics || [];
  buildSlPriorityDuplicateKeys();
}

function hydrateFilters() {
  const levels = [...new Set(state.allQuestions.map((q) => inferLevel(q)).filter(Boolean))].sort();
  levels.forEach((level) => {
    const option = document.createElement("option");
    option.value = level;
    option.textContent = level;
    levelFilter.appendChild(option);
  });

  const paperTypes = [...new Set(state.allQuestions.map((q) => q.paper_type).filter(Boolean))].sort();
  paperTypes.forEach((paperType) => {
    const option = document.createElement("option");
    option.value = paperType;
    option.textContent = paperType;
    paperTypeFilter.appendChild(option);
  });

  const papers = [...new Set(state.allQuestions.map((q) => q.paper).filter(Boolean))].sort();
  papers.forEach((paper) => {
    const option = document.createElement("option");
    option.value = paper;
    option.textContent = paper;
    paperFilter.appendChild(option);
  });

  state.topics.forEach((topic) => {
    const option = document.createElement("option");
    option.value = topic.name;
    option.textContent = topic.name;
    topicFilter.appendChild(option);
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
    const option = document.createElement("option");
    option.value = subtopic;
    option.textContent = subtopic;
    subtopicFilter.appendChild(option);
  });

  if ([...subtopicFilter.options].some((o) => o.value === previousValue)) {
    subtopicFilter.value = previousValue;
  }
}

function normalizeForSearch(value) {
  return String(value || "")
    .toLowerCase()
    .normalize("NFKD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/[^a-z0-9]+/g, " ")
    .trim();
}

function matchesSearchToken(q, token, normalizedHaystack, level) {
  if (!token) {
    return true;
  }

  if (token === "hl" || token === "sl") {
    return level.toLowerCase() === token;
  }

  const paperMatch = token.match(/^(?:paper|p)([123])$/);
  if (paperMatch) {
    const n = paperMatch[1];
    const paperTypeText = normalizeForSearch(q.paper_type || "");
    const paperText = normalizeForSearch(q.paper || "");
    return paperTypeText.includes(`paper ${n}`) || paperText.includes(`paper ${n}`);
  }

  const questionMatch = token.match(/^q(\d{1,3})$/);
  if (questionMatch) {
    return String(q.question_number || "") === questionMatch[1];
  }

  return normalizedHaystack.includes(token);
}

function matchesSearchQuery(q, rawQuery, level) {
  const query = normalizeForSearch(rawQuery);
  if (!query) {
    return true;
  }

  const tokens = query.split(/\s+/).filter(Boolean);
  const normalizedHaystack = normalizeForSearch(
    [
      q.title,
      q.question_text,
      q.answer_text,
      q.paper,
      q.paper_type,
      q.topic,
      q.subtopic,
      q.question_number,
      q.source?.paper_file,
    ].join(" ")
  );

  return tokens.every((token) => matchesSearchToken(q, token, normalizedHaystack, level));
}

function filterQuestions() {
  if (state.paperBundle) {
    return filterQuestionsByBundle();
  }

  const selectedLevel = levelFilter.value;
  const selectedPaperType = paperTypeFilter.value;
  const selectedPaper = paperFilter.value;
  const selectedDifficulty = difficultyFilter.value;
  const selectedSaved = savedFilter.value;
  const selectedTopic = topicFilter.value;
  const selectedSubtopic = subtopicFilter.value;
  const searchTerm = searchInput.value.trim();

  return state.allQuestions.filter((q) => {
    const level = inferLevel(q);
    const levelMatch = !selectedLevel || level === selectedLevel;
    const paperTypeMatch = !selectedPaperType || q.paper_type === selectedPaperType;
    const paperMatch = !selectedPaper || q.paper === selectedPaper;
    const difficultyMatch = !selectedDifficulty || inferDifficulty(q) === selectedDifficulty;
    const action = getUserAction(q.id);
    const savedMatch = !selectedSaved || (selectedSaved === "saved" ? action.saved : action.done);
    const topicMatch = !selectedTopic || q.topic === selectedTopic;
    const subtopicMatch = !selectedSubtopic || q.subtopic === selectedSubtopic;
    const searchMatch = matchesSearchQuery(q, searchTerm, level);
    const duplicateMatch = !shouldHideAsCrossLevelDuplicate(q);

    return (
      levelMatch &&
      paperTypeMatch &&
      paperMatch &&
      difficultyMatch &&
      savedMatch &&
      topicMatch &&
      subtopicMatch &&
      searchMatch &&
      duplicateMatch
    );
  });
}

function parsePaperMeta(paperLabel) {
  const m = String(paperLabel || "").match(
    /^(May|November)\s+(\d{4})(?:\s+Physics)?\s+Paper\s+([123](?:[AB])?)(?:\s+(TZ\d))?\s+(HL|SL)$/i
  );
  if (!m) {
    return null;
  }
  return {
    session: m[1],
    year: Number(m[2]),
    paperNo: Number(String(m[3]).replace(/[^0-9]/g, "")),
    timezone: m[4] || "No TZ",
    level: m[5].toUpperCase(),
  };
}

function buildCrossLevelDuplicateKey(q) {
  const meta = parsePaperMeta(q.paper);
  if (!meta) {
    return null;
  }
  const textBasis = normalizeForSearch(q.question_text || q.title || "");
  if (textBasis.length < 24) {
    return null;
  }
  return [
    meta.session,
    meta.year,
    meta.paperNo,
    meta.timezone,
    normalizeForSearch(q.paper_type || ""),
    String(Number.isFinite(q.marks) ? q.marks : ""),
    normalizeForSearch(q.topic || ""),
    normalizeForSearch(q.subtopic || ""),
    textBasis.slice(0, 260),
  ].join("|");
}

function buildSlPriorityDuplicateKeys() {
  const seen = new Map();
  state.allQuestions.forEach((q) => {
    const key = buildCrossLevelDuplicateKey(q);
    if (!key) {
      return;
    }
    const level = inferLevel(q);
    if (!seen.has(key)) {
      seen.set(key, new Set());
    }
    seen.get(key).add(level);
  });

  state.slPriorityDuplicateKeys = new Set(
    [...seen.entries()].filter(([, levels]) => levels.has("SL") && levels.has("HL")).map(([key]) => key)
  );
}

function shouldHideAsCrossLevelDuplicate(q) {
  if (inferLevel(q) !== "HL") {
    return false;
  }
  const key = buildCrossLevelDuplicateKey(q);
  if (!key) {
    return false;
  }
  return state.slPriorityDuplicateKeys.has(key);
}

function filterQuestionsByBundle() {
  const bundle = state.paperBundle;
  const selectedTopic = topicFilter.value;
  const selectedSubtopic = subtopicFilter.value;
  const selectedDifficulty = difficultyFilter.value;
  const selectedSaved = savedFilter.value;
  const searchTerm = searchInput.value.trim();

  let rows = state.allQuestions.filter((q) => {
    const meta = parsePaperMeta(q.paper);
    if (!meta) {
      return false;
    }
    const examMatch =
      meta.year === bundle.year &&
      meta.session === bundle.session &&
      meta.paperNo === bundle.paperNo &&
      meta.timezone === bundle.timezone;
    if (!examMatch) {
      return false;
    }

    if (bundle.level === "SL" && inferLevel(q) !== "SL") {
      return false;
    }
    const topicMatch = !selectedTopic || q.topic === selectedTopic;
    const subtopicMatch = !selectedSubtopic || q.subtopic === selectedSubtopic;
    const difficultyMatch = !selectedDifficulty || inferDifficulty(q) === selectedDifficulty;
    const action = getUserAction(q.id);
    const savedMatch = !selectedSaved || (selectedSaved === "saved" ? action.saved : action.done);
    const searchMatch = matchesSearchQuery(q, searchTerm, inferLevel(q));
    const duplicateMatch = !shouldHideAsCrossLevelDuplicate(q);
    return topicMatch && subtopicMatch && difficultyMatch && savedMatch && searchMatch && duplicateMatch;
  });

  if (bundle.level === "HL") {
    const byQNum = new Map();
    rows.forEach((q) => {
      const qn = String(q.question_number || "");
      const existing = byQNum.get(qn);
      if (!existing) {
        byQNum.set(qn, q);
        return;
      }
      const currLevel = inferLevel(q);
      const prevLevel = inferLevel(existing);
      if (currLevel === "SL" && prevLevel !== "SL") {
        byQNum.set(qn, q);
      }
    });
    rows = [...byQNum.values()];
  }

  rows.sort((a, b) => Number(a.question_number || 0) - Number(b.question_number || 0));
  return rows;
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
  const markschemeDetails = node.querySelector("details");

  const marks = Number.isFinite(q.marks) ? `${q.marks} marks` : "marks n/a";
  node.querySelector(".meta").textContent = `${q.paper || "Unknown paper"} | ${q.topic || "Unsorted"} | ${q.subtopic || "Unsorted"} | ${marks}`;
  const hasMarkscheme = q.has_markscheme !== false;
  if (!hasMarkscheme && tagsEl) {
    const badge = document.createElement("span");
    badge.className = "difficulty-tag difficulty-medium";
    badge.textContent = "No markscheme";
    tagsEl.appendChild(badge);
  }

  const qImages = Array.isArray(q.question_image_paths) ? q.question_image_paths : [];
  const msImages = Array.isArray(q.markscheme_image_paths) ? q.markscheme_image_paths : [];
  const hasAnyImage = qImages.length > 0 || msImages.length > 0;
  const questionNumber = `${q.question_number || ""}`.trim();
  const fallbackTitle = questionNumber ? `Q${questionNumber}` : "Question";

  if (hasAnyImage) {
    titleEl.textContent = fallbackTitle;
  } else {
    titleEl.textContent = cleanPreviewText(q.title || "") || fallbackTitle;
  }

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
    if (action.saved) {
      saveBtn.classList.add("active");
    }
    saveBtn.addEventListener("click", () => {
      const current = getUserAction(q.id);
      state.userActions[q.id] = { ...current, saved: !current.saved };
      persistUserActions();
      renderQuestions(true);
    });
  }
  if (doneBtn) {
    doneBtn.textContent = action.done ? "Done" : "Mark done";
    if (action.done) {
      doneBtn.classList.add("active");
    }
    doneBtn.addEventListener("click", () => {
      const current = getUserAction(q.id);
      state.userActions[q.id] = { ...current, done: !current.done };
      persistUserActions();
      renderQuestions(true);
    });
  }
  const examLocked = state.examMode.enabled && state.examMode.started && !state.examMode.ended;
  if (examLocked) {
    sideBySideBtn.hidden = true;
    if (markschemeDetails) {
      markschemeDetails.hidden = true;
    }
  } else {
    sideBySideBtn.hidden = false;
    if (markschemeDetails) {
      markschemeDetails.hidden = false;
    }
  }
  sideBySideBtn.addEventListener("click", () => openCompareModal(q));

  if (qImages.length > 0) {
    qImages.forEach((imgPath, index) => {
      const img = createImageWithFallback(imgPath, `Question ${q.question_number || ""} image ${index + 1}`);
      questionImagesEl.appendChild(img);
    });
    questionTextEl.hidden = true;
  } else {
    questionTextEl.textContent = q.question_text || "";
    questionTextEl.hidden = false;
  }

  if (msImages.length > 0) {
    msImages.forEach((imgPath, index) => {
      const img = createImageWithFallback(imgPath, `Markscheme ${q.question_number || ""} image ${index + 1}`);
      markschemeImagesEl.appendChild(img);
    });
    answerTextEl.hidden = true;
  } else {
    answerTextEl.textContent = q.answer_text || "No answer extracted yet.";
    answerTextEl.hidden = false;
  }

  return node;
}

function openCompareModal(q) {
  if (!compareModal || !compareQuestionBody || !compareMarkschemeBody || !compareTitle) {
    return;
  }

  compareQuestionBody.innerHTML = "";
  compareMarkschemeBody.innerHTML = "";

  const qImages = Array.isArray(q.question_image_paths) ? q.question_image_paths : [];
  const msImages = Array.isArray(q.markscheme_image_paths) ? q.markscheme_image_paths : [];

  if (qImages.length > 0) {
    qImages.forEach((imgPath, index) => {
      compareQuestionBody.appendChild(
        createImageWithFallback(imgPath, `Question ${q.question_number || ""} image ${index + 1}`)
      );
    });
  } else {
    const p = document.createElement("p");
    p.className = "compare-fallback";
    p.textContent = q.question_text || "No extracted question text.";
    compareQuestionBody.appendChild(p);
  }

  if (msImages.length > 0) {
    msImages.forEach((imgPath, index) => {
      compareMarkschemeBody.appendChild(
        createImageWithFallback(imgPath, `Markscheme ${q.question_number || ""} image ${index + 1}`)
      );
    });
  } else {
    const p = document.createElement("p");
    p.className = "compare-fallback";
    p.textContent = q.answer_text || "No extracted markscheme text.";
    compareMarkschemeBody.appendChild(p);
  }

  const qLabel = `${q.question_number || ""}`.trim();
  compareTitle.textContent = qLabel ? `Side by side - Q${qLabel}` : "Side by side view";
  compareModal.hidden = false;
  document.body.style.overflow = "hidden";
}

function closeCompareModal() {
  if (!compareModal || !compareQuestionBody || !compareMarkschemeBody) {
    return;
  }
  compareModal.hidden = true;
  compareQuestionBody.innerHTML = "";
  compareMarkschemeBody.innerHTML = "";
  document.body.style.overflow = "";
}

function formatDuration(seconds) {
  const s = Math.max(0, Math.floor(seconds));
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  const sec = s % 60;
  if (h > 0) {
    return `${h}:${String(m).padStart(2, "0")}:${String(sec).padStart(2, "0")}`;
  }
  return `${m}:${String(sec).padStart(2, "0")}`;
}

function stopExamTimer() {
  if (state.examMode.timerId) {
    clearInterval(state.examMode.timerId);
    state.examMode.timerId = null;
  }
}

function updateExamBarText() {
  if (!examModeInfo || !state.examMode.enabled) {
    return;
  }
  if (!state.examMode.started && !state.examMode.ended) {
    examModeInfo.textContent = `Exam mode ready • duration ${formatDuration(state.examMode.durationSeconds)}`;
    return;
  }
  if (state.examMode.started && !state.examMode.ended) {
    const remaining = Math.max(0, Math.floor((state.examMode.endTs - Date.now()) / 1000));
    examModeInfo.textContent = `Exam mode running • time left ${formatDuration(remaining)}`;
    return;
  }
  examModeInfo.textContent = "Exam mode complete • markschemes unlocked";
}

function finishExamMode() {
  stopExamTimer();
  state.examMode.started = false;
  state.examMode.ended = true;
  if (examModeStartBtn) {
    examModeStartBtn.hidden = true;
  }
  if (examModeEndBtn) {
    examModeEndBtn.hidden = true;
  }
  updateExamBarText();
  renderQuestions(true);
}

function startExamMode() {
  state.examMode.started = true;
  state.examMode.ended = false;
  state.examMode.endTs = Date.now() + state.examMode.durationSeconds * 1000;
  if (examModeStartBtn) {
    examModeStartBtn.hidden = true;
  }
  if (examModeEndBtn) {
    examModeEndBtn.hidden = false;
  }
  updateExamBarText();
  renderQuestions(true);
  stopExamTimer();
  state.examMode.timerId = setInterval(() => {
    const remaining = Math.floor((state.examMode.endTs - Date.now()) / 1000);
    if (remaining <= 0) {
      finishExamMode();
      return;
    }
    updateExamBarText();
  }, 1000);
}

function setupExamModeUi() {
  if (
    !state.paperBundle ||
    !state.examMode.enabled ||
    !examModeBar ||
    !examModeInfo ||
    !examModeStartBtn ||
    !examModeEndBtn
  ) {
    return;
  }
  examModeBar.hidden = false;
  examModeStartBtn.hidden = false;
  examModeEndBtn.hidden = true;
  updateExamBarText();
  examModeStartBtn.addEventListener("click", startExamMode);
  examModeEndBtn.addEventListener("click", finishExamMode);
}

function updateResultSummary() {
  const total = state.filteredQuestions.length;
  const shown = Math.min(state.visibleCount, total);
  resultCount.textContent = total === 0 ? "0 question(s)" : `Showing ${shown} of ${total} question(s)`;
  const hasMore = shown < total;
  loadMoreWrap.style.display = hasMore ? "block" : "none";
}

function renderQuestions(reset = true) {
  if (reset) {
    state.filteredQuestions = filterQuestions();
    state.visibleCount = Math.min(PAGE_SIZE, state.filteredQuestions.length);
    questionList.innerHTML = "";

    if (state.filteredQuestions.length === 0) {
      resultCount.textContent = "0 question(s)";
      if (state.paperBundle && state.paperSourceFile) {
        const relPath = state.paperSourcePath || `raw/papers/${state.paperSourceFile}`;
        const safePath = relPath
          .split("/")
          .filter(Boolean)
          .map((part) => encodeURIComponent(part))
          .join("/");
        const paperUrl = `/data/${safePath}`;
        const msNote = state.paperNoMarkscheme
          ? '<p class="paper-only-note">No markscheme available for this paper yet.</p>'
          : "";
        questionList.innerHTML = `
          <article class="question-card paper-only-card">
            <h3 class="title">Paper available as PDF</h3>
            <p class="meta">${state.paperBundle.session} ${state.paperBundle.year} Paper ${state.paperBundle.paperNo} ${state.paperBundle.timezone} ${state.paperBundle.level}</p>
            ${msNote}
            <p class="question">This paper is currently scan-only, so it has not been split into individual questions yet.</p>
            <a class="hero-link" href="${paperUrl}" target="_blank" rel="noopener noreferrer">Open Paper PDF</a>
          </article>
        `;
      } else {
        questionList.innerHTML = "<p>No matches yet.</p>";
      }
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

function cleanPreviewText(text) {
  return String(text || "")
    .replace(/\s+/g, " ")
    .replace(/\/g\d+/gi, " ")
    .replace(/[]/g, " ")
    .replace(/\.{3,}/g, "...")
    .trim();
}

function inferDifficulty(q) {
  const marks = Number(q?.marks || 0);
  const level = inferLevel(q);
  const paperType = String(q?.paper_type || "").toLowerCase();
  const paperMatch = paperType.match(/paper\s*([123])/);
  const paperNo = paperMatch ? Number(paperMatch[1]) : 0;

  let score = 0;
  if (marks >= 11) {
    score += 2;
  } else if (marks >= 7) {
    score += 1;
  }

  if (level === "HL") {
    score += 1;
  }
  if (paperNo === 3) {
    score += 1;
  } else if (paperNo === 2) {
    score += 0.5;
  }

  if (marks <= 4 && level === "SL" && paperNo === 1) {
    score -= 1;
  }

  if (score <= 0) {
    return "Easy";
  }
  if (score <= 2) {
    return "Medium";
  }
  return "Hard";
}

function legacyImageRelPath(relPath) {
  return String(relPath || "").replace(/_(sl|hl)(?=(_p\d+)?\.png$)/i, "");
}

function createImageWithFallback(relPath, altText) {
  const img = document.createElement("img");
  img.alt = altText;
  img.loading = "lazy";
  img.src = `../data/physics/processed/${relPath}`;
  const legacyRelPath = legacyImageRelPath(relPath);
  if (legacyRelPath !== relPath) {
    img.addEventListener(
      "error",
      () => {
        img.src = `../data/physics/processed/${legacyRelPath}`;
      },
      { once: true }
    );
  }
  return img;
}

function applyInitialQueryFilters() {
  const params = new URLSearchParams(window.location.search);
  const bundle = params.get("bundle");
  const level = params.get("level");
  const paperType = params.get("paperType");
  const paper = params.get("paper");
  const year = params.get("year");
  const session = params.get("session");
  const tz = params.get("tz");
  const paperNo = params.get("paperNo");
  const topic = params.get("topic");
  const subtopic = params.get("subtopic");
  const difficulty = params.get("difficulty");
  const search = params.get("search");
  const exam = params.get("exam");
  const durationMin = params.get("durationMin");
  const sourcePaper = params.get("sourcePaper");
  const sourcePaperPath = params.get("sourcePaperPath");
  const noMs = params.get("noMs");

  if (bundle === "1" && level && year && session && tz && paperNo) {
    state.paperBundle = {
      level,
      year: Number(year),
      session,
      timezone: tz,
      paperNo: Number(paperNo),
    };
    state.paperSourceFile = sourcePaper || "";
    state.paperSourcePath = sourcePaperPath || "";
    state.paperNoMarkscheme = noMs === "1";
    if ([...levelFilter.options].some((o) => o.value === level)) {
      levelFilter.value = level;
    }
    const pType = `Paper ${paperNo}`;
    if ([...paperTypeFilter.options].some((o) => o.value === pType)) {
      paperTypeFilter.value = pType;
    }
    // Exam mode is only allowed from the AA Papers flow (bundle mode).
    if (exam === "1" && durationMin) {
      const mins = Number(durationMin);
      if (Number.isFinite(mins) && mins > 0) {
        state.examMode.enabled = true;
        state.examMode.durationSeconds = Math.round(mins * 60);
      }
    }
    return;
  }

  if (level && [...levelFilter.options].some((o) => o.value === level)) {
    levelFilter.value = level;
  }
  if (paperType && [...paperTypeFilter.options].some((o) => o.value === paperType)) {
    paperTypeFilter.value = paperType;
  }
  if (paper && [...paperFilter.options].some((o) => o.value === paper)) {
    paperFilter.value = paper;
  }
  if (topic && [...topicFilter.options].some((o) => o.value === topic)) {
    topicFilter.value = topic;
    updateSubtopicOptions();
  }
  if (subtopic && [...subtopicFilter.options].some((o) => o.value === subtopic)) {
    subtopicFilter.value = subtopic;
  }
  if (difficulty && [...difficultyFilter.options].some((o) => o.value === difficulty)) {
    difficultyFilter.value = difficulty;
  }
  if (search) {
    searchInput.value = search;
  }
}

function bindEvents() {
  levelFilter.addEventListener("change", () => renderQuestions(true));
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
  if (compareBackdrop) {
    compareBackdrop.addEventListener("click", closeCompareModal);
  }
  if (compareCloseBtn) {
    compareCloseBtn.addEventListener("click", closeCompareModal);
  }
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && compareModal && !compareModal.hidden) {
      closeCompareModal();
    }
  });
}

async function start() {
  try {
    loadUserActions();
    await loadData();
    hydrateFilters();
    applyInitialQueryFilters();
    if (!state.paperBundle) {
      state.examMode.enabled = false;
      if (examModeBar) {
        examModeBar.remove();
      }
    }
    setupExamModeUi();
    bindEvents();
    renderQuestions(true);
  } catch (error) {
    questionList.innerHTML = `<p>Failed to load data: ${error.message}</p>`;
  }
}

start();
