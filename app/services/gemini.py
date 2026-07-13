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

        # --- BUILD PROMPT WITH FULL CONTEXT ---
        if lesson_context and conversation_context:
            # Has both lesson AND conversation history
            prompt = f"""
You are Manlayag, an AI tutor for Caraga State University.

IMPORTANT RULES:
1. Use BOTH the lesson context AND conversation history to answer.
2. If the answer is NOT in the lesson context, say: 
   "The lesson does not contain enough information to answer this question."
3. Do NOT include "Source:" or lesson titles in your answer.
4. Do NOT use Markdown, bold, italic, bullet points, or numbering.
5. Respond in plain text as one or two paragraphs.

CONVERSATION HISTORY:
{conversation_context}

LESSON CONTEXT:
{lesson_context}

Current Question: {original_question}

Answer based on the lesson context and conversation history. If this is a follow-up question, use the conversation history for context.
"""
        elif conversation_context and not lesson_context:
            # Has conversation history but no lesson context
            prompt = f"""
You are Manlayag, an AI tutor for Caraga State University.

CONVERSATION HISTORY:
{conversation_context}

Current Question: {original_question}

Answer based on the conversation history and your general knowledge.
Be helpful, friendly, and educational.
Return ONLY the answer in plain text.
"""
        elif lesson_context and not conversation_context:
            # Has lesson context but no history
            prompt = f"""
You are Manlayag, an AI tutor for Caraga State University.

IMPORTANT RULES:
1. Answer using ONLY the lesson context provided.
2. If the answer is NOT in the lesson context, say: 
   "The lesson does not contain enough information to answer this question."
3. Do NOT include "Source:" or lesson titles.
4. Do NOT use Markdown, bold, italic, bullet points, or numbering.
5. Respond as one or two paragraphs.

LESSON CONTEXT:
{lesson_context}

Question: {original_question}

Answer:
"""
        else:
            # No context at all - general conversation
            prompt = f"""
You are Manlayag, an AI tutor for Caraga State University.

Have a helpful conversation with the user.
Be friendly, educational, and encouraging.
Return ONLY the answer in plain text.

Question: {original_question}

Answer:
"""

        try:
            response = self.model.generate_content(prompt)
            if not response.text:
                return "I couldn't generate a response. Please try again."
            
            answer = response.text.strip()
            
            # If answer contains "not enough information", return exact message
            if "does not contain enough information" in answer.lower():
                return "The lesson does not contain enough information to answer this question."
            
            return answer
            
        except Exception as e:
            print("Gemini Error:", e)
            return f"Error: {str(e)}"