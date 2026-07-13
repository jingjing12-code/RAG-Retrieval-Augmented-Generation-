# app/services/embedding.py

from groq import Groq
import os

class EmbeddingService:
    def __init__(self):
        self.api_key = os.getenv('GROQ_API_KEY')
        self.model = os.getenv('GROQ_EMBED_MODEL', 'text-embedding-3-small')
        self.is_configured = bool(self.api_key)
        if self.is_configured:
            self.client = Groq(api_key=self.api_key)

    def get_embedding(self, text):
        if not self.is_configured:
            return None
        try:
            if not text:
                return None
            if len(text) > 8000:
                text = text[:8000]
            response = self.client.embeddings.create(
                model=self.model,
                input=text
            )
            return response.data[0].embedding
        except Exception as e:
            print(f"Embedding error: {e}")
            return None