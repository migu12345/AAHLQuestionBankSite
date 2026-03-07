const state = {
  allQuestions: [],
  markschemesById: {},
  markschemeImagesById: {},
  filteredQuestions: [],
  visibleCount: 0,
};
const PAGE_SIZE = 10;

const searchTutorInput = document.getElementById("searchTutorInput");
const subtopicFilter = document.getElementById("subtopicFilter");
const sourceFilter = document.getElementById("sourceFilter");
const tutorCount = document.getElementById("tutorCount");
const tutorQuestionList = document.getElementById("tutorQuestionList");
const tutorQuestionTemplate = document.getElementById("tutorQuestionTemplate");
const tutorLoadMoreWrap = document.getElementById("tutorLoadMoreWrap");
const tutorLoadMoreBtn = document.getElementById("tutorLoadMoreBtn");

async function loadData() {
  const [qRes, msRes] = await Promise.all([
    fetch("/data/tutoring/processed/questions.json"),
    fetch("/data/tutoring/processed/markschemes.json"),
  ]);
  const qData = await qRes.json();
  const msData = await msRes.json();

  state.allQuestions = Array.isArray(qData.questions) ? qData.questions : [];
  const markschemes = Array.isArray(msData.questions) ? msData.questions : [];
  state.markschemesById = Object.fromEntries(
    markschemes.map((entry) => [entry.id, entry.worked_solution_text || "No worked solution yet."])
  );
  state.markschemeImagesById = Object.fromEntries(
    markschemes.map((entry) => [entry.id, Array.isArray(entry.markscheme_image_paths) ? entry.markscheme_image_paths : []])
  );
}

function hydrateFilters() {
  const subtopics = [...new Set(state.allQuestions.map((q) => q.subtopic).filter(Boolean))].sort();
  const sources = [...new Set(state.allQuestions.map((q) => q.source_file).filter(Boolean))].sort();

  subtopics.forEach((subtopic) => {
    const option = document.createElement("option");
    option.value = subtopic;
    option.textContent = subtopic;
    subtopicFilter.appendChild(option);
  });

  sources.forEach((source) => {
    const option = document.createElement("option");
    option.value = source;
    option.textContent = source;
    sourceFilter.appendChild(option);
  });
}

function normalizeForSearch(value) {
  return String(value || "")
    .toLowerCase()
    .normalize("NFKD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/[^a-z0-9]+/g, " ")
    .trim();
}

function matchesSearchToken(q, token, normalizedHaystack) {
  if (!token) {
    return true;
  }
  const questionMatch = token.match(/^q(\d{1,3})$/);
  if (questionMatch) {
    return String(q.question_number || "") === questionMatch[1];
  }
  return normalizedHaystack.includes(token);
}

function matchesSearchQuery(q, rawQuery) {
  const query = normalizeForSearch(rawQuery);
  if (!query) {
    return true;
  }

  const tokens = query.split(/\s+/).filter(Boolean);
  const normalizedHaystack = normalizeForSearch(
    [q.title, q.question_text, q.source_file, q.topic, q.subtopic, q.question_number].join(" ")
  );

  return tokens.every((token) => matchesSearchToken(q, token, normalizedHaystack));
}

function filteredQuestions() {
  const searchTerm = searchTutorInput.value.trim();
  const subtopic = subtopicFilter.value;
  const source = sourceFilter.value;

  return state.allQuestions.filter((q) => {
    const subtopicMatch = !subtopic || q.subtopic === subtopic;
    const sourceMatch = !source || q.source_file === source;
    const searchMatch = matchesSearchQuery(q, searchTerm);
    return subtopicMatch && sourceMatch && searchMatch;
  });
}

function buildTutorNode(q) {
  const node = tutorQuestionTemplate.content.cloneNode(true);
  const questionImagesEl = node.querySelector(".question-images");
  const markschemeImagesEl = node.querySelector(".markscheme-images");
  const questionTextEl = node.querySelector(".question");
  const markschemeTextEl = node.querySelector(".answer");
  node.querySelector(".meta").textContent = `${q.topic} | ${q.subtopic} | ${q.source_file}`;
  node.querySelector(".title").textContent = `${q.title || "Question"} (${q.source_file || "Unknown file"})`;

  const qImages = Array.isArray(q.question_image_paths) ? q.question_image_paths : [];
  if (qImages.length > 0) {
    qImages.forEach((imgPath, index) => {
      const img = document.createElement("img");
      img.src = `/data/tutoring/processed/${imgPath}`;
      img.alt = `Tutor question ${q.question_number || ""} image ${index + 1}`;
      img.loading = "lazy";
      questionImagesEl.appendChild(img);
    });
    questionTextEl.hidden = true;
  } else {
    questionTextEl.textContent = q.question_text || "";
    questionTextEl.hidden = false;
  }

  const msImages = state.markschemeImagesById[q.id] || [];
  if (msImages.length > 0) {
    msImages.forEach((imgPath, index) => {
      const img = document.createElement("img");
      img.src = `/data/tutoring/processed/${imgPath}`;
      img.alt = `Tutor markscheme ${q.question_number || ""} image ${index + 1}`;
      img.loading = "lazy";
      markschemeImagesEl.appendChild(img);
    });
    markschemeTextEl.hidden = true;
  } else {
    markschemeTextEl.textContent = state.markschemesById[q.id] || "No markscheme available.";
    markschemeTextEl.hidden = false;
  }

  return node;
}

function updateTutorSummary() {
  const total = state.filteredQuestions.length;
  const shown = Math.min(state.visibleCount, total);
  tutorCount.textContent = total === 0 ? "0 question(s)" : `Showing ${shown} of ${total} question(s)`;
  tutorLoadMoreWrap.style.display = shown < total ? "block" : "none";
}

function render(reset = true) {
  if (reset) {
    state.filteredQuestions = filteredQuestions();
    state.visibleCount = Math.min(PAGE_SIZE, state.filteredQuestions.length);
    tutorQuestionList.innerHTML = "";

    if (state.filteredQuestions.length === 0) {
      tutorCount.textContent = "0 question(s)";
      tutorQuestionList.innerHTML = "<p>No matches found.</p>";
      tutorLoadMoreWrap.style.display = "none";
      return;
    }

    state.filteredQuestions.slice(0, state.visibleCount).forEach((q) => {
      tutorQuestionList.appendChild(buildTutorNode(q));
    });
    updateTutorSummary();
    return;
  }

  const currentShown = Math.min(state.visibleCount, state.filteredQuestions.length);
  const newShown = Math.min(currentShown + PAGE_SIZE, state.filteredQuestions.length);
  state.filteredQuestions.slice(currentShown, newShown).forEach((q) => {
    tutorQuestionList.appendChild(buildTutorNode(q));
  });
  state.visibleCount = newShown;
  updateTutorSummary();
}

function bindEvents() {
  searchTutorInput.addEventListener("input", () => render(true));
  subtopicFilter.addEventListener("change", () => render(true));
  sourceFilter.addEventListener("change", () => render(true));
  tutorLoadMoreBtn.addEventListener("click", () => render(false));
}

async function start() {
  try {
    await loadData();
    hydrateFilters();
    bindEvents();
    render(true);
  } catch (error) {
    tutorQuestionList.innerHTML = `<p>Failed to load tutoring questions: ${error.message}</p>`;
  }
}

start();
