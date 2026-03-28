# DOCUEXTRACT

A document-based Question Answering web app built with a Retrieval-Augmented Generation (RAG) pipeline.

Users can upload documents, index their contents, and ask questions grounded in the uploaded material. The app retrieves relevant chunks from the document store and uses Gemini to generate answers with source citations.

## Features

- Upload `.pdf`, `.docx`, and `.txt` files
- Extract text from uploaded documents
- Chunk text for retrieval
- Generate embeddings for semantic search
- Store and search vectors with FAISS
- Ask natural language questions against uploaded content
- Return answers with citations
- Fall back to retrieval-only answers if Gemini is unavailable

## Tech Stack

### Backend

- Python
- FastAPI
- Google Gemini API via `google-genai`
- FAISS
- Sentence Transformers

### Frontend

- HTML
- CSS
- JavaScript

## Project Structure

```text
DOCUEXTRACT/
|-- backend/
|   |-- app.py
|   |-- chunking.py
|   |-- config.py
|   |-- document_loader.py
|   |-- embeddings.py
|   |-- rag_pipeline.py
|   `-- vector_store.py
|-- frontend/
|   |-- app.js
|   |-- index.html
|   `-- styles.css
|-- uploads/
|-- database/
|-- requirements.txt
|-- .env.example
`-- README.md
```

## How It Works

1. A user uploads a document.
2. The backend extracts text from the file.
3. The text is split into chunks.
4. Chunks are converted into embeddings.
5. Embeddings and metadata are stored in the vector index.
6. The user asks a question.
7. The app retrieves the most relevant chunks.
8. Gemini generates an answer using the retrieved context.
9. The UI displays the answer and source citations.

## Supported File Types

- PDF
- DOCX
- TXT

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

### 4. Create the environment file

Copy `.env.example` to `.env`:

```powershell
Copy-Item .env.example .env
```

Then set your Gemini API key inside `.env`:

```env
GEMINI_API_KEY=your_actual_api_key
GEMINI_MODEL=gemini-2.5-flash
EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2
CHUNK_SIZE=500
CHUNK_OVERLAP=50
RETRIEVAL_K=4
MAX_FILE_SIZE_MB=20
```

### 5. Run the app

```powershell
.\.venv\Scripts\python.exe -m uvicorn backend.app:app --reload
```

Open the app at:

[http://127.0.0.1:8000](http://127.0.0.1:8000)

## API Endpoints

### `GET /health`

Returns service health and current index stats.

### `POST /upload`

Uploads and indexes a supported document.

Request:

- `file`: uploaded `.pdf`, `.docx`, or `.txt`

Example response:

```json
{
  "filename": "sample.pdf",
  "stored_as": "uuid_sample.pdf",
  "chunks_added": 6,
  "stats": {
    "chunks": 6,
    "documents": ["sample.pdf"]
  }
}
```

### `POST /ask`

Asks a question against the indexed documents.

Request:

```json
{
  "question": "What is this document about?"
}
```

Example response:

```json
{
  "answer": "This document discusses ...",
  "sources": [
    "sample.pdf - Page 2",
    "sample.pdf - Page 4"
  ]
}
```

## Current Behavior

- If Gemini is configured correctly, the app returns generated answers grounded in retrieved context.
- If Gemini is unavailable or the API key is missing, the app falls back to retrieval-only answers.
- Source labels display the original uploaded filename instead of the internal stored filename.

## Notes

- `uploads/` stores uploaded files locally.
- `database/` stores vector data and metadata locally.
- The first run can take longer because the embedding model may need to initialize.
- Some transformer model warnings during startup can be harmless as long as the app finishes startup successfully.

## Future Improvements

- Chat history
- Multi-document session management
- Better duplicate-file handling
- Scanned PDF OCR support
- Deployment configuration
- UI polish and loading states

## License

This project is currently intended for educational and internship project use.
