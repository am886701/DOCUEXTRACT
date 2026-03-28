# RAG QA App Context

## Goal

Build a document-grounded question answering web app that:

- accepts PDF, DOCX, and TXT uploads
- extracts and chunks text
- generates embeddings
- stores vectors for retrieval
- answers questions with citations

## Current Implementation

- Backend: FastAPI
- Retrieval: FAISS when available, NumPy similarity fallback otherwise
- Embeddings: Sentence Transformers when available, hashing fallback otherwise
- Generation: Gemini API via `google-genai`, with retrieval-only fallback when no API key is configured
- Frontend: Static HTML/CSS/JavaScript served by FastAPI

## Run

Install dependencies:

```bash
pip install -r requirements.txt
```

Set environment variables from `.env.example`, then start the app:

```bash
uvicorn backend.app:app --reload
```

Open `http://127.0.0.1:8000`.
