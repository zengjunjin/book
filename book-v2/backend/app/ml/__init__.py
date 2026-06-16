# ML module for book recommendation system
from app.ml.config import ml_config
from app.ml.embedding_service import BookEmbeddingService

__all__ = ["ml_config", "BookEmbeddingService"]
