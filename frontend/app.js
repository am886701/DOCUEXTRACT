const uploadForm = document.getElementById("upload-form");
const askForm = document.getElementById("ask-form");
const fileInput = document.getElementById("file-input");
const selectedFile = document.getElementById("selected-file");
const questionInput = document.getElementById("question-input");
const uploadStatus = document.getElementById("upload-status");
const questionStatus = document.getElementById("question-status");
const answerBox = document.getElementById("answer-box");
const answerMeta = document.getElementById("answer-meta");
const reasoningBox = document.getElementById("reasoning-box");
const summaryBox = document.getElementById("summary-box");
const workflowList = document.getElementById("workflow-list");
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

function renderTextBox(element, value, emptyMessage) {
  element.textContent = value && value.trim() ? value : emptyMessage;
  element.classList.toggle("muted", !(value && value.trim()));
}

function renderSimpleList(element, items, emptyMessage) {
  element.innerHTML = "";
  element.classList.toggle("empty-list", items.length === 0);

  if (items.length === 0) {
    const item = document.createElement("li");
    item.textContent = emptyMessage;
    element.appendChild(item);
    return;
  }

  items.forEach((entry) => {
    const item = document.createElement("li");
    item.textContent = entry;
    element.appendChild(item);
  });
}

function renderSources(sources) {
  renderSimpleList(
    sourcesList,
    sources.map((source) => (typeof source === "string" ? source : `${source.document_name} - Page ${source.page}`)),
    "No sources yet."
  );
}

function renderWorkflow(steps) {
  renderSimpleList(workflowList, steps, "No workflow steps yet.");
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
      <span class="history-meta">${item.used_gemini ? "Gemini answer" : "Fallback answer"} • ${item.created_at}</span>
    `;
    entry.addEventListener("click", () => {
      questionInput.value = item.question;
      answerBox.textContent = item.answer;
      answerBox.classList.remove("muted");
      setStatus(answerMeta, `Showing saved answer from history #${item.id}.`, "success");
      setStatus(questionStatus, "Loaded a previous question into the workspace.", "success");
      renderTextBox(reasoningBox, "History entries from before the LangGraph upgrade may not have saved reasoning.", "The reasoning plan will appear here.");
      renderTextBox(summaryBox, "History entries from before the LangGraph upgrade may not have saved summaries.", "The evidence summary will appear here.");
      renderWorkflow(["Loaded a previous answer from stored history."]);
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
      setStatus(
        questionStatus,
        `Your index is ready. Active workflow: ${payload.agentic.framework} using ${payload.agentic.provider}.`,
        "success"
      );
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
renderWorkflow([]);
renderSources([]);
renderTextBox(reasoningBox, "", "The reasoning plan will appear here.");
renderTextBox(summaryBox, "", "The evidence summary will appear here.");

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
    setStatus(questionStatus, "Document indexed. The agentic workflow is ready for questions.", "success");
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

  setBusy(askButton, "Running agents...", true);
  setStatus(questionStatus, "Reasoning agent is planning the workflow...", "neutral");
  setStatus(answerMeta, "Running the LangGraph workflow...", "neutral");
  answerBox.textContent = "Working on it...";
  answerBox.classList.remove("muted");
  renderTextBox(reasoningBox, "", "The reasoning plan will appear here.");
  renderTextBox(summaryBox, "", "The evidence summary will appear here.");
  renderWorkflow(["Workflow started."]);
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
        ? `Gemini completed the agentic workflow using ${payload.provider}.`
        : `The workflow completed using ${payload.provider}.`,
      "success"
    );
    setStatus(questionStatus, "Ready for another question.", "success");
    answerBox.textContent = payload.answer;
    renderTextBox(reasoningBox, payload.reasoning || "", "The reasoning plan will appear here.");
    renderTextBox(summaryBox, payload.summary || "", "The evidence summary will appear here.");
    renderWorkflow(payload.workflow_steps || []);
    renderSources(payload.sources || []);
    await refreshHealth();
    await refreshHistory();
  } catch (error) {
    setStatus(answerMeta, "Request failed.", "error");
    setStatus(questionStatus, "The question could not be completed.", "error");
    answerBox.textContent = error.message;
    renderTextBox(reasoningBox, "", "The reasoning plan will appear here.");
    renderTextBox(summaryBox, "", "The evidence summary will appear here.");
    renderWorkflow([]);
    renderSources([]);
  } finally {
    setBusy(askButton, "Running agents...", false);
  }
});
