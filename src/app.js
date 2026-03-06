const state = {
  allQuestions: [],
  topics: [],
};

const paperTypeFilter = document.getElementById("paperTypeFilter");
const paperFilter = document.getElementById("paperFilter");
const topicFilter = document.getElementById("topicFilter");
const subtopicFilter = document.getElementById("subtopicFilter");
const searchInput = document.getElementById("searchInput");
const questionList = document.getElementById("questionList");
const resultCount = document.getElementById("resultCount");
const questionTemplate = document.getElementById("questionTemplate");

async function loadData() {
  const [questionRes, topicRes] = await Promise.all([
    fetch("../data/processed/questions.json"),
    fetch("../data/topic-map.json"),
  ]);

  const questionData = await questionRes.json();
  const topicData = await topicRes.json();

  state.allQuestions = questionData.questions || [];
  state.topics = topicData.topics || [];
}

function hydrateFilters() {
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

function filterQuestions() {
  const selectedPaperType = paperTypeFilter.value;
  const selectedPaper = paperFilter.value;
  const selectedTopic = topicFilter.value;
  const selectedSubtopic = subtopicFilter.value;
  const searchTerm = searchInput.value.trim().toLowerCase();

  return state.allQuestions.filter((q) => {
    const paperTypeMatch = !selectedPaperType || q.paper_type === selectedPaperType;
    const paperMatch = !selectedPaper || q.paper === selectedPaper;
    const topicMatch = !selectedTopic || q.topic === selectedTopic;
    const subtopicMatch = !selectedSubtopic || q.subtopic === selectedSubtopic;
    const text = `${q.title || ""} ${q.question_text || ""} ${q.answer_text || ""}`.toLowerCase();
    const searchMatch = !searchTerm || text.includes(searchTerm);

    return paperTypeMatch && paperMatch && topicMatch && subtopicMatch && searchMatch;
  });
}

function renderQuestions() {
  const questions = filterQuestions();
  questionList.innerHTML = "";
  resultCount.textContent = `${questions.length} question(s)`;

  if (questions.length === 0) {
    questionList.innerHTML = "<p>No matches yet.</p>";
    return;
  }

  questions.forEach((q) => {
    const node = questionTemplate.content.cloneNode(true);
    const questionImagesEl = node.querySelector(".question-images");
    const markschemeImagesEl = node.querySelector(".markscheme-images");
    const questionTextEl = node.querySelector(".question");
    const answerTextEl = node.querySelector(".answer");

    const marks = Number.isFinite(q.marks) ? `${q.marks} marks` : "marks n/a";
    node.querySelector(".meta").textContent = `${q.paper || "Unknown paper"} | ${q.topic || "Unsorted"} | ${q.subtopic || "Unsorted"} | ${marks}`;
    node.querySelector(".title").textContent = q.title || "Untitled question";

    const qImages = Array.isArray(q.question_image_paths) ? q.question_image_paths : [];
    const msImages = Array.isArray(q.markscheme_image_paths) ? q.markscheme_image_paths : [];

    if (qImages.length > 0) {
      qImages.forEach((imgPath, index) => {
        const img = document.createElement("img");
        img.src = `../data/processed/${imgPath}`;
        img.alt = `Question ${q.question_number || ""} image ${index + 1}`;
        img.loading = "lazy";
        questionImagesEl.appendChild(img);
      });
      questionTextEl.hidden = true;
    } else {
      questionTextEl.textContent = q.question_text || "";
      questionTextEl.hidden = false;
    }

    if (msImages.length > 0) {
      msImages.forEach((imgPath, index) => {
        const img = document.createElement("img");
        img.src = `../data/processed/${imgPath}`;
        img.alt = `Markscheme ${q.question_number || ""} image ${index + 1}`;
        img.loading = "lazy";
        markschemeImagesEl.appendChild(img);
      });
      answerTextEl.hidden = true;
    } else {
      answerTextEl.textContent = q.answer_text || "No answer extracted yet.";
      answerTextEl.hidden = false;
    }

    questionList.appendChild(node);
  });
}

function bindEvents() {
  paperTypeFilter.addEventListener("change", renderQuestions);
  paperFilter.addEventListener("change", renderQuestions);

  topicFilter.addEventListener("change", () => {
    updateSubtopicOptions();
    renderQuestions();
  });

  subtopicFilter.addEventListener("change", renderQuestions);
  searchInput.addEventListener("input", renderQuestions);
}

async function start() {
  try {
    await loadData();
    hydrateFilters();
    bindEvents();
    renderQuestions();
  } catch (error) {
    questionList.innerHTML = `<p>Failed to load data: ${error.message}</p>`;
  }
}

start();
