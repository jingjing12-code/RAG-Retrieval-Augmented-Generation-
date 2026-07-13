from app.models.database import Lesson, LessonChunk, Conversation, db
from app.services.embedding import EmbeddingService
from config import TOP_K


class RetrievalService:
    def __init__(self):
        self.embedding_service = EmbeddingService()
        self.top_k = TOP_K

    def search(self, query, course_id=None, lesson_id=None, lesson_type=None):
        query_embedding = self.embedding_service.get_embedding(query)
        if not query_embedding:
            return []

        sql = """
            SELECT lc.content, lc.chunk_metadata,
                   l.title AS lesson_title,
                   l.lesson_type AS source_type,
                   l.course_id AS course_id,
                   l.lesson_id AS lesson_id,
                   1 - (lc.embedding <=> CAST(:emb AS vector)) AS similarity
            FROM lesson_chunks lc
            JOIN lessons l ON lc.lesson_id = l.id
            WHERE lc.embedding IS NOT NULL
        """

        params = {"emb": str(query_embedding)}

        if course_id and course_id != "ALL":
            sql += " AND l.course_id = :course_id"
            params["course_id"] = course_id

        if lesson_id and lesson_id != "ALL":
            sql += " AND l.lesson_id = :lesson_id"
            params["lesson_id"] = lesson_id

        if lesson_type and lesson_type != "ALL":
            sql += " AND l.lesson_type = :lesson_type"
            params["lesson_type"] = lesson_type

        sql += """
            ORDER BY similarity DESC
            LIMIT :top_k
        """

        params["top_k"] = self.top_k

        try:
            rows = db.session.execute(
                db.text(sql),
                params
            ).fetchall()
            return rows
        except Exception as e:
            print(f"Search error: {e}")
            return []

    def get_history(self, user_id, limit=20):  # Increased to 20
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
            "documents": Lesson.query.count(),
            "chunks": LessonChunk.query.count(),
            "vectors": LessonChunk.query.filter(
                LessonChunk.embedding.isnot(None)
            ).count()
        }