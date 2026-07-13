import time
import re
from flask import Blueprint, request, jsonify

from app.services.retrieval import RetrievalService
from app.services.gemini import GeminiService
from app.models.database import Conversation, db

ask_bp = Blueprint("ask", __name__)

retrieval_service = RetrievalService()
gemini_service = GeminiService()


@ask_bp.route("/api/ask", methods=["POST"])
def ask():
    start_time = time.time()

    try:
        data = request.get_json()

        question = data.get("question", "").strip()
        course_id = data.get("course_id", "ALL")
        lesson_id = data.get("lesson_id", "ALL")
        lesson_type = data.get("lesson_type", "ALL")
        user_id = data.get("user_id", "guest")

        if not question:
            return jsonify({
                "error": "question is required"
            }), 400

        print("\n========== REQUEST ==========")
        print(f"Question: {question}")
        print(f"Course: {course_id}")
        print(f"Lesson: {lesson_id}")
        print(f"User: {user_id}")
        print("=============================")

        #################################################
        # Get FULL Conversation History (all previous chats)
        #################################################
        history = retrieval_service.get_history(user_id, limit=20)
        
        # Build conversation history in chronological order
        history_text = ""
        history_list = []
        
        for h in reversed(history):  # Oldest to newest
            history_text += f"User: {h.question}\n"
            history_text += f"Assistant: {h.answer}\n"
            history_list.append({
                "question": h.question,
                "answer": h.answer
            })

        print("\n===== CONVERSATION HISTORY =====")
        print(history_text if history_text else "(No history)")
        print("================================")

        #################################################
        # Rewrite Follow-up Question
        #################################################
        rewritten_question = gemini_service.rewrite_question(
            question,
            history_text
        )

        print(f"Original: {question}")
        print(f"Rewritten: {rewritten_question}")

        #################################################
        # Search for relevant chunks
        #################################################
        chunks = retrieval_service.search(
            rewritten_question,
            course_id,
            lesson_id,
            lesson_type
        )

        #################################################
        # Build Context & References
        #################################################
        context = []
        references = []
        sources = []

        if chunks:
            for chunk in chunks:
                context.append({
                    "content": chunk.content,
                    "lesson_title": chunk.lesson_title,
                    "source_type": chunk.source_type
                })

                references.append({
                    "lesson": chunk.lesson_title,
                    "type": chunk.source_type,
                    "course_id": getattr(chunk, 'course_id', course_id),
                    "lesson_id": getattr(chunk, 'lesson_id', lesson_id)
                })

                sources.append({
                    "title": chunk.lesson_title,
                    "type": chunk.source_type,
                    "course_id": getattr(chunk, 'course_id', course_id),
                    "lesson_id": getattr(chunk, 'lesson_id', lesson_id),
                    "similarity": round(getattr(chunk, 'similarity', 0.0), 4)
                })

        #################################################
        # Generate Answer with FULL context
        #################################################
        answer = gemini_service.generate_answer(
            question,  # Original question
            rewritten_question,
            context,
            history_text,
            history_list  # Pass full history list
        )

        #################################################
        # Clean Formatting
        #################################################
        answer = clean_answer(answer)

        #################################################
        # Save Conversation
        #################################################
        conversation = Conversation(
            user_id=user_id,
            course_id=course_id,
            lesson_id=lesson_id,
            question=question,
            answer=answer
        )
        db.session.add(conversation)
        db.session.commit()

        #################################################
        # Response
        #################################################
        return jsonify({
            "answer": answer,
            "references": references[:5] if references else [],
            "sources": sources[:5] if sources else [],
            "rewritten_question": rewritten_question,
            "conversation_history_used": len(history),
            "has_context": bool(chunks),
            "response_time": round(time.time() - start_time, 2)
        })

    except Exception as e:
        db.session.rollback()
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            "error": str(e)
        }), 500


def clean_answer(answer):
    """Clean the answer from formatting and source references"""
    if not answer:
        return "I couldn't generate a response. Please try again."
    
    # Remove markdown formatting
    answer = re.sub(r"\*\*(.*?)\*\*", r"\1", answer)
    answer = re.sub(r"\*(.*?)\*", r"\1", answer)
    answer = re.sub(r"#+", "", answer)
    
    # Remove bullet points and numbering
    answer = re.sub(r"^\s*[-•*]\s*", "", answer, flags=re.MULTILINE)
    answer = re.sub(r"^\s*\d+\.\s*", "", answer, flags=re.MULTILINE)
    
    # Remove source references
    answer = re.sub(r"^Source:.*$", "", answer, flags=re.MULTILINE)
    answer = re.sub(r"\[Source:.*?\]", "", answer)
    
    # Clean whitespace
    answer = answer.replace("\n", " ")
    answer = re.sub(r"\s+", " ", answer).strip()
    
    return answer