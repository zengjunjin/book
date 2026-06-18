from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, or_, desc, asc
from typing import Optional, List, Dict, Any
from pydantic import BaseModel
from app.database import get_db
from app.models import Book, Rating
from app.schemas.book import BookResponse, BookListResponse, BookDetailResponse
from app.api.deps import get_current_user, get_current_user_optional
from app.models import User, Interaction
from collections import Counter
from app.ml.embedding_service import BookEmbeddingService
from app.services.rag_service import RAGBookService

router = APIRouter()

# 内存存储搜索历史（简单实现，生产环境可考虑数据库）
_search_history_store: Dict[int, List[str]] = {}
_hot_search_terms = [
    "Harry Potter", "三体", "1984", "活着", "百年孤独",
    "The Great Gatsby", "围城", "红楼梦", "To Kill a Mockingbird",
    "人类简史", "Python", "机器学习", "深度学习"
]


class SearchHistoryRequest(BaseModel):
    term: str


@router.get("/", response_model=BookListResponse)
def get_books(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    search: Optional[str] = None,
    category: Optional[str] = None,
    sort: Optional[str] = Query(None, description="排序方式: default, rating_desc, rating_asc, reviews_desc, year_desc, year_asc, popularity"),
    min_rating: Optional[float] = Query(None, ge=0, le=10),
    max_rating: Optional[float] = Query(None, ge=0, le=10),
    year_from: Optional[int] = None,
    year_to: Optional[int] = None,
    author: Optional[str] = None,
    db: Session = Depends(get_db)
):
    query = db.query(Book)

    if search:
        query = query.filter(
            Book.title.ilike(f"%{search}%") | Book.author.ilike(f"%{search}%")
        )

    if category:
        categories = [c.strip() for c in category.split(",") if c.strip()]
        if len(categories) == 1:
            query = query.filter(Book.category == categories[0])
        else:
            query = query.filter(Book.category.in_(categories))

    if author:
        query = query.filter(Book.author.ilike(f"%{author}%"))

    if year_from:
        query = query.filter(Book.year >= year_from)
    if year_to:
        query = query.filter(Book.year <= year_to)

    # 评分筛选（基于关联的 Rating 表计算）
    if min_rating is not None or max_rating is not None:
        rating_subq = (
            db.query(
                Rating.book_id.label("book_id"),
                func.avg(Rating.rating).label("avg_r")
            )
            .group_by(Rating.book_id)
            .subquery()
        )
        query = query.outerjoin(rating_subq, rating_subq.c.book_id == Book.id)
        if min_rating is not None:
            query = query.filter(rating_subq.c.avg_r >= min_rating)
        if max_rating is not None:
            query = query.filter(rating_subq.c.avg_r <= max_rating)

    # 排序逻辑
    if sort:
        if sort == "rating_desc":
            rating_subq = (
                db.query(
                    Rating.book_id.label("book_id"),
                    func.avg(Rating.rating).label("avg_r")
                )
                .group_by(Rating.book_id)
                .subquery()
            )
            query = query.outerjoin(rating_subq, rating_subq.c.book_id == Book.id)
            query = query.order_by(desc(rating_subq.c.avg_r))
        elif sort == "rating_asc":
            rating_subq = (
                db.query(
                    Rating.book_id.label("book_id"),
                    func.avg(Rating.rating).label("avg_r")
                )
                .group_by(Rating.book_id)
                .subquery()
            )
            query = query.outerjoin(rating_subq, rating_subq.c.book_id == Book.id)
            query = query.order_by(asc(rating_subq.c.avg_r))
        elif sort == "reviews_desc":
            review_subq = (
                db.query(
                    Rating.book_id.label("book_id"),
                    func.count(Rating.id).label("cnt")
                )
                .group_by(Rating.book_id)
                .subquery()
            )
            query = query.outerjoin(review_subq, review_subq.c.book_id == Book.id)
            query = query.order_by(desc(review_subq.c.cnt))
        elif sort == "year_desc":
            query = query.order_by(desc(Book.year))
        elif sort == "year_asc":
            query = query.order_by(asc(Book.year))
        elif sort == "popularity":
            review_subq = (
                db.query(
                    Rating.book_id.label("book_id"),
                    func.count(Rating.id).label("cnt")
                )
                .group_by(Rating.book_id)
                .subquery()
            )
            query = query.outerjoin(review_subq, review_subq.c.book_id == Book.id)
            query = query.order_by(desc(review_subq.c.cnt))

    total = query.count()
    books = query.offset((page - 1) * per_page).limit(per_page).all()

    return BookListResponse(
        books=[BookResponse.model_validate(b) for b in books],
        total=total,
        page=page,
        pages=(total + per_page - 1) // per_page
    )


@router.get("/count")
def get_filtered_count(
    search: Optional[str] = None,
    category: Optional[str] = None,
    author: Optional[str] = None,
    min_rating: Optional[float] = Query(None, ge=0, le=10),
    max_rating: Optional[float] = Query(None, ge=0, le=10),
    year_from: Optional[int] = None,
    year_to: Optional[int] = None,
    db: Session = Depends(get_db)
):
    """获取筛选后的书籍数量"""
    query = db.query(Book)

    if search:
        query = query.filter(
            Book.title.ilike(f"%{search}%") | Book.author.ilike(f"%{search}%")
        )
    if category:
        categories = [c.strip() for c in category.split(",") if c.strip()]
        if len(categories) == 1:
            query = query.filter(Book.category == categories[0])
        else:
            query = query.filter(Book.category.in_(categories))
    if author:
        query = query.filter(Book.author.ilike(f"%{author}%"))
    if year_from:
        query = query.filter(Book.year >= year_from)
    if year_to:
        query = query.filter(Book.year <= year_to)

    count = query.count()
    return {"count": count, "total": db.query(Book).count()}


@router.get("/{book_id}/similar")
def get_similar_books(book_id: int, db: Session = Depends(get_db)):
    book = db.query(Book).filter(Book.id == book_id).first()
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")

    conditions = []
    if book.author:
        conditions.append(Book.author == book.author)
    if book.category:
        conditions.append(Book.category == book.category)

    if conditions:
        similar = db.query(Book).filter(
            Book.id != book_id,
            or_(*conditions)
        ).limit(6).all()
    else:
        similar = db.query(Book).filter(Book.id != book_id).limit(6).all()

    return {"similar_books": [BookResponse.model_validate(b) for b in similar]}


@router.get("/suggestions")
def get_suggestions(
    q: str = Query(..., min_length=1),
    limit: int = Query(10, ge=1, le=30),
    db: Session = Depends(get_db)
):
    """搜索建议：基于书名和作者的模糊匹配"""
    title_matches = (
        db.query(Book)
        .filter(Book.title.ilike(f"%{q}%"))
        .limit(limit)
        .all()
    )
    author_matches = (
        db.query(Book)
        .filter(Book.author.ilike(f"%{q}%"))
        .limit(limit)
        .all()
    )

    suggestions = []
    seen_titles = set()

    for book in title_matches:
        if book.title and book.title not in seen_titles:
            suggestions.append({"type": "title", "text": book.title, "book_id": book.id})
            seen_titles.add(book.title)
        if len(suggestions) >= limit:
            break

    for book in author_matches:
        if book.author and book.author not in seen_titles:
            suggestions.append({"type": "author", "text": book.author, "book_id": book.id})
            seen_titles.add(book.author)
        if len(suggestions) >= limit:
            break

    return {"suggestions": suggestions, "query": q}


@router.get("/hot-search")
def get_hot_search(limit: int = Query(10, ge=1, le=30), db: Session = Depends(get_db)):
    """热门搜索词"""
    return {"hot_search": _hot_search_terms[:limit]}


@router.get("/search-history")
def get_search_history(
    current_user: User = Depends(get_current_user)
):
    """获取当前登录用户的搜索历史"""
    history = _search_history_store.get(current_user.id, [])
    return {"history": history, "user_id": current_user.id}


@router.post("/search-history")
def add_search_history(
    req: SearchHistoryRequest,
    current_user: User = Depends(get_current_user)
):
    """为当前登录用户添加搜索历史"""
    user_id = current_user.id
    if user_id not in _search_history_store:
        _search_history_store[user_id] = []
    if req.term not in _search_history_store[user_id]:
        _search_history_store[user_id].insert(0, req.term)
    if len(_search_history_store[user_id]) > 20:
        _search_history_store[user_id] = _search_history_store[user_id][:20]
    return {"success": True, "history": _search_history_store[user_id]}


@router.delete("/search-history")
def clear_search_history(
    current_user: User = Depends(get_current_user)
):
    """清除当前登录用户的搜索历史"""
    if current_user.id in _search_history_store:
        _search_history_store[current_user.id] = []
    return {"success": True, "cleared": True}


@router.get("/categories")
def get_categories(db: Session = Depends(get_db)):
    """获取所有书籍分类 - 当无分类数据时自动 fallback 到基于作者的分组浏览"""
    # 先尝试基于 category 字段
    rows = (
        db.query(Book.category, func.count(Book.id).label("cnt"))
        .filter(Book.category.isnot(None))
        .filter(Book.category != '')
        .group_by(Book.category)
        .order_by(desc("cnt"))
        .limit(50)
        .all()
    )
    categories = []
    for row in rows:
        if row.category and row.category.strip():
            categories.append({
                "name": row.category.strip(),
                "count": row.cnt
            })

    # 如果没有分类数据，fallback 到基于热门作者的分组浏览
    if not categories:
        author_rows = (
            db.query(Book.author, func.count(Book.id).label("cnt"))
            .filter(Book.author.isnot(None))
            .filter(Book.author != '')
            .group_by(Book.author)
            .order_by(desc("cnt"))
            .limit(20)
            .all()
        )
        for row in author_rows:
            categories.append({
                "name": row.author.strip(),
                "count": row.cnt
            })

    return {
        "categories": categories,
        "total": len(categories),
        "source": "category" if rows and categories else "author_fallback"
    }


@router.get("/filters")
def get_filter_options(db: Session = Depends(get_db)):
    """获取所有筛选选项（分类、出版年份范围等）"""
    # 分类 - 同样 fallback 到作者浏览
    category_rows = (
        db.query(Book.category)
        .filter(Book.category.isnot(None))
        .filter(Book.category != '')
        .distinct()
        .limit(50)
        .all()
    )
    categories = [row.category.strip() for row in category_rows if row.category and row.category.strip()]
    source = "category"

    if not categories:
        author_rows = (
            db.query(Book.author)
            .filter(Book.author.isnot(None))
            .filter(Book.author != '')
            .distinct()
            .order_by(Book.author)
            .limit(20)
            .all()
        )
        categories = [row.author.strip() for row in author_rows if row.author and row.author.strip()]
        source = "author_fallback"

    # 年份范围
    year_stats = (
        db.query(
            func.min(Book.year).label("min_year"),
            func.max(Book.year).label("max_year")
        )
        .filter(Book.year.isnot(None))
        .first()
    )

    # 评分范围
    rating_stats = (
        db.query(
            func.min(Rating.rating).label("min_rating"),
            func.max(Rating.rating).label("max_rating"),
            func.avg(Rating.rating).label("avg_rating")
        )
        .first()
    )

    return {
        "categories": categories,
        "filter_source": source,
        "year_range": {
            "min": year_stats.min_year if year_stats and year_stats.min_year else 1900,
            "max": year_stats.max_year if year_stats and year_stats.max_year else 2024
        },
        "rating_range": {
            "min": float(rating_stats.min_rating) if rating_stats and rating_stats.min_rating else 0,
            "max": float(rating_stats.max_rating) if rating_stats and rating_stats.max_rating else 10,
            "avg": round(float(rating_stats.avg_rating), 2) if rating_stats and rating_stats.avg_rating else 0
        },
        "total_books": db.query(Book).count()
    }


@router.get("/{book_id}/semantic-similar")
def get_semantic_similar_books(
    book_id: int,
    top_k: int = Query(10, ge=1, le=20),
    db: Session = Depends(get_db)
):
    """基于 BERT 语义相似度推荐相似书籍"""
    book = db.query(Book).filter(Book.id == book_id).first()
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")

    try:
        embedding_service = BookEmbeddingService()
        similar_books = embedding_service.find_similar_books(db, book_id, top_k)
        return {"semantic_similar_books": similar_books}
    except Exception as e:
        return {"semantic_similar_books": [], "warning": f"Embedding model not available: {str(e)}"}


@router.get("/search/rag")
def rag_book_search(
    q: str = Query(..., min_length=2, description="搜索查询，如：关于人工智能的书籍"),
    top_k: int = Query(10, ge=1, le=30),
    category: Optional[str] = None,
    min_rating: Optional[float] = Query(None, ge=0, le=10),
    db: Session = Depends(get_db)
):
    """基于自然语言的书籍搜索（RAG 检索增强）"""
    try:
        rag_service = RAGBookService()
        results = rag_service.query_books(
            db, q, top_k, category, min_rating
        )
        return {
            "query": q,
            "total": len(results),
            "books": results
        }
    except Exception as e:
        return {
            "query": q,
            "total": 0,
            "books": [],
            "warning": f"RAG search failed: {str(e)}"
        }


@router.get("/search/rag/personalized")
def rag_personalized_search(
    q: str = Query(..., min_length=2),
    top_k: int = Query(10, ge=1, le=30),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """基于用户兴趣的个性化 RAG 搜索"""
    try:
        rag_service = RAGBookService()
        results = rag_service.query_by_interests(
            db, current_user.id, q, top_k
        )
        return {
            "query": q,
            "user_id": current_user.id,
            "total": len(results),
            "books": results
        }
    except Exception as e:
        return {
            "query": q,
            "total": 0,
            "books": [],
            "warning": f"Personalized RAG search failed: {str(e)}"
        }


@router.get("/{book_id}", response_model=BookDetailResponse)
def get_book(
    book_id: int,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional)
):
    """获取书籍详情（无需登录即可查看公开信息，登录后可查看个人相关数据）"""
    book = db.query(Book).filter(Book.id == book_id).first()
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")

    ratings = db.query(Rating).filter(Rating.book_id == book_id).all()
    rating_count = len(ratings)
    avg_rating = round(sum(r.rating for r in ratings) / rating_count, 1) if rating_count > 0 else None

    distribution = {str(i): 0 for i in range(1, 11)}
    for r in ratings:
        key = str(r.rating)
        if key in distribution:
            distribution[key] += 1

    most_common = Counter(r.rating for r in ratings).most_common(1)
    most_common_rating = most_common[0][0] if most_common else None

    # 只有登录用户才能看到自己的评分和交互记录
    user_rating = None
    user_interactions = {}
    if current_user:
        user_rating = db.query(Rating).filter(
            Rating.user_id == current_user.id,
            Rating.book_id == book_id
        ).first()

        interactions = db.query(Interaction).filter(
            Interaction.user_id == current_user.id,
            Interaction.book_id == book_id
        ).all()
        user_interactions = {i.interaction_type: True for i in interactions}

    return BookDetailResponse(
        **BookResponse.model_validate(book).model_dump(),
        community_rating={
            "avg_rating": avg_rating,
            "rating_count": rating_count,
            "distribution": distribution,
            "most_common_rating": most_common_rating
        },
        user_rating=user_rating.rating if user_rating else None,
        user_interactions=user_interactions
    )
