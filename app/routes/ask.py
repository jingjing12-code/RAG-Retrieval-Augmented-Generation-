import time
import re
from flask import Blueprint, request, jsonify

from app.services.retrieval import RetrievalService
from app.services.groq_service import GroqService
from app.models.database import Conversation, db

ask_bp = Blueprint("ask", __name__)

retrieval_service = RetrievalService()
groq_service = GroqService()  # ← FIXED: Use GroqService instead of gemini_service


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
        # Rewrite Follow-up Question using Groq
        #################################################
        rewritten_question = groq_service.rephrase_question(  # ← FIXED: Use groq_service
            question,
            history_list
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
            total_sim = 0.0
            seen_lessons = set()  # ← ADDED: To avoid duplicates
            
            for chunk in chunks:
                # Get section from chunk_index
                chunk_index = getattr(chunk, 'section', 0)
                section_name = f"Section {chunk_index + 1}" if chunk_index is not None else "General"
                
                lesson_key = f"{chunk.lesson_title}_{chunk.source_type}"
                
                if lesson_key in seen_lessons:
                    continue
                seen_lessons.add(lesson_key)
                
                context.append({
                    "content": chunk.content,
                    "lesson_title": chunk.lesson_title,
                    "source_type": chunk.source_type,
                    "section": section_name
                })

                # Build URL based on source type
                file_name = getattr(chunk, 'file_name', None)
                source_url = getattr(chunk, 'source_url', None)
                ref_url = None
                if chunk.source_type == 'pdf' and file_name:
                    ref_url = f"/upload/{file_name}"
                elif chunk.source_type == 'video' and source_url:
                    ref_url = source_url

                references.append({
                    "lesson": chunk.lesson_title,
                    "source": chunk.source_type,
                    "section": section_name,
                    "url": ref_url,
                    "course_id": getattr(chunk, 'course_id', course_id),
                    "lesson_id": getattr(chunk, 'lesson_id', lesson_id)
                })

                sources.append({
                    "title": chunk.lesson_title,
                    "type": chunk.source_type,
                    "section": section_name,
                    "course_id": getattr(chunk, 'course_id', course_id),
                    "lesson_id": getattr(chunk, 'lesson_id', lesson_id),
                    "similarity": round(getattr(chunk, 'similarity', 0.0), 4)
                })
                total_sim += getattr(chunk, 'similarity', 0.0)
            
            avg_sim = total_sim / len(chunks) if chunks else 0.0
            
            # ← FIXED: If similarity is too low, clear context
            if avg_sim < 0.35:
                context = []
                references = []
                sources = []

        #################################################
        # Generate Answer with FULL context using Groq
        #################################################
        if context:
            answer = groq_service.generate_answer(  # ← FIXED: Use groq_service
                rewritten_question,
                context,
                history_list
            )
        else:
            answer = "The lesson does not contain enough information to answer this question."

        #################################################
        # Clean Formatting
        #################################################
        answer = clean_answer(answer)
        
        if "does not contain enough information" in answer.lower():
            answer = "The lesson does not contain enough information to answer this question."

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
            "has_context": bool(context),
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
        return "The lesson does not contain enough information to answer this question."
    
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
    
    # Remove introductory phrases
    intro_phrases = [
        r'^Based on the lesson,?\s*',
        r'^Based on my understanding,?\s*',
        r'^Let me explain,?\s*',
        r'^I think,?\s*',
        r'^From the lesson,?\s*',
    ]
    for phrase in intro_phrases:
        answer = re.sub(phrase, '', answer, flags=re.IGNORECASE)
    
    # Clean whitespace
    answer = answer.replace("\n", " ")
    answer = re.sub(r"\s+", " ", answer).strip()
    
    # Check if answer contains the refusal message
    if "does not contain enough information" in answer.lower():
        return "The lesson does not contain enough information to answer this question."
    
    return answer