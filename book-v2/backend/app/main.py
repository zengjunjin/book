from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
from app.api import auth, books, ratings, interactions, recommend, users, reviews, social, discussions

app = FastAPI(
    title="Book Recommendation System V2",
    description="Modern book recommendation system with multi-dimensional feedback",
    version="2.0.0",
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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


@app.get("/api/health")
def health_check():
    return {"status": "ok", "version": "2.0.0"}
