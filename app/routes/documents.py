from flask import Blueprint, request, jsonify
from app.models.database import Lesson, db

documents_bp = Blueprint('documents', __name__)

@documents_bp.route('/api/documents', methods=['GET'])
def list_documents():
    try:
        docs = Lesson.query.order_by(Lesson.created_at.desc()).all()
        return jsonify({
            'documents': [{
                'id': d.id,
                'file_name': d.file_name,
                'title': d.title,
                'course_id': d.course_id,
                'lesson_id': d.lesson_id,
                'chunk_count': d.chunk_count
            } for d in docs]
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500