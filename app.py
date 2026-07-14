# app.py — SurodRAG (Groq + local sentence-transformers embeddings)

from flask import Flask, jsonify, send_from_directory, request
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import os
from dotenv import load_dotenv
from openai import OpenAI
from sentence_transformers import SentenceTransformer
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects.postgresql import JSON
import fitz
import re
import time
import traceback
import socket

# ====================================================================
# LOAD ENVIRONMENT VARIABLES
# ====================================================================
load_dotenv()

db_host     = os.getenv('DB_HOST', 'localhost')
db_port     = os.getenv('DB_PORT', '5432')
db_name     = os.getenv('DB_NAME', 'surod_rag')
db_user     = os.getenv('DB_USER', 'postgres')
db_password = os.getenv('DB_PASSWORD', '')
groq_key    = os.getenv('GROQ_API_KEY', '')
groq_model  = os.getenv('GROQ_MODEL', 'llama-3.1-8b-instant')  # ← FIXED: Use GROQ_MODEL

print("=" * 60)
print("Manlayag Starting...")
print(f"DB  : {db_name} @ {db_host}:{db_port}")
print(f"GROQ_KEY : {'SET' if groq_key else 'MISSING'}")
print(f"GROQ_MODEL: {groq_model}")  # ← FIXED: Show actual model
print("=" * 60)

# ====================================================================
# CONFIGURE GROQ
# ====================================================================
groq_client = None
if groq_key:
    try:
        groq_client = OpenAI(api_key=groq_key, base_url="https://api.groq.com/openai/v1")
        print(f" Groq configured OK with model: {groq_model}")
    except Exception as e:
        print(f" Groq client init FAILED: {e}")
else:
    print(" WARNING: No Groq API key in .env")

# ====================================================================
# FLASK APP
# ====================================================================
app = Flask(__name__, static_folder='static', static_url_path='')
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev-secret')
app.config['SQLALCHEMY_DATABASE_URI'] = (
    f"postgresql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"
)
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = 'upload'
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024

db = SQLAlchemy(app)
CORS(app)

LESSON_TYPES = ('text', 'pdf', 'video')

# ====================================================================
# DATABASE MODELS
# ====================================================================
class Lesson(db.Model):
    __tablename__ = 'lessons'
    id          = db.Column(db.Integer, primary_key=True)
    course_id   = db.Column(db.String(50), nullable=False)
    lesson_id   = db.Column(db.String(50), nullable=False)
    title       = db.Column(db.String(255))
    lesson_type = db.Column(db.String(20))
    content     = db.Column(db.Text)
    source_path = db.Column(db.String(500))
    source_url  = db.Column(db.String(500))
    file_name   = db.Column(db.String(255))
    file_size   = db.Column(db.Integer)
    chunk_count = db.Column(db.Integer, default=0)
    created_at  = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at  = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class LessonChunk(db.Model):
    __tablename__  = 'lesson_chunks'
    id             = db.Column(db.Integer, primary_key=True)
    lesson_id      = db.Column(db.Integer, db.ForeignKey('lessons.id', ondelete='CASCADE'))
    chunk_index    = db.Column(db.Integer)
    content        = db.Column(db.Text)
    embedding      = db.Column(Vector(768))
    chunk_metadata = db.Column(JSON)
    created_at     = db.Column(db.DateTime, default=datetime.utcnow)

class Conversation(db.Model):
    __tablename__      = 'conversations'
    id                 = db.Column(db.Integer, primary_key=True)
    user_id            = db.Column(db.String(50))
    course_id          = db.Column(db.String(50))
    lesson_id          = db.Column(db.String(50))
    question           = db.Column(db.Text)
    answer             = db.Column(db.Text)
    source_references  = db.Column(JSON)
    confidence         = db.Column(db.Float)
    created_at         = db.Column(db.DateTime, default=datetime.utcnow)

with app.app_context():
    try:
        db.create_all()
        try:
            db.session.execute(db.text(
                "ALTER TABLE lessons ADD COLUMN IF NOT EXISTS source_url VARCHAR(500)"
            ))
            db.session.commit()
        except Exception:
            db.session.rollback()
        print(" Database tables ready")
    except Exception as e:
        print(f" DB error: {e}")

# ====================================================================
# EMBEDDING SERVICE
# ====================================================================
_embed_model_singleton = None

def get_embed_model():
    global _embed_model_singleton
    if _embed_model_singleton is None:
        print(" Loading local embedding model (first time only, please wait)...")
        _embed_model_singleton = SentenceTransformer('sentence-transformers/all-mpnet-base-v2')
        print(" Embedding model loaded.")
    return _embed_model_singleton

class EmbeddingService:
    def __init__(self):
        self.model = get_embed_model()

    def get_embedding(self, text):
        try:
            if not text or len(text.strip()) == 0:
                return None
            if len(text) > 8000:
                text = text[:8000]
            embedding = self.model.encode(text)
            return embedding.tolist()
        except Exception as e:
            print(f"[ERROR] Embedding error: {e}")
            print(traceback.format_exc())
            return None

# ====================================================================
# PDF PARSER
# ====================================================================
class PDFParser:

    def extract_text(self, pdf_path):
        try:
            doc = fitz.open(pdf_path)
            text = ""

            for page in doc:
                text += page.get_text("text")

            doc.close()

            return text.strip()

        except Exception as e:
            print("PDF error:", e)
            return ""

    def _clean(self, text):
        if not text:
            return ""

        import re

        text = text.replace("\x00", "")
        text = re.sub(r'\r', '\n', text)
        text = re.sub(r'\n+', '\n', text)
        text = re.sub(r'[ \t]+', ' ', text)

        return text.strip()

# ====================================================================
# TRANSCRIPT PARSER
# ====================================================================
class TranscriptParser:
    _TS  = re.compile(r'\d{2}:\d{2}:\d{2}[,.]\d{3}\s*-->\s*\d{2}:\d{2}:\d{2}[,.]\d{3}')
    _NUM = re.compile(r'^\d+$')

    def clean(self, raw, sentences_per_para=5):
        lines = []
        for line in raw.splitlines():
            l = line.strip()
            if not l:
                continue
            if l.upper().startswith('WEBVTT') or l.upper().startswith('NOTE'):
                continue
            if self._TS.search(l):
                continue
            if self._NUM.match(l):
                continue
            l = re.sub(r'<[^>]+>', '', l).strip()
            if l:
                lines.append(l)

        text = re.sub(r'\s+', ' ', ' '.join(lines)).strip()
        if not text:
            return ''

        sentences = re.split(r'(?<=[.!?])\s+', text)
        paras, buf = [], []
        for i, s in enumerate(sentences, 1):
            buf.append(s)
            if i % sentences_per_para == 0:
                paras.append(' '.join(buf))
                buf = []
        if buf:
            paras.append(' '.join(buf))
        return '\n\n'.join(paras)

# ====================================================================
# CHUNKING SERVICE
# ====================================================================
class ChunkingService:
    def chunk_content(self, content, lesson_db_id, chunk_size=600, overlap=100):
        chunks = []
        paragraphs = content.split('\n\n')
        current = ""
        idx = 0

        for para in paragraphs:
            if not para.strip():
                continue
            if len(current) + len(para) > chunk_size and current:
                chunks.append({
                    'lesson_id': lesson_db_id,
                    'chunk_index': idx,
                    'content': current.strip(),
                    'chunk_metadata': {'chunk_size': len(current)}
                })
                idx += 1
                current = current[-overlap:] + "\n\n" + para
            else:
                current = (current + "\n\n" + para).strip() if current else para

        if current:
            chunks.append({
                'lesson_id': lesson_db_id,
                'chunk_index': idx,
                'content': current.strip(),
                'chunk_metadata': {'chunk_size': len(current)}
            })

        print(f" Created {len(chunks)} chunks")
        return chunks

# ====================================================================
# RETRIEVAL SERVICE
# ====================================================================
class RetrievalService:
    def __init__(self):
        self.embedding_service = EmbeddingService()
        self.top_k = 5

    def search(self, query, course_id=None, lesson_id=None, lesson_type=None, top_k=None):
        if top_k is None:
            top_k = self.top_k

        query_embedding = self.embedding_service.get_embedding(query)
        if not query_embedding:
            print(" No query embedding generated")
            return []

        sql = """
            SELECT lc.content, lc.chunk_metadata,
                   l.title AS lesson_title, 
                   l.lesson_type AS source_type,
                   l.course_id AS course_id,
                   l.lesson_id AS lesson_id,
                   l.file_name AS file_name,
                   l.source_url AS source_url,
                   lc.chunk_index AS section,
                   1 - (lc.embedding <=> CAST(:emb AS vector)) AS similarity
            FROM lesson_chunks lc
            JOIN lessons l ON lc.lesson_id = l.id
            WHERE lc.embedding IS NOT NULL
        """
        params = {"emb": str(query_embedding)}

        if course_id and course_id != 'ALL':
            sql += " AND l.course_id = :course_id"
            params["course_id"] = course_id
        if lesson_id and lesson_id != 'ALL':
            sql += " AND l.lesson_id = :lesson_id"
            params["lesson_id"] = lesson_id
        if lesson_type and lesson_type != 'ALL':
            sql += " AND l.lesson_type = :lesson_type"
            params["lesson_type"] = lesson_type

        sql += " ORDER BY similarity DESC LIMIT :top_k"
        params["top_k"] = top_k

        try:
            rows = db.session.execute(db.text(sql), params).fetchall()
            print(f" Found {len(rows)} relevant chunks")
            return rows
        except Exception as e:
            print(f" Search error: {e}")
            return []

    def get_history(self, user_id, limit=20):
        history = (
            Conversation.query
            .filter_by(user_id=user_id)
            .order_by(Conversation.created_at.desc())
            .limit(limit)
            .all()
        )
        return history

    def get_stats(self):
        return {
            'documents': Lesson.query.count(),
            'chunks':    LessonChunk.query.count(),
            'vectors':   LessonChunk.query.filter(LessonChunk.embedding.isnot(None)).count()
        }

# ====================================================================
# GROQ SERVICE - FIXED
# ====================================================================
class GroqService:
    SYSTEM_PROMPT = """
You are Manlayag, an AI tutor for Caraga State University.

CRITICAL RULES:
1. Answer the question directly using the lesson content provided.
2. Start your answer with the main point or definition immediately.
3. Do NOT use introductory phrases like "Based on my understanding", "Let me explain", etc.
4. Use natural language with words like "because", "and", "for example".
5. Do NOT use Markdown, bold, italic, bullet points, or numbering.
6. Return ONLY the answer in plain text.
7. If the answer is not in the lesson context, reply exactly with:
   "The lesson does not contain enough information to answer this question."
"""

    def __init__(self):
        self.is_configured = bool(groq_client)
        self.model = groq_model  # ← FIXED: Use groq_model

    def _chat(self, messages):
        return groq_client.chat.completions.create(
            model=self.model,  # ← FIXED: Use groq_model
            messages=messages
        )

    def rephrase_question(self, question, history):
        if not self.is_configured or not history:
            return question

        hist_lines = []
        for m in history[-5:]:
            hist_lines.append(f"User: {m.get('question')}")
            hist_lines.append(f"Assistant: {m.get('answer')}")
        hist_str = "\n".join(hist_lines)

        prompt = f"""Given the following conversation history and a follow-up question, rephrase the follow-up question to be a standalone search query that contains all necessary context from the conversation. Do NOT answer the question, just return the rephrased query.

Conversation History:
{hist_str}

Follow-up Question: {question}

Rephrased Search Query (return ONLY the rephrased query in plain text):"""
        try:
            response = self._chat([
                {"role": "system", "content": "You are a helpful assistant that rephrases follow-up questions into standalone search queries. Return only the rephrased query, nothing else."},
                {"role": "user", "content": prompt}
            ])
            rephrased = response.choices[0].message.content.strip()
            rephrased = rephrased.strip('\'"').strip()
            if rephrased:
                print(f" Rephrased '{question}' -> '{rephrased}'")
                return rephrased
            return question
        except Exception as e:
            print(f" Failed to rephrase question: {e}")
            return question

    def generate_answer(self, question, context, history=None):
        if not self.is_configured:
            return "The lesson does not contain enough information to answer this question."

        # Build context string from lessons
        ctx_str = ""
        if context and len(context) > 0:
            ctx_str = "\n\n".join(c.get('content', '') for c in context)
        
        # Build history string
        hist_str = ""
        if history and len(history) > 0:
            hist_lines = []
            last_exchanges = history[-5:] if len(history) > 5 else history
            for m in last_exchanges:
                hist_lines.append(f"User: {m.get('question')}")
                hist_lines.append(f"Assistant: {m.get('answer')}")
            hist_str = "\n".join(hist_lines)

        # If no lesson context is available, return the exact message
        if not ctx_str or len(ctx_str.strip()) < 50:
            return "The lesson does not contain enough information to answer this question."

        # Build prompt
        if hist_str:
            prompt = (
                "Lesson Context:\n"
                f"{ctx_str}\n\n"
                "Conversation History:\n"
                f"{hist_str}\n\n"
                "Question:\n"
                f"{question}\n\n"
                "Give a direct answer to the question. Start with the main point immediately. "
                "Do not use any introductory phrases. "
                "If the answer is not in the context, reply exactly with: "
                '"The lesson does not contain enough information to answer this question."'
            )
        else:
            prompt = (
                "Lesson Context:\n"
                f"{ctx_str}\n\n"
                "Question:\n"
                f"{question}\n\n"
                "Give a direct answer to the question. Start with the main point immediately. "
                "Do not use any introductory phrases. "
                "If the answer is not in the context, reply exactly with: "
                '"The lesson does not contain enough information to answer this question."'
            )

        try:
            response = self._chat([
                {"role": "system", "content": self.SYSTEM_PROMPT},
                {"role": "user", "content": prompt}
            ])
            
            answer = response.choices[0].message.content
            answer = self._clean_answer(answer)
            
            if not answer or not answer.strip():
                return "The lesson does not contain enough information to answer this question."
            
            if "does not contain enough information" in answer.lower():
                return "The lesson does not contain enough information to answer this question."
            
            return answer.strip()
            
        except Exception as e:
            print(f"[ERROR] Groq answer failed: {type(e).__name__}: {e}")
            print(traceback.format_exc())
            return "The lesson does not contain enough information to answer this question."

    def _clean_answer(self, answer):
        import re
        
        answer = re.sub(r'\[Source:.*?\]', '', answer)
        answer = re.sub(r'^Source:.*$', '', answer, flags=re.MULTILINE)
        answer = re.sub(r'^Source\s*:.*$', '', answer, flags=re.MULTILINE)
        answer = re.sub(r'^[\s]*[-*•]\s*', '', answer, flags=re.MULTILINE)
        answer = re.sub(r'\n\s*\n', '\n\n', answer)
        answer = answer.strip()
        
        return answer

    def generate_topic(self, question):
        if not self.is_configured:
            return question[:60]
        try:
            response = self._chat([
                {"role": "user", "content": f"Give a 4-6 word topic label for: {question}\nLabel:"}
            ])
            return response.choices[0].message.content.strip()
        except Exception as e:
            print(f"Topic error: {e}")
            return question[:60]

# ====================================================================
# SHARED INGESTION PIPELINE
# ====================================================================
def _slugify(s):
    s = re.sub(r'[^a-zA-Z0-9\- ]', '', s or '').strip().lower()
    s = re.sub(r'\s+', '-', s)
    return s or f"untitled-{int(time.time())}"

def process_and_store(course_id, lesson_id, title, lesson_type, text,
                       file_name, file_size=None, source_path=None, source_url=None):
    if lesson_type not in LESSON_TYPES:
        return None, f"Invalid lesson_type: {lesson_type}"
    if not text or not text.strip():
        return None, 'No text content to index'

    t0 = time.time()
    file_size = file_size if file_size is not None else len(text.encode('utf-8'))

    existing = Lesson.query.filter_by(file_name=file_name).first()
    if existing:
        LessonChunk.query.filter_by(lesson_id=existing.id).delete()
        db.session.delete(existing)
        db.session.commit()
        print(f"Replaced existing: {file_name}")

    lesson = Lesson(
        course_id=course_id, lesson_id=lesson_id, title=title or file_name,
        lesson_type=lesson_type, content=text, source_path=source_path,
        source_url=source_url, file_name=file_name, file_size=file_size
    )
    db.session.add(lesson)
    db.session.flush()

    chunks = ChunkingService().chunk_content(text, lesson.id)
    emb_svc = EmbeddingService()
    emb_count = 0

    for i, cd in enumerate(chunks):
        chunk = LessonChunk(
            lesson_id=cd['lesson_id'], chunk_index=cd['chunk_index'],
            content=cd['content'], chunk_metadata=cd['chunk_metadata']
        )
        db.session.add(chunk)
        db.session.flush()

        emb = emb_svc.get_embedding(chunk.content)
        if emb:
            chunk.embedding = emb
            emb_count += 1
            print(f"  [{i+1}/{len(chunks)}] OK")
        else:
            print(f"  [{i+1}/{len(chunks)}] FAILED")

    lesson.chunk_count = len(chunks)
    db.session.commit()

    elapsed = round(time.time() - t0, 2)
    print(f"Done: {emb_count}/{len(chunks)} embedded in {elapsed}s")

    return {
        'document_id': lesson.id,
        'file_name': lesson.file_name,
        'title': lesson.title,
        'lesson_type': lesson_type,
        'file_size': file_size,
        'chunks_created': len(chunks),
        'embeddings_generated': emb_count,
        'processing_time': elapsed
    }, None

# ====================================================================
# ROUTES
# ====================================================================
@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def serve(path):
    full = os.path.join('static', path)
    if path and os.path.exists(full):
        return send_from_directory('static', path)
    return send_from_directory('static', 'index.html')

@app.route('/upload/<path:filename>')
def serve_upload(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

@app.route('/api/status', methods=['GET'])
def get_status():
    stats = RetrievalService().get_stats()
    return jsonify({
        'status': 'ok', 
        'system': 'Manlayag Assistant',
        'model': groq_model,
        **stats
    })

@app.route('/api/health', methods=['GET'])
def health_check():
    db_ok = False
    try:
        db.session.execute(db.text('SELECT 1'))
        db_ok = True
    except Exception:
        pass

    embed_ok, embed_err = False, None
    gen_ok, gen_err = False, None

    try:
        emb = EmbeddingService().get_embedding("health check")
        embed_ok = bool(emb)
    except Exception as e:
        embed_err = str(e)

    if groq_client is not None:
        try:
            r = groq_client.chat.completions.create(
                model=groq_model,
                messages=[{"role": "user", "content": "Say OK."}]
            )
            gen_ok = bool(r.choices[0].message.content)
        except Exception as e:
            gen_err = str(e)

    return jsonify({
        'status': 'healthy' if (db_ok and embed_ok and gen_ok) else 'degraded',
        'database': 'connected' if db_ok else 'disconnected',
        'groq_key': 'configured' if groq_key else 'not configured',
        'groq_model': groq_model,
        'embedding_model': {'name': 'all-mpnet-base-v2 (local)', 'working': embed_ok, 'error': embed_err},
        'generation_model': {'name': groq_model, 'working': gen_ok, 'error': gen_err}
    })

# ====================================================================
# /api/ask - MAIN ROUTE
# ====================================================================
@app.route('/api/ask', methods=['POST'])
def ask():
    t0 = time.time()
    try:
        data = request.get_json() or {}
        question = data.get('question', '').strip()
        course_id = data.get('course_id', 'ALL')
        lesson_id = data.get('lesson_id', 'ALL')
        lesson_type = data.get('lesson_type', 'ALL')
        user_id = data.get('user_id', 'anonymous')

        if not question:
            return jsonify({'error': 'question is required'}), 400

        print("\n" + "="*60)
        print(f" QUESTION: {question}")
        print(f" USER: {user_id}")
        print(f" MODEL: {groq_model}")
        print("="*60)

        retrieval = RetrievalService()
        ai_service = GroqService()

        # --- GET FULL CONVERSATION HISTORY ---
        history_objects = retrieval.get_history(user_id, limit=20)
        history = []
        
        if history_objects:
            for h in reversed(history_objects):
                history.append({
                    'question': h.question,
                    'answer': h.answer
                })
            print(f"\n Found {len(history)} history entries")
        else:
            print("\n No history found")

        # --- REPHRASE QUESTION FOR RETRIEVAL IF HISTORY EXISTS ---
        search_query = question
        if history and len(history) > 0:
            search_query = ai_service.rephrase_question(question, history)

        # --- SEARCH FOR RELEVANT CHUNKS ---
        chunks = retrieval.search(search_query, course_id, lesson_id, lesson_type)

        context = []
        references = []
        avg_sim = 0.0

        if chunks:
            total_sim = 0.0
            seen_lessons = set()
            
            for chunk in chunks:
                chunk_index = getattr(chunk, 'section', 0)
                section_name = f"Section {chunk_index + 1}" if chunk_index is not None else "General"
                
                lesson_key = f"{chunk.lesson_title}_{chunk.source_type}"
                
                if lesson_key in seen_lessons:
                    continue
                seen_lessons.add(lesson_key)
                
                context.append({
                    'content': chunk.content,
                    'lesson_title': chunk.lesson_title,
                    'source_type': chunk.source_type,
                    'section': section_name
                })
                
                # --- BUILD DETAILED REFERENCES ---
                file_name = getattr(chunk, 'file_name', None)
                source_url = getattr(chunk, 'source_url', None)
                course_id_val = getattr(chunk, 'course_id', course_id)
                lesson_id_val = getattr(chunk, 'lesson_id', lesson_id)
                
                # Build URL based on source type
                ref_url = None
                if chunk.source_type == 'pdf' and file_name:
                    ref_url = f"/upload/{file_name}"
                elif chunk.source_type == 'video' and source_url:
                    ref_url = source_url
                elif chunk.source_type == 'text' and lesson_id_val:
                    ref_url = f"/api/documents?lesson_id={lesson_id_val}"
                
                references.append({
                    "course_id": course_id_val,
                    "lesson_id": lesson_id_val,
                    "lesson": chunk.lesson_title,
                    "source_type": chunk.source_type,
                    "source": chunk.source_type,
                    "section": section_name,
                    "chunk_index": chunk_index,
                    "url": ref_url,
                    "file_name": file_name,
                    "similarity": round(getattr(chunk, 'similarity', 0.0), 4)
                })
                total_sim += getattr(chunk, 'similarity', 0.0)
            
            avg_sim = total_sim / len(chunks) if chunks else 0.0
            
            print(f"\n Using lesson context (similarity: {avg_sim:.4f})")
            answer = ai_service.generate_answer(question, context, history)
            
        else:
            print("\n No chunks found")
            answer = "The lesson does not contain enough information to answer this question."
            references = []

        # --- FINAL CLEANUP ---
        if "does not contain enough information" in answer.lower():
            answer = "The lesson does not contain enough information to answer this question."
            references = []

        # Clean the answer
        answer = clean_answer_text(answer)

        # Generate topic
        topic_label = ai_service.generate_topic(question)

        # --- SAVE CONVERSATION ---
        conv = Conversation(
            user_id=user_id,
            course_id=course_id,
            lesson_id=lesson_id,
            question=question,
            answer=answer,
            source_references=references[:3] if references else [],
            confidence=round(avg_sim, 4) if avg_sim > 0 else 0.0
        )
        db.session.add(conv)
        db.session.commit()

        # --- RESPONSE ---
        return jsonify({
            'answer': answer,
            'references': references[:5] if references else [],
            'confidence': round(avg_sim, 4) if avg_sim > 0 else 0.0,
            'topic': topic_label,
            'chunks_used': len(chunks) if chunks else 0,
            'has_context': bool(chunks),
            'has_history': bool(history),
            'history_used': len(history) if history else 0,
            'response_time': round(time.time() - t0, 2)
        })

    except Exception as e:
        db.session.rollback()
        print(traceback.format_exc())
        return jsonify({'error': str(e)}), 500


def clean_answer_text(answer):
    """Clean the answer text"""
    if not answer:
        return "The lesson does not contain enough information to answer this question."
    
    # Remove markdown
    answer = re.sub(r'\*\*(.*?)\*\*', r'\1', answer)
    answer = re.sub(r'\*(.*?)\*', r'\1', answer)
    answer = re.sub(r'#+', '', answer)
    
    # Remove bullets
    answer = re.sub(r'^\s*[-•*]\s*', '', answer, flags=re.MULTILINE)
    answer = re.sub(r'^\s*\d+\.\s*', '', answer, flags=re.MULTILINE)
    
    # Remove source references
    answer = re.sub(r'^Source:.*$', '', answer, flags=re.MULTILINE)
    answer = re.sub(r'\[Source:.*?\]', '', answer)
    
    # Clean whitespace
    answer = answer.replace('\n', ' ')
    answer = re.sub(r'\s+', ' ', answer).strip()
    
    # Check if answer contains the refusal message
    if "does not contain enough information" in answer.lower():
        return "The lesson does not contain enough information to answer this question."
    
    return answer


# ─── 1. TEXT-BASED LESSONS ────────────────────────────────
@app.route('/api/ingest/text', methods=['POST'])
def ingest_text():
    try:
        data      = request.get_json() or {}
        course_id = data.get('course_id', 'COURSE001')
        lesson_id = data.get('lesson_id', 'LESSON-TEXT')
        title     = data.get('title', '').strip() or 'Untitled Lesson'
        content   = data.get('content', '').strip()

        if not content:
            return jsonify({'error': 'content is required'}), 400

        file_name = f"{_slugify(title)}.txt"
        result, err = process_and_store(course_id, lesson_id, title, 'text', content, file_name=file_name)
        if err:
            return jsonify({'error': err}), 400
        return jsonify(result), 201
    except Exception as e:
        db.session.rollback()
        print(traceback.format_exc())
        return jsonify({'error': str(e)}), 500

# ─── 2. PDF DOCUMENTS ─────────────────────────────────────
@app.route('/api/ingest/pdf', methods=['POST'])
def ingest_pdf():
    try:
        file      = request.files.get('file')
        course_id = request.form.get('course_id', 'COURSE001')
        lesson_id = request.form.get('lesson_id', 'LESSON-PDF')

        if not file or not file.filename:
            return jsonify({'error': 'No file provided'}), 400
        if not file.filename.lower().endswith('.pdf'):
            return jsonify({'error': 'Only PDF files are supported'}), 400

        filename = file.filename
        title    = request.form.get('title', filename.replace('.pdf', ''))
        data     = file.read()
        size     = len(data)

        os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
        path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        with open(path, 'wb') as f:
            f.write(data)

        print(f"\n Ingesting PDF: {filename} ({size} bytes)")
        text = PDFParser().extract_text(path)
        if not text.strip():
            return jsonify({'error': 'No text extracted from PDF'}), 400
        print(f" Extracted {len(text)} characters")

        result, err = process_and_store(
            course_id, lesson_id, title, 'pdf', text,
            file_name=filename, file_size=size, source_path=path
        )
        if err:
            return jsonify({'error': err}), 400
        return jsonify(result), 201
    except Exception as e:
        db.session.rollback()
        print(traceback.format_exc())
        return jsonify({'error': str(e)}), 500

# ─── 3. VIDEO LESSON TRANSCRIPTIONS ───────────────────────
@app.route('/api/ingest/video', methods=['POST'])
def ingest_video():
    try:
        course_id = request.form.get('course_id', 'COURSE001')
        lesson_id = request.form.get('lesson_id', 'LESSON-VIDEO')
        title     = request.form.get('title', '').strip() or 'Untitled Video Lesson'
        video_url = request.form.get('video_url', '').strip() or None

        file   = request.files.get('file')
        pasted = request.form.get('video', '').strip()

        raw_text, file_name, file_size = '', None, None
        parser = TranscriptParser()

        if file and file.filename:
            file_name = file.filename
            ext = file_name.lower().rsplit('.', 1)[-1] if '.' in file_name else ''
            if ext not in ('srt', 'vtt', 'txt'):
                return jsonify({'error': 'Supported transcript formats: .srt, .vtt, .txt'}), 400
            raw_bytes = file.read()
            file_size = len(raw_bytes)
            decoded   = raw_bytes.decode('utf-8', errors='ignore')
            raw_text  = parser.clean(decoded) if ext in ('srt', 'vtt') else decoded.strip()
        elif pasted:
            raw_text  = pasted
            file_size = len(pasted.encode('utf-8'))
            file_name = f"{_slugify(title)}.txt"
        else:
            return jsonify({'error': 'Provide a transcript file or pasted transcript text'}), 400

        if not raw_text.strip():
            return jsonify({'error': 'No transcript text found after cleaning'}), 400

        result, err = process_and_store(
            course_id,
            lesson_id,
            title,
            'video',
            raw_text,
            file_name=file_name,
            file_size=file_size,
            source_url=video_url
        )
        if err:
            return jsonify({'error': err}), 400
        if video_url:
            result['video_url'] = video_url
        return jsonify(result), 201
    except Exception as e:
        db.session.rollback()
        print(traceback.format_exc())
        return jsonify({'error': str(e)}), 500

@app.route('/api/documents', methods=['GET'])
def list_documents():
    try:
        lesson_type = request.args.get('lesson_type')
        q = Lesson.query
        if lesson_type and lesson_type != 'ALL':
            q = q.filter_by(lesson_type=lesson_type)
        docs = q.order_by(Lesson.created_at.desc()).all()
        return jsonify({'documents': [{
            'id': d.id, 'file_name': d.file_name, 'title': d.title,
            'lesson_type': d.lesson_type, 'course_id': d.course_id,
            'lesson_id': d.lesson_id, 'source_url': d.source_url,
            'chunk_count': d.chunk_count, 'file_size': d.file_size,
            'created_at': d.created_at.isoformat()
        } for d in docs]})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/documents/<int:doc_id>', methods=['DELETE'])
def delete_document(doc_id):
    try:
        lesson = Lesson.query.get_or_404(doc_id)
        LessonChunk.query.filter_by(lesson_id=doc_id).delete()
        db.session.delete(lesson)
        db.session.commit()
        return jsonify({'message': f'Deleted document {doc_id}'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@app.errorhandler(404)
def not_found(e):
    return jsonify({'error': 'Not found'}), 404

@app.errorhandler(500)
def server_error(e):
    return jsonify({'error': 'Internal server error'}), 500

@app.errorhandler(413)
def too_large(e):
    return jsonify({'error': 'File too large. Max 50MB'}), 413

if __name__ == '__main__':
    hostname = socket.gethostname()
    local_ip = socket.gethostbyname(hostname)

    print("\n==============================================")
    print("Server is running!")
    print(f"Local:   http://localhost:8000")
    print(f"Network: http://{local_ip}:8000")
    print(f"Model:   {groq_model}")
    print("==============================================\n")

    from waitress import serve
    serve(app, host='0.0.0.0', port=8000)