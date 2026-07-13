# SurodRAG Assistant

SurodRAG is an AI-powered tutor designed for educational institutions. It utilizes Retrieval-Augmented Generation (RAG) to provide highly accurate, contextual answers based on your specific lesson documents and PDFs.

Currently powered by **DeepSeek API** for advanced conversational generation, and uses **SentenceTransformers** (HuggingFace) for fully local, free document embeddings.

## Features

- **Document Ingestion:** Easily upload PDFs which are automatically chunked and stored in a vector database.
- **DeepSeek Integration:** Generates intelligent, accurate responses using the highly capable DeepSeek model.
- **Local Embeddings:** Avoids costly embedding APIs by using a locally-run SentenceTransformers model (`all-mpnet-base-v2`).
- **PostgreSQL & pgvector:** Efficient, fast vector search and retrieval for high-accuracy context building.
- **Clean API:** Simple REST endpoints for UI integration.

## Prerequisites

- Python 3.10+
- PostgreSQL (with `pgvector` extension)
- DeepSeek API Key

## Local Setup Instructions

1. **Clone the repository:**
   ```bash
   git clone https://github.com/yourusername/surod-rag.git
   cd surod-rag
   ```

2. **Set up a Virtual Environment:**
   ```bash
   python -m venv venv
   source venv/bin/activate # On Windows use: venv\Scripts\activate
   ```

3. **Install Dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Environment Variables:**
   - Copy the `.env.example` file to `.env`:
     ```bash
     cp .env.example .env
     ```
   - Edit `.env` and add your database credentials and **DeepSeek API Key**.
   > **Note**: You can obtain a DeepSeek API key by signing up at [DeepSeek's API platform](https://platform.deepseek.com/).

5. **Run the Application:**
   ```bash
   python app.py
   ```
   The Flask server will start at `http://localhost:8000`. The first time you run the application or ingest a document, the local `sentence-transformers` model will be downloaded automatically (approx 400MB).

## API Endpoints

- `GET /api/status` - View system status and vector database statistics.
- `POST /api/ask` - Send a question to the AI tutor.
- `POST /api/ingest/pdf` - Upload a PDF document for processing and vectorization.
- `GET /api/documents` - List all ingested documents.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
