# RAG-Retrieval-Augmented-Generation

An AI-powered educational assistant that uses Retrieval-Augmented Generation (RAG) to answer questions based only on uploaded learning materials such as PDF lessons, text documents, and lecture transcripts.

The system retrieves the most relevant lesson content using vector search before generating an answer with Groq's high-performance models, allowing students to ask follow-up questions naturally while keeping responses grounded in the uploaded lessons.

---

## Features

- Conversational RAG
- PDF Lesson Ingestion
- Text Lesson Ingestion
- Video Transcript Ingestion
- Automatic Text Chunking
- Vector Embeddings using SentenceTransformers
- PostgreSQL + pgvector
- **Groq API Integration** (llama-3.1-8b-instant)
- Conversation History
- Follow-up Question Understanding
- Semantic Search
- Clickable Source References
- Similarity Threshold Filtering
- REST API
- Flask Backend
- HTML, CSS and JavaScript Frontend

---

## Tech Stack

| Component | Technology |
|------------|------------|
| Backend | Flask |
| Database | PostgreSQL |
| Vector Database | pgvector |
| ORM | SQLAlchemy |
| Embeddings | SentenceTransformers (all-mpnet-base-v2) |
| **Large Language Model** | **Groq API (llama-3.1-8b-instant)** |
| Frontend | HTML, CSS, JavaScript |

---

## Project Structure
