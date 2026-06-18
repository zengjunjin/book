from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
from app.database import Base, engine
from app.api import auth, books, ratings, interactions, recommend, users, reviews, social, discussions, ai, streaming

app = FastAPI(
    title="Book Recommendation System V2",
    description="Modern book recommendation system with multi-dimensional feedback",
    version="2.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

Base.metadata.create_all(bind=engine)


@app.on_event("startup")
async def startup_event():
    """应用启动时预加载推荐引擎，避免首次请求超时"""
    import logging
    logger = logging.getLogger(__name__)
    logger.info("预加载推荐引擎...")
    try:
        from app.services.recommender import get_recommender
        get_recommender()  # 预初始化单例
        logger.info("推荐引擎预加载完成")
    except Exception as e:
        logger.warning(f"推荐引擎预加载失败（将在首次请求时加载）: {e}")


# Include routers
app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(users.router, prefix="/api/users", tags=["users"])
app.include_router(books.router, prefix="/api/books", tags=["books"])
app.include_router(ratings.router, prefix="/api/ratings", tags=["ratings"])
app.include_router(interactions.router, prefix="/api/interactions", tags=["interactions"])
app.include_router(recommend.router, prefix="/api/recommend", tags=["recommend"])
app.include_router(reviews.router, prefix="/api/reviews", tags=["reviews"])
app.include_router(social.router, prefix="/api/social", tags=["social"])
app.include_router(discussions.router, prefix="/api/discussions", tags=["discussions"])
app.include_router(ai.router, prefix="/api")  # AI 助手 (chat, search, status) - 路径已包含 /ai 前缀
app.include_router(streaming.router, prefix="/api/streaming", tags=["streaming"])


@app.get("/api/health")
def health_check():
    return {"status": "ok", "version": "2.0.0"}
