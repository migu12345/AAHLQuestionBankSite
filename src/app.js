const state = {
  allQuestions: [],
  topics: [],
  filteredQuestions: [],
  visibleCount: 0,
};
const PAGE_SIZE = 10;

const paperTypeFilter = document.getElementById("paperTypeFilter");
const paperFilter = document.getElementById("paperFilter");
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
    fetch("/data/processed/questions.json"),
    fetch("/data/topic-map.json"),
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
  const selectedLevel = levelFilter.value;
  const selectedPaperType = paperTypeFilter.value;
  const selectedPaper = paperFilter.value;
  const selectedTopic = topicFilter.value;
  const selectedSubtopic = subtopicFilter.value;
  const searchTerm = searchInput.value.trim();

  return state.allQuestions.filter((q) => {
    const level = inferLevel(q);
    const levelMatch = !selectedLevel || level === selectedLevel;
    const paperTypeMatch = !selectedPaperType || q.paper_type === selectedPaperType;
    const paperMatch = !selectedPaper || q.paper === selectedPaper;
    const topicMatch = !selectedTopic || q.topic === selectedTopic;
    const subtopicMatch = !selectedSubtopic || q.subtopic === selectedSubtopic;
    const searchMatch = matchesSearchQuery(q, searchTerm, level);

    return levelMatch && paperTypeMatch && paperMatch && topicMatch && subtopicMatch && searchMatch;
  });
}

function buildQuestionNode(q) {
  const node = questionTemplate.content.cloneNode(true);
  const questionImagesEl = node.querySelector(".question-images");
  const markschemeImagesEl = node.querySelector(".markscheme-images");
  const questionTextEl = node.querySelector(".question");
  const answerTextEl = node.querySelector(".answer");
  const titleEl = node.querySelector(".title");

  const marks = Number.isFinite(q.marks) ? `${q.marks} marks` : "marks n/a";
  node.querySelector(".meta").textContent = `${q.paper || "Unknown paper"} | ${q.topic || "Unsorted"} | ${q.subtopic || "Unsorted"} | ${marks}`;

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
      questionList.innerHTML = "<p>No matches yet.</p>";
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

function legacyImageRelPath(relPath) {
  return String(relPath || "").replace(/_(sl|hl)(?=(_p\d+)?\.png$)/i, "");
}

function createImageWithFallback(relPath, altText) {
  const img = document.createElement("img");
  img.alt = altText;
  img.loading = "lazy";
  img.src = `../data/processed/${relPath}`;
  const legacyRelPath = legacyImageRelPath(relPath);
  if (legacyRelPath !== relPath) {
    img.addEventListener(
      "error",
      () => {
        img.src = `../data/processed/${legacyRelPath}`;
      },
      { once: true }
    );
  }
  return img;
}

function bindEvents() {
  levelFilter.addEventListener("change", () => renderQuestions(true));
  paperTypeFilter.addEventListener("change", () => renderQuestions(true));
  paperFilter.addEventListener("change", () => renderQuestions(true));

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
}

async function start() {
  try {
    await loadData();
    hydrateFilters();
    bindEvents();
    renderQuestions(true);
  } catch (error) {
    questionList.innerHTML = `<p>Failed to load data: ${error.message}</p>`;
  }
}

start();
