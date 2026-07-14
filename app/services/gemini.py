import os
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()


class GeminiService:

    def __init__(self):
        self.api_key = os.getenv("GEMINI_API_KEY")
        self.is_configured = bool(self.api_key)

        if self.is_configured:
            genai.configure(api_key=self.api_key)
            self.model = genai.GenerativeModel("gemini-1.5-flash")
            print("✅ Gemini initialized")
        else:
            self.model = None
            print("❌ GEMINI_API_KEY not found")

    def rewrite_question(self, question, history_text=""):
        if not self.is_configured:
            return question

        if not history_text:
            return question

        prompt = f"""
You are a query rewriting assistant.

CONVERSATION HISTORY:
{history_text}

CURRENT QUESTION:
{question}

Rewrite the current question into a complete standalone question.

RULES:
- Use the conversation history to understand what the user is asking about.
- If the question contains words like "it", "that", "this", "explain further", "give example", use the history.
- If the question already stands alone, return it unchanged.
- Return ONLY the rewritten question.
"""

        try:
            response = self.model.generate_content(prompt)
            if response.text:
                return response.text.strip()
            return question
        except Exception as e:
            print("Rewrite Error:", e)
            return question

    def generate_answer(self, original_question, rewritten_question, context, history_text="", history_list=None):
        if not self.is_configured:
            return "Gemini API is not configured."

        # Build lesson context
        lesson_context = ""
        if context:
            lesson_context = "\n\n".join([
                f"""
Lesson: {item['lesson_title']}
Source: {item['source_type']}

{item['content']}
"""
                for item in context
            ])

        # Build conversation history for prompt
        conversation_context = ""
        if history_list and len(history_list) > 0:
            # Get last 3 exchanges for context
            last_exchanges = history_list[-3:] if len(history_list) > 3 else history_list
            conv_lines = []
            for ex in last_exchanges:
                conv_lines.append(f"User: {ex['question']}")
                conv_lines.append(f"Assistant: {ex['answer']}")
            conversation_context = "\n".join(conv_lines)

        # If no lesson context is available, immediately return refusal
        if not lesson_context:
            return "Ang tubag wala makita sa gi-upload nga PDF."

        # --- BUILD PROMPT WITH FULL CONTEXT ---
        if conversation_context:
            # Has both lesson AND conversation history
            prompt = f"""
You are Manlayag, an AI tutor for Caraga State University.

IMPORTANT RULES:
1. Answer the current question strictly using ONLY the lesson context provided below. Do NOT use general knowledge or external information.
2. If the answer cannot be found in the provided lesson context, you must reply exactly with: "Ang tubag wala makita sa gi-upload nga PDF." Do NOT make up, assume, or extrapolate any information.
3. Do NOT include "Source:" or lesson titles in your answer.
4. Do NOT use Markdown, bold, italic, bullet points, or numbering.
5. Respond in plain text as one or two paragraphs.

CONVERSATION HISTORY:
{conversation_context}

LESSON CONTEXT:
{lesson_context}

Current Question: {original_question}

Answer based ONLY on the lesson context. If the answer is not in the lesson context, reply exactly with: "Ang tubag wala makita sa gi-upload nga PDF."
"""
        else:
            # Has lesson context but no history
            prompt = f"""
You are Manlayag, an AI tutor for Caraga State University.

IMPORTANT RULES:
1. Answer the current question strictly using ONLY the lesson context provided below. Do NOT use general knowledge or external information.
2. If the answer cannot be found in the provided lesson context, you must reply exactly with: "Ang tubag wala makita sa gi-upload nga PDF." Do NOT make up, assume, or extrapolate any information.
3. Do NOT include "Source:" or lesson titles.
4. Do NOT use Markdown, bold, italic, bullet points, or numbering.
5. Respond as one or two paragraphs.

LESSON CONTEXT:
{lesson_context}

Question: {original_question}

Answer:
"""

        try:
            response = self.model.generate_content(prompt)
            if not response.text:
                return "Ang tubag wala makita sa gi-upload nga PDF."
            
            answer = response.text.strip()
            
            # If answer contains refusal triggers, return exact message
            if "does not contain enough information" in answer.lower() or "wala makita" in answer.lower():
                return "Ang tubag wala makita sa gi-upload nga PDF."
            
            return answer
            
        except Exception as e:
            print("Gemini Error:", e)
            return "Ang tubag wala makita sa gi-upload nga PDF."