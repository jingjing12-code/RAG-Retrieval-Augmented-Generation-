import os
from flask import Blueprint, request, jsonify
from app.models.database import Lesson, LessonChunk, db
from app.services.extractor import clean_html_text, extract_pdf_text
from app.services.transcript import parse_srt
from app.services.chunking import ChunkingService
from app.services.embedding import EmbeddingService
from config import UPLOAD_DIR

ingest_bp = Blueprint('ingest', __name__)

chunking_service = ChunkingService()
embedding_service = EmbeddingService()

@ingest_bp.route('/api/ingest/text', methods=['POST'])
def ingest_text():
    data = request.get_json()
    course_id = data.get('course_id', 'GENERAL')
    lesson_id = data.get('lesson_id', 'LESSON001')
    title = data.get('title', 'Untitled')
    content = data.get('content', '')
    
    clean_content = clean_html_text(content)
    
    lesson = Lesson(
        course_id=course_id,
        lesson_id=lesson_id,
        title=title,
        lesson_type='text',
        content=clean_content
    )
    db.session.add(lesson)
    db.session.flush()
    
    chunks = chunking_service.chunk_content(clean_content, lesson.id)
    for chunk_data in chunks:
        chunk = LessonChunk(
            lesson_id=chunk_data['lesson_id'],
            chunk_index=chunk_data['chunk_index'],
            content=chunk_data['content'],
            chunk_metadata=chunk_data['chunk_metadata']
        )
        db.session.add(chunk)
        db.session.flush()
        emb = embedding_service.get_embedding(chunk.content)
        if emb:
            chunk.embedding = emb
    
    lesson.chunk_count = len(chunks)
    db.session.commit()
    
    return jsonify({
        'message': f'Text lesson "{title}" ingested',
        'chunks_created': len(chunks)
    }), 201

@ingest_bp.route('/api/ingest/pdf', methods=['POST'])
def ingest_pdf():
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400
    
    file = request.files['file']
    course_id = request.form.get('course_id', 'GENERAL')
    lesson_id = request.form.get('lesson_id', 'LESSON001')
    title = request.form.get('title', file.filename)
    
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    filepath = os.path.join(UPLOAD_DIR, file.filename)
    file.save(filepath)
    
    text = extract_pdf_text(filepath)
    if not text.strip():
        return jsonify({'error': 'No text extracted'}), 400
    
    lesson = Lesson(
        course_id=course_id,
        lesson_id=lesson_id,
        title=title,
        lesson_type='pdf',
        content=text,
        file_name=file.filename
    )
    db.session.add(lesson)
    db.session.flush()
    
    chunks = chunking_service.chunk_content(text, lesson.id)
    for chunk_data in chunks:
        chunk = LessonChunk(
            lesson_id=chunk_data['lesson_id'],
            chunk_index=chunk_data['chunk_index'],
            content=chunk_data['content'],
            chunk_metadata=chunk_data['chunk_metadata']
        )
        db.session.add(chunk)
        db.session.flush()
        emb = embedding_service.get_embedding(chunk.content)
        if emb:
            chunk.embedding = emb
    
    lesson.chunk_count = len(chunks)
    db.session.commit()
    
    return jsonify({
        'message': f'PDF lesson "{title}" ingested',
        'chunks_created': len(chunks)
    }), 201

@ingest_bp.route('/api/ingest/transcript', methods=['POST'])
def ingest_transcript():
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400
    
    file = request.files['file']
    course_id = request.form.get('course_id', 'GENERAL')
    lesson_id = request.form.get('lesson_id', 'LESSON001')
    title = request.form.get('title', file.filename)
    
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    filepath = os.path.join(UPLOAD_DIR, file.filename)
    file.save(filepath)
    
    text = parse_srt(filepath)
    if not text.strip():
        return jsonify({'error': 'No text extracted'}), 400
    
    lesson = Lesson(
        course_id=course_id,
        lesson_id=lesson_id,
        title=title,
        lesson_type='video',
        content=text,
        file_name=file.filename
    )
    db.session.add(lesson)
    db.session.flush()
    
    chunks = chunking_service.chunk_content(text, lesson.id)
    for chunk_data in chunks:
        chunk = LessonChunk(
            lesson_id=chunk_data['lesson_id'],
            chunk_index=chunk_data['chunk_index'],
            content=chunk_data['content'],
            chunk_metadata=chunk_data['chunk_metadata']
        )
        db.session.add(chunk)
        db.session.flush()
        emb = embedding_service.get_embedding(chunk.content)
        if emb:
            chunk.embedding = emb
    
    lesson.chunk_count = len(chunks)
    db.session.commit()
    
    return jsonify({
        'message': f'Transcript lesson "{title}" ingested',
        'chunks_created': len(chunks)
    }), 201

@ingest_bp.route('/api/lesson/reindex/<lesson_id>', methods=['POST'])
def reindex_lesson(lesson_id):
    """Re-index a lesson by regenerating chunks and embeddings."""
    try:
        lesson = Lesson.query.filter_by(lesson_id=lesson_id).first()
        if not lesson:
            return jsonify({'error': 'Lesson not found'}), 404
        
        # Delete existing chunks
        LessonChunk.query.filter_by(lesson_id=lesson.id).delete()
        
        # Re-chunk
        chunks = chunking_service.chunk_content(lesson.content, lesson.id)
        
        # Generate new embeddings
        for chunk_data in chunks:
            chunk = LessonChunk(
                lesson_id=chunk_data['lesson_id'],
                chunk_index=chunk_data['chunk_index'],
                content=chunk_data['content'],
                chunk_metadata=chunk_data['chunk_metadata']
            )
            db.session.add(chunk)
            db.session.flush()
            
            emb = embedding_service.get_embedding(chunk.content)
            if emb:
                chunk.embedding = emb
        
        lesson.chunk_count = len(chunks)
        db.session.commit()
        
        return jsonify({
            'message': f'Lesson "{lesson_id}" re-indexed',
            'chunks_created': len(chunks)
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500
    