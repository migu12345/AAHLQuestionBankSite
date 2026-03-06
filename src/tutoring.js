const STORAGE_KEY = "aahl_tutoring_question_bank_v1";

const tutorForm = document.getElementById("tutorForm");
const titleInput = document.getElementById("titleInput");
const unitInput = document.getElementById("unitInput");
const sourceInput = document.getElementById("sourceInput");
const questionInput = document.getElementById("questionInput");
const answerInput = document.getElementById("answerInput");
const searchTutorInput = document.getElementById("searchTutorInput");
const clearAllBtn = document.getElementById("clearAllBtn");
const tutorCount = document.getElementById("tutorCount");
const tutorQuestionList = document.getElementById("tutorQuestionList");
const tutorQuestionTemplate = document.getElementById("tutorQuestionTemplate");

let entries = [];

function loadEntries() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    entries = raw ? JSON.parse(raw) : [];
  } catch (_error) {
    entries = [];
  }
}

function saveEntries() {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(entries));
}

function formatDate(iso) {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return "Unknown date";
  return date.toLocaleDateString();
}

function filteredEntries() {
  const term = searchTutorInput.value.trim().toLowerCase();
  if (!term) return entries;

  return entries.filter((entry) => {
    const text = `${entry.title} ${entry.unit} ${entry.source} ${entry.question} ${entry.answer}`.toLowerCase();
    return text.includes(term);
  });
}

function renderEntries() {
  const data = filteredEntries();
  tutorQuestionList.innerHTML = "";
  tutorCount.textContent = `${data.length} saved question(s)`;

  if (data.length === 0) {
    tutorQuestionList.innerHTML = "<p>No tutor questions saved yet.</p>";
    return;
  }

  data.forEach((entry) => {
    const node = tutorQuestionTemplate.content.cloneNode(true);
    node.querySelector(".meta").textContent = `${entry.unit} | ${entry.source || "No source"} | ${formatDate(entry.createdAt)}`;
    node.querySelector(".title").textContent = entry.title || "Untitled";
    node.querySelector(".question").textContent = entry.question;
    node.querySelector(".answer").textContent = entry.answer || "No answer/notes added.";

    const deleteBtn = node.querySelector(".danger-btn");
    deleteBtn.addEventListener("click", () => {
      entries = entries.filter((item) => item.id !== entry.id);
      saveEntries();
      renderEntries();
    });

    tutorQuestionList.appendChild(node);
  });
}

function addEntry(event) {
  event.preventDefault();
  const randomId =
    typeof crypto !== "undefined" && crypto.randomUUID
      ? crypto.randomUUID()
      : `${Date.now()}_${Math.random().toString(16).slice(2)}`;

  const entry = {
    id: randomId,
    createdAt: new Date().toISOString(),
    title: titleInput.value.trim(),
    unit: unitInput.value,
    source: sourceInput.value.trim(),
    question: questionInput.value.trim(),
    answer: answerInput.value.trim(),
  };

  entries.unshift(entry);
  saveEntries();
  tutorForm.reset();
  renderEntries();
}

function clearAllEntries() {
  if (!confirm("Delete all saved tutor questions?")) return;
  entries = [];
  saveEntries();
  renderEntries();
}

function bindEvents() {
  tutorForm.addEventListener("submit", addEntry);
  searchTutorInput.addEventListener("input", renderEntries);
  clearAllBtn.addEventListener("click", clearAllEntries);
}

function start() {
  loadEntries();
  bindEvents();
  renderEntries();
}

start();
