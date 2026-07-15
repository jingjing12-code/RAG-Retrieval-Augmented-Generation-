# RAG-Retrieval-Augmented-Generation

An AI-powered educational assistant that uses Retrieval-Augmented Generation (RAG) to answer questions based only on uploaded learning materials such as PDF lessons, text documents, and lecture transcripts.

The system retrieves the most relevant lesson content using vector search before generating answers with the Groq API (Llama 3.1), allowing students to ask follow-up questions naturally while ensuring that responses remain grounded in the uploaded lessons.

---

# Features

- Conversational RAG
- PDF Lesson Ingestion
- Text Lesson Ingestion
- Video Transcript Ingestion
- Automatic Text Chunking
- Semantic Search
- Vector Embeddings using SentenceTransformers
- PostgreSQL + pgvector
- Groq Llama 3.1 Integration
- Conversation History
- Follow-up Question Understanding
- Source References
- REST API
- Flask Backend
- HTML, CSS and JavaScript Frontend

---

# Tech Stack

| Component | Technology |
|------------|------------|
| Backend | Flask |
| Database | PostgreSQL |
| Vector Database | pgvector |
| ORM | SQLAlchemy |
| Embeddings | SentenceTransformers (all-mpnet-base-v2) |
| Large Language Model | Groq (Llama 3.1 8B Instant) |
| Frontend | HTML, CSS, JavaScript |

---

# Project Structure

```
app/
│
├── models/
│
├── routes/
│     ├── ask.py
│     ├── ingest.py
│     └── documents.py
│
├── services/
│     ├── embedding.py
│     ├── retrieval.py
│     ├── groq_service.py
│     ├── pdf_parser.py
│     └── transcript_parser.py
│
├── static/
├── templates/
│
app.py
config.py
requirements.txt
.env
```

---

# Installation

## Clone Repository

```bash
git clone https://github.com/jingjing12-code/RAG-Retrieval-Augmented-Generation-.git
```

```bash
cd RAG-Retrieval-Augmented-Generation-
```

---

## Create Virtual Environment

Windows

```bash
python -m venv venv
```

Activate

```bash
venv\Scripts\activate
```

---

## Install Dependencies

```bash
pip install -r requirements.txt
```

---

## Configure Environment Variables

Create a `.env` file.

Example

```env
# Database

DB_HOST=localhost
DB_PORT=5432
DB_NAME=surod_rag
DB_USER=postgres
DB_PASSWORD=your_password

# Groq

GROQ_API_KEY=YOUR_GROQ_API_KEY
GROQ_MODEL=llama-3.1-8b-instant

# Flask

SECRET_KEY=your-secret-key
```

---

## Run Application

```bash
python app.py
```

The application will start at

```
http://localhost:8000
```

---

# API Endpoints

## Ask Question

```
POST /api/ask
```

Example Request

```json
{
    "question": "Why is persuasive writing important?",
    "course_id": "ENG101",
    "lesson_id": "PERS001",
    "lesson_type": "ALL",
    "user_id": "student001"
}
```

---

## Upload PDF

```
POST /api/ingest/pdf
```

---

## Upload Text

```
POST /api/ingest/text
```

---

## Upload Transcript

```
POST /api/ingest/video
```

---

## List Documents

```
GET /api/documents
```

---

## System Status

```
GET /api/status
```

---

# Conversational RAG Workflow

1. The user submits a question.
2. Previous conversation history is retrieved.
3. Follow-up questions are rewritten into standalone questions.
4. SentenceTransformers converts the rewritten question into an embedding vector.
5. PostgreSQL with pgvector searches for the most relevant lesson chunks.
6. Retrieved lesson chunks are combined into a lesson context.
7. Groq (Llama 3.1) generates an answer using only the retrieved lesson context.
8. If the answer is not found in the uploaded lessons, the assistant responds:

```
"The lesson does not contain enough information to answer this question.".
```

9. The conversation is stored for future follow-up questions.

---

# Technologies Used

- Flask
- SQLAlchemy
- PostgreSQL
- pgvector
- SentenceTransformers
- Groq API
- Llama 3.1 8B Instant
- HTML
- CSS
- JavaScript

---

# Requirements

- Python 3.10+
- PostgreSQL
- pgvector Extension
- Groq API Key

---

# License

This project is licensed under the MIT License.

---

# Developed By

Capstone Project

**RAG-Retrieval-Augmented-Generation**

Caraga State University
