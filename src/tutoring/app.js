const state = {
  allQuestions: [],
  markschemesById: {},
  markschemeImagesById: {},
};

const searchTutorInput = document.getElementById("searchTutorInput");
const subtopicFilter = document.getElementById("subtopicFilter");
const sourceFilter = document.getElementById("sourceFilter");
const tutorCount = document.getElementById("tutorCount");
const tutorQuestionList = document.getElementById("tutorQuestionList");
const tutorQuestionTemplate = document.getElementById("tutorQuestionTemplate");

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

function filteredQuestions() {
  const searchTerm = searchTutorInput.value.trim().toLowerCase();
  const subtopic = subtopicFilter.value;
  const source = sourceFilter.value;

  return state.allQuestions.filter((q) => {
    const subtopicMatch = !subtopic || q.subtopic === subtopic;
    const sourceMatch = !source || q.source_file === source;
    const text = `${q.title || ""} ${q.question_text || ""} ${q.source_file || ""}`.toLowerCase();
    const searchMatch = !searchTerm || text.includes(searchTerm);
    return subtopicMatch && sourceMatch && searchMatch;
  });
}

function render() {
  const questions = filteredQuestions();
  tutorQuestionList.innerHTML = "";
  tutorCount.textContent = `${questions.length} question(s)`;

  if (questions.length === 0) {
    tutorQuestionList.innerHTML = "<p>No matches found.</p>";
    return;
  }

  questions.forEach((q) => {
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

    tutorQuestionList.appendChild(node);
  });
}

function bindEvents() {
  searchTutorInput.addEventListener("input", render);
  subtopicFilter.addEventListener("change", render);
  sourceFilter.addEventListener("change", render);
}

async function start() {
  try {
    await loadData();
    hydrateFilters();
    bindEvents();
    render();
  } catch (error) {
    tutorQuestionList.innerHTML = `<p>Failed to load tutoring questions: ${error.message}</p>`;
  }
}

start();
