from flask import Flask, jsonify, send_from_directory
from flask_cors import CORS
from app.models.database import db
from app.routes.ingest import ingest_bp
from app.routes.ask import ask_bp
from app.routes.documents import documents_bp
import os
from dotenv import load_dotenv

load_dotenv()

def create_app():
    app = Flask(__name__, static_folder='static', static_url_path='')
    
    app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev-secret')
    app.config['SQLALCHEMY_DATABASE_URI'] = f"postgresql://{os.getenv('DB_USER')}:{os.getenv('DB_PASSWORD')}@{os.getenv('DB_HOST')}:{os.getenv('DB_PORT')}/{os.getenv('DB_NAME')}"
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    
    db.init_app(app)
    CORS(app)
    
    # Register blueprints
    app.register_blueprint(ingest_bp)
    app.register_blueprint(ask_bp)
    app.register_blueprint(documents_bp)
    
    @app.route('/')
    def index():
        return send_from_directory('static', 'index.html')
    
    @app.route('/<path:path>')
    def static_files(path):
        return send_from_directory('static', path)
    
    @app.route('/api/status', methods=['GET'])
    def get_status():
        from app.services.retrieval import RetrievalService
        stats = RetrievalService().get_stats()
        return jsonify({
            'status': 'ok',
            'system': 'AI Tutor RAG',
            'documents': stats.get('documents', 0),
            'chunks': stats.get('chunks', 0),
            'vectors': stats.get('vectors', 0)
        })
    
    with app.app_context():
        db.create_all()
        print("✅ Database tables ready")
    
    return app