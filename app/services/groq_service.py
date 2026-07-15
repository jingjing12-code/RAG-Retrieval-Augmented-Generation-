# app/services/groq_service.py

import os
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()


class GroqService:

    def __init__(self):
        self.api_key = os.getenv("GROQ_API_KEY")
        self.model = os.getenv("GROQ_MODEL", "llama-3.1-8b-instant")
        self.is_configured = bool(self.api_key)

        if self.is_configured:
            self.client = OpenAI(
                api_key=self.api_key,
                base_url="https://api.groq.com/openai/v1"
            )
            print(f"✅ Groq initialized with model: {self.model}")
        else:
            self.client = None
            print("❌ GROQ_API_KEY not found in .env")

    def rephrase_question(self, question, history_list=None):
        """Rephrase follow-up question using Groq"""
        if not self.is_configured or not history_list:
            return question

        # Build conversation history
        hist_lines = []
        for m in history_list[-5:]:  # Last 5 exchanges
            hist_lines.append(f"User: {m.get('question')}")
            hist_lines.append(f"Assistant: {m.get('answer')}")
        hist_str = "\n".join(hist_lines)

        prompt = f"""
You are a query rewriting assistant.

CONVERSATION HISTORY:
{hist_str}

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
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a helpful assistant that rephrases follow-up questions into standalone search queries. Return only the rephrased query, nothing else."},
                    {"role": "user", "content": prompt}
                ]
            )
            rephrased = response.choices[0].message.content.strip()
            rephrased = rephrased.strip('\'"').strip()
            if rephrased:
                print(f" Rephrased '{question}' -> '{rephrased}'")
                return rephrased
            return question
        except Exception as e:
            print(f" Rephrase Error: {e}")
            return question

    def generate_answer(self, original_question, rewritten_question, context, history_text="", history_list=None):
        """Generate answer using Groq with strict lesson context"""
        if not self.is_configured:
            return "The lesson does not contain enough information to answer this question."

        # Build lesson context
        lesson_context = ""
        if context and len(context) > 0:
            lesson_context = "\n\n".join([
                f"""
Lesson: {item.get('lesson_title', 'Unknown')}
Source: {item.get('source_type', 'Unknown')}
Section: {item.get('section', 'General')}

{item.get('content', '')}
"""
                for item in context
            ])

        # If no lesson context is available, immediately return refusal
        if not lesson_context or len(lesson_context.strip()) < 50:
            return "The lesson does not contain enough information to answer this question."

        # Build conversation history for prompt
        conversation_context = ""
        if history_list and len(history_list) > 0:
            last_exchanges = history_list[-3:] if len(history_list) > 3 else history_list
            conv_lines = []
            for ex in last_exchanges:
                conv_lines.append(f"User: {ex.get('question', '')}")
                conv_lines.append(f"Assistant: {ex.get('answer', '')}")
            conversation_context = "\n".join(conv_lines)

        # --- BUILD PROMPT WITH FULL CONTEXT ---
        if conversation_context:
            prompt = f"""
You are Manlayag, an AI tutor for Caraga State University.

CRITICAL RULES:
1. Answer the current question strictly using ONLY the lesson context provided below. Do NOT use general knowledge or external information.
2. If the answer cannot be found in the provided lesson context, you must reply exactly with: "The lesson does not contain enough information to answer this question."
3. Do NOT include "Source:" or lesson titles in your answer.
4. Do NOT use Markdown, bold, italic, bullet points, or numbering.
5. Respond in plain text as one or two paragraphs.
6. Start your answer with the main point immediately. Do NOT use introductory phrases.

CONVERSATION HISTORY:
{conversation_context}

LESSON CONTEXT:
{lesson_context}

Current Question: {original_question}

Answer based ONLY on the lesson context. If the answer is not in the lesson context, reply exactly with: "The lesson does not contain enough information to answer this question."
"""
        else:
            prompt = f"""
You are Manlayag, an AI tutor for Caraga State University.

CRITICAL RULES:
1. Answer the current question strictly using ONLY the lesson context provided below. Do NOT use general knowledge or external information.
2. If the answer cannot be found in the provided lesson context, you must reply exactly with: "The lesson does not contain enough information to answer this question."
3. Do NOT include "Source:" or lesson titles.
4. Do NOT use Markdown, bold, italic, bullet points, or numbering.
5. Respond as one or two paragraphs.
6. Start your answer with the main point immediately. Do NOT use introductory phrases.

LESSON CONTEXT:
{lesson_context}

Question: {original_question}

Answer based ONLY on the lesson context above. If the answer is not in the lesson context, reply exactly with: "The lesson does not contain enough information to answer this question."
"""

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are an AI tutor. Answer strictly using only the provided lesson context. Do not use general knowledge. If the answer is not in the context, say exactly: 'The lesson does not contain enough information to answer this question.'"},
                    {"role": "user", "content": prompt}
                ]
            )
            
            answer = response.choices[0].message.content.strip()
            
            # If answer contains refusal triggers, return exact message
            if "does not contain enough information" in answer.lower():
                return "The lesson does not contain enough information to answer this question."
            
            # Remove any source references
            answer = self._clean_answer(answer)
            
            if not answer:
                return "The lesson does not contain enough information to answer this question."
            
            return answer
            
        except Exception as e:
            print(f" Groq Error: {e}")
            return "The lesson does not contain enough information to answer this question."

    def _clean_answer(self, answer):
        """Clean answer from formatting and source references"""
        import re
        
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
        
        # Remove introductory phrases
        intro_phrases = [
            r'^Based on the lesson,?\s*',
            r'^Based on my understanding,?\s*',
            r'^Let me explain,?\s*',
            r'^I think,?\s*',
            r'^From the lesson,?\s*',
            r'^According to the lesson,?\s*',
        ]
        for phrase in intro_phrases:
            answer = re.sub(phrase, '', answer, flags=re.IGNORECASE)
    
        answer = answer.replace('\n', ' ')
        answer = re.sub(r'\s+', ' ', answer).strip()
        
        return answer