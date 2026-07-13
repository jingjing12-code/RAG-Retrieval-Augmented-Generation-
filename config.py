import os
from dotenv import load_dotenv

load_dotenv()

# Directories
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, 'data')
UPLOAD_DIR = os.path.join(BASE_DIR, 'upload')

# Database
DB_HOST = os.getenv('DB_HOST', 'localhost')
DB_PORT = os.getenv('DB_PORT', '5432')
DB_NAME = os.getenv('DB_NAME', 'surod_rag')
DB_USER = os.getenv('DB_USER', 'postgres')
DB_PASSWORD = os.getenv('DB_PASSWORD', '')

# Groq API
GROQ_API_KEY = os.getenv('GROQ_API_KEY', '')
GROQ_MODEL = os.getenv('GROQ_MODEL', 'llama-3.3-70b-versatile')

# Vector Search
TOP_K = 5

# Chunking
CHUNK_SIZE = 600
CHUNK_OVERLAP = 100

# System Prompt
SYSTEM_PROMPT = """You are an AI Tutor. Answer ONLY using the provided lesson context.
If the answer is not found in the lesson content, respond:
"The lesson does not contain enough information to answer this question."
Provide references to the lesson sections used."""