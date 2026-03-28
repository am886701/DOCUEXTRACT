const uploadForm = document.getElementById("upload-form");
const askForm = document.getElementById("ask-form");
const fileInput = document.getElementById("file-input");
const selectedFile = document.getElementById("selected-file");
const questionInput = document.getElementById("question-input");
const uploadStatus = document.getElementById("upload-status");
const questionStatus = document.getElementById("question-status");
const answerBox = document.getElementById("answer-box");
const answerMeta = document.getElementById("answer-meta");
const sourcesList = document.getElementById("sources-list");
const uploadButton = document.getElementById("upload-button");
const askButton = document.getElementById("ask-button");
const documentsCount = document.getElementById("documents-count");
const chunksCount = document.getElementById("chunks-count");
const historyCount = document.getElementById("history-count");
const historyStatus = document.getElementById("history-status");
const historyList = document.getElementById("history-list");

function setStatus(element, message, tone = "neutral") {
  element.textContent = message;
  element.dataset.tone = tone;
}

function setBusy(button, busyText, isBusy) {
  button.disabled = isBusy;
  button.textContent = isBusy ? busyText : button.dataset.defaultLabel;
}

function renderSources(sources) {
  sourcesList.innerHTML = "";
  sourcesList.classList.toggle("empty-list", sources.length === 0);

  if (sources.length === 0) {
    const item = document.createElement("li");
    item.textContent = "No sources yet.";
    sourcesList.appendChild(item);
    return;
  }

  sources.forEach((source) => {
    const item = document.createElement("li");
    item.textContent = typeof source === "string" ? source : `${source.document_name} - Page ${source.page}`;
    sourcesList.appendChild(item);
  });
}

function renderHistory(items) {
  historyList.innerHTML = "";
  historyCount.textContent = String(items.length);

  if (items.length === 0) {
    historyList.innerHTML = '<article class="history-empty">No questions asked yet.</article>';
    setStatus(historyStatus, "History will appear here after your first question.", "neutral");
    return;
  }

  setStatus(historyStatus, "Click a previous question to reopen its answer.", "success");

  items.forEach((item) => {
    const entry = document.createElement("button");
    entry.type = "button";
    entry.className = "history-item";
    entry.innerHTML = `
      <span class="history-question">${item.question}</span>
      <span class="history-meta">${item.used_gemini ? "Gemini answer" : "Retrieval answer"} • ${item.created_at}</span>
    `;
    entry.addEventListener("click", () => {
      questionInput.value = item.question;
      answerBox.textContent = item.answer;
      answerBox.classList.remove("muted");
      setStatus(answerMeta, `Showing saved answer from history #${item.id}.`, "success");
      setStatus(questionStatus, "Loaded a previous question into the workspace.", "success");
      renderSources(item.sources);
    });
    historyList.appendChild(entry);
  });
}

async function readJsonResponse(response) {
  const contentType = response.headers.get("content-type") || "";
  if (contentType.includes("application/json")) {
    return response.json();
  }
  return { detail: await response.text() };
}

async function refreshHistory() {
  try {
    const response = await fetch("/history");
    const payload = await readJsonResponse(response);
    if (!response.ok) {
      throw new Error(payload.detail || "Could not load history.");
    }

    renderHistory(payload.items || []);
  } catch (error) {
    historyCount.textContent = "0";
    historyList.innerHTML = '<article class="history-empty">History could not be loaded.</article>';
    setStatus(historyStatus, "Could not load history right now.", "error");
  }
}

async function refreshHealth() {
  try {
    const response = await fetch("/health");
    const payload = await readJsonResponse(response);
    if (!response.ok) {
      throw new Error(payload.detail || "Could not load index stats.");
    }

    const documents = payload.index.documents || [];
    documentsCount.textContent = String(documents.length);
    chunksCount.textContent = String(payload.index.chunks || 0);
    historyCount.textContent = String(payload.database.questions || 0);
    askButton.disabled = documents.length === 0;
    if (documents.length > 0) {
      setStatus(questionStatus, "Your index is ready for questions.", "success");
    }
  } catch (error) {
    setStatus(questionStatus, "Could not load index status yet.", "error");
  }
}

uploadButton.dataset.defaultLabel = uploadButton.textContent;
askButton.dataset.defaultLabel = askButton.textContent;
askButton.disabled = true;
refreshHealth();
refreshHistory();

fileInput.addEventListener("change", () => {
  const file = fileInput.files[0];
  selectedFile.textContent = file ? file.name : "No file selected";
});

uploadForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const file = fileInput.files[0];
  if (!file) {
    setStatus(uploadStatus, "Choose a file before uploading.", "error");
    return;
  }

  setBusy(uploadButton, "Uploading...", true);
  setStatus(uploadStatus, `Uploading ${file.name} and building the index...`, "neutral");
  const formData = new FormData();
  formData.append("file", file);

  try {
    const response = await fetch("/upload", {
      method: "POST",
      body: formData,
    });
    const payload = await readJsonResponse(response);
    if (!response.ok) {
      throw new Error(payload.detail || "Upload failed.");
    }

    if (payload.duplicate) {
      setStatus(uploadStatus, payload.message || `${payload.filename} was already indexed.`, "success");
    } else {
      setStatus(uploadStatus, `Indexed ${payload.filename} with ${payload.chunks_added} chunks.`, "success");
    }
    setStatus(questionStatus, "Document indexed. You can ask questions now.", "success");
    fileInput.value = "";
    selectedFile.textContent = "No file selected";
    await refreshHealth();
  } catch (error) {
    setStatus(uploadStatus, error.message, "error");
  } finally {
    setBusy(uploadButton, "Uploading...", false);
  }
});

askForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const question = questionInput.value.trim();
  if (!question) {
    setStatus(questionStatus, "Enter a question before submitting.", "error");
    return;
  }

  setBusy(askButton, "Thinking...", true);
  setStatus(questionStatus, "Searching your indexed documents...", "neutral");
  setStatus(answerMeta, "Searching and generating an answer...", "neutral");
  answerBox.textContent = "Working on it...";
  answerBox.classList.remove("muted");
  renderSources([]);

  try {
    const response = await fetch("/ask", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question }),
    });
    const payload = await readJsonResponse(response);
    if (!response.ok) {
      throw new Error(payload.detail || "Question request failed.");
    }

    setStatus(
      answerMeta,
      payload.used_gemini
        ? "Gemini generated an answer from indexed content."
        : "Returned a retrieval-based answer from indexed content.",
      "success"
    );
    setStatus(questionStatus, "Ready for another question.", "success");
    answerBox.textContent = payload.answer;
    renderSources(payload.sources);
    await refreshHealth();
    await refreshHistory();
  } catch (error) {
    setStatus(answerMeta, "Request failed.", "error");
    setStatus(questionStatus, "The question could not be completed.", "error");
    answerBox.textContent = error.message;
    renderSources([]);
  } finally {
    setBusy(askButton, "Thinking...", false);
  }
});
