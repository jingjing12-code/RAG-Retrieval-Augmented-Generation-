from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects.postgresql import JSON

db = SQLAlchemy()

class Lesson(db.Model):
    __tablename__ = 'lessons'
    
    id = db.Column(db.Integer, primary_key=True)
    course_id = db.Column(db.String(50), nullable=False)
    lesson_id = db.Column(db.String(50), nullable=False)
    title = db.Column(db.String(255))
    lesson_type = db.Column(db.String(20))
    content = db.Column(db.Text)
    file_name = db.Column(db.String(255))
    chunk_count = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class LessonChunk(db.Model):
    __tablename__ = 'lesson_chunks'
    
    id = db.Column(db.Integer, primary_key=True)
    lesson_id = db.Column(db.Integer, db.ForeignKey('lessons.id', ondelete='CASCADE'))
    chunk_index = db.Column(db.Integer)
    content = db.Column(db.Text)
    embedding = db.Column(Vector(768))
    chunk_metadata = db.Column(JSON)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Conversation(db.Model):
    __tablename__ = 'conversations'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.String(50))
    course_id = db.Column(db.String(50))
    lesson_id = db.Column(db.String(50))
    question = db.Column(db.Text)
    answer = db.Column(db.Text)
    source_references = db.Column(JSON)
    confidence = db.Column(db.Float)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)