# DOCUEXTRACT

An Agentic Retrieval-Augmented Generation system built with FastAPI, LangGraph, and multi-agent orchestration.

The project upgrades a traditional RAG application into an agentic workflow where multiple agents collaborate to analyze the user query, retrieve relevant evidence, summarize findings, and generate a grounded final answer with citations.

## Features

- Upload `.pdf`, `.docx`, and `.txt` files
- Build a local vector index using FAISS
- Run a LangGraph-powered multi-agent workflow
- Reasoning agent for query analysis and response planning
- Retrieval agent for chunk search and ranking
- Summarization agent for evidence condensation
- Response agent for final grounded answer generation
- Citation-based responses
- SQLite-backed document metadata and Q&A history
- Duplicate document detection using file hashing
- Graceful fallback workflow when no Gemini key is configured

## Tech Stack

### Backend

- Python
- FastAPI
- LangGraph
- LangChain
- Gemini API via `langchain-google-genai`
- FAISS
- Sentence Transformers
- SQLite

### Frontend

- HTML
- CSS
- JavaScript

## Agent Architecture

The LangGraph workflow coordinates four collaborating agents:

1. Retrieval Agent
   Queries the vector store and gathers the most relevant document chunks.
2. Reasoning Agent
   Analyzes the question and decides the retrieval and response strategy.
3. Summarization Agent
   Condenses the retrieved evidence into a focused summary.
4. Response Agent
   Generates the final answer with grounded citations.

## Workflow

1. User submits a question.
2. Reasoning agent analyzes intent and retrieval strategy.
3. Retrieval agent fetches relevant chunks from the vector store.
4. Summarization agent compresses the evidence.
5. Response agent produces the final answer.
6. The system returns the answer, citations, summary, and workflow trace.

## Project Structure

```text
DOCUEXTRACT/
|-- backend/
|   |-- agents/
|   |   |-- reasoning_agent.py
|   |   |-- response_agent.py
|   |   |-- retrieval_agent.py
|   |   `-- summarizer_agent.py
|   |-- api/
|   |   `-- routes.py
|   |-- core/
|   |   |-- agentic_workflow.py
|   |   |-- llm_factory.py
|   |   `-- models.py
|   |-- app.py
|   |-- config.py
|   |-- database.py
|   |-- document_loader.py
|   |-- embeddings.py
|   |-- rag_pipeline.py
|   `-- vector_store.py
|-- frontend/
|-- uploads/
|-- database/
|-- requirements.txt
|-- .env.example
`-- README.md
```

## Setup

### 1. Clone the repository

```bash
git clone https://github.com/am886701/DOCUEXTRACT.git
cd DOCUEXTRACT
```

### 2. Create a virtual environment

Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure environment variables

Copy `.env.example` to `.env`:

```powershell
Copy-Item .env.example .env
```

Then set your Gemini API key:

```env
GOOGLE_API_KEY=your_actual_api_key
GEMINI_MODEL=gemini-2.5-flash
EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2
CHUNK_SIZE=500
CHUNK_OVERLAP=50
RETRIEVAL_K=4
MAX_FILE_SIZE_MB=20
```

## Run

```powershell
.\.venv\Scripts\python.exe -m uvicorn backend.app:app --reload
```

Open the app at:

[http://127.0.0.1:8000](http://127.0.0.1:8000)

## API Endpoints

### `GET /health`

Returns vector store stats, database stats, and agentic workflow metadata.

### `GET /history`

Returns recent stored questions and answers from SQLite.

### `POST /upload`

Uploads and indexes a supported document.

### `POST /ask`

Runs the LangGraph agentic workflow and returns:

- final answer
- citations
- reasoning plan
- summary
- workflow steps
- provider information

## Notes

- If `GOOGLE_API_KEY` is missing, the system still works with heuristic/fallback behavior.
- SQLite stores document metadata and question history in `database/app.db`.
- FAISS remains the retrieval engine for vector search.
- Scanned PDFs without extractable text are rejected with a clearer OCR-style message.

## Resume Value

This project demonstrates:

- agentic AI architecture
- LangGraph orchestration
- multi-agent reasoning pipelines
- retrieval-augmented generation
- production-oriented API and data modeling
- AI system design for GenAI engineering roles
