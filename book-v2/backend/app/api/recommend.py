from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.schemas.recommend import RecommendationResponse, RecommendationItem
from app.models import User, Book, Rating
from app.api.deps import get_current_user, get_current_user_optional
from app.services.recommender import get_recommender
from app.services.evaluation import EvaluationService
from app.services.explanation import ExplanationService
from app.services.gnn_recommender import get_gnn_recommender
from sqlalchemy import func
from typing import Optional

router = APIRouter()


def _get_popular_fallback(db: Session, n: int, user_id: int) -> list:
    """当推荐引擎无结果时，fallback 到热门高分书籍"""
    popular_books = (
        db.query(
            Book,
            func.avg(Rating.rating).label("avg_rating"),
            func.count(Rating.id).label("rating_count")
        )
        .join(Rating, Book.id == Rating.book_id)
        .group_by(Book.id)
        .order_by(func.avg(Rating.rating).desc(), func.count(Rating.id).desc())
        .limit(n * 3)
        .all()
    )

    recs = []
    for book, avg_rating, rating_count in popular_books[:n]:
        user_rating_record = db.query(Rating).filter(
            Rating.user_id == user_id,
            Rating.book_id == book.id
        ).first()
        recs.append(RecommendationItem(
            book_id=book.id,
            id=book.id,
            title=book.title,
            author=book.author,
            image_url=book.image_url,
            score=float(avg_rating) if avg_rating else 0.0,
            predicted_rating=float(avg_rating) if avg_rating else 0.0,
            user_rating=float(user_rating_record.rating) if user_rating_record else None,
            avg_rating=float(avg_rating) if avg_rating else None,
            reason="热门高分书籍 - 作为新用户的初始推荐",
            source="popular_fallback"
        ))
    return recs


@router.get("/cf", response_model=RecommendationResponse)
def get_cf_recommendations_query(
    n: int = Query(20, ge=1, le=100),
    refresh: bool = Query(True),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """协同过滤推荐 - 基于当前登录用户的评分数据（新用户自动 fallback 到热门推荐）"""
    user_id = current_user.id

    rating_count = db.query(Rating).filter(Rating.user_id == user_id).count()

    recs = []
    used_fallback = False

    if rating_count >= 3:
        try:
            recommender = get_recommender()
            recs = recommender.cf_recommend(user_id, n)
        except Exception:
            recs = []

    if not recs:
        used_fallback = True
        recs = _get_popular_fallback(db, n, user_id)

    return RecommendationResponse(
        user_id=user_id,
        recommendations=recs,
        total=len(recs),
        source="cf" if not used_fallback else "cf_popular_fallback"
    )


@router.get("/svd", response_model=RecommendationResponse)
def get_svd_recommendations_query(
    n: int = Query(20, ge=1, le=100),
    refresh: bool = Query(True),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """SVD 矩阵分解推荐 - 基于当前登录用户的评分数据（新用户自动 fallback 到热门推荐）"""
    user_id = current_user.id

    rating_count = db.query(Rating).filter(Rating.user_id == user_id).count()

    recs = []
    used_fallback = False

    if rating_count >= 3:
        try:
            recommender = get_recommender()
            recs = recommender.svd_recommend(user_id, n)
        except Exception:
            recs = []

    if not recs:
        used_fallback = True
        recs = _get_popular_fallback(db, n, user_id)

    return RecommendationResponse(
        user_id=user_id,
        recommendations=recs,
        total=len(recs),
        source="svd" if not used_fallback else "svd_popular_fallback"
    )


@router.get("/compare")
def get_algorithms_compare(
    n: int = Query(10, ge=1, le=50),
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional)
):
    """对比 CF 和 SVD 两种算法的推荐结果（已登录可看个人对比，未登录仅看系统统计）"""

    total_books = db.query(Book).count()
    total_ratings = db.query(Rating).count()
    total_users = db.query(Rating.user_id).distinct().count()

    rating_stats = db.query(
        func.avg(Rating.rating).label("avg_rating"),
        func.min(Rating.rating).label("min_rating"),
        func.max(Rating.rating).label("max_rating")
    ).first()

    cf_recs = []
    svd_recs = []
    cf_book_ids = []
    svd_book_ids = []

    if current_user:
        user_id = current_user.id
        rating_count = db.query(Rating).filter(Rating.user_id == user_id).count()

        recommender = None
        if rating_count >= 3:
            try:
                recommender = get_recommender()
                cf_recs = recommender.cf_recommend(user_id, n)
            except Exception:
                cf_recs = []
            try:
                if recommender is None:
                    recommender = get_recommender()
                svd_recs = recommender.svd_recommend(user_id, n)
            except Exception:
                svd_recs = []

        if not cf_recs:
            cf_recs = _get_popular_fallback(db, n, user_id)
        if not svd_recs:
            svd_recs = _get_popular_fallback(db, n, user_id)

        cf_book_ids = [r.book_id for r in cf_recs if hasattr(r, 'book_id')]
        svd_book_ids = [r.book_id for r in svd_recs if hasattr(r, 'book_id')]

    overlap = len(set(cf_book_ids) & set(svd_book_ids)) if cf_book_ids and svd_book_ids else 0

    return {
        "statistics": {
            "total_books": total_books,
            "total_ratings": total_ratings,
            "total_users": total_users,
            "avg_rating": float(rating_stats.avg_rating) if rating_stats and rating_stats.avg_rating else 0,
            "min_rating": float(rating_stats.min_rating) if rating_stats and rating_stats.min_rating else 0,
            "max_rating": float(rating_stats.max_rating) if rating_stats and rating_stats.max_rating else 10
        },
        "algorithms": [
            {
                "name": "协同过滤 (User-based CF)",
                "description": "基于用户行为相似度的推荐算法，找到相似用户并推荐他们喜欢的书籍",
                "recommendation_count": len(cf_recs),
                "books": cf_recs
            },
            {
                "name": "SVD 矩阵分解",
                "description": "基于奇异值分解的隐语义模型，将用户-物品矩阵分解为低维向量空间",
                "recommendation_count": len(svd_recs),
                "books": svd_recs
            }
        ],
        "comparison": {
            "user_id": current_user.id if current_user else None,
            "overlap_count": overlap,
            "overlap_ratio": round(overlap / max(len(cf_book_ids), 1), 2) if cf_book_ids else 0,
            "cf_unique_count": len(cf_book_ids) - overlap,
            "svd_unique_count": len(svd_book_ids) - overlap,
        },
        "tips": "如果两种算法推荐的重合度较高，说明推荐结果较为稳定；如果重合度较低，可考虑使用混合推荐。"
    }


@router.get("/cf/{user_id}", response_model=RecommendationResponse)
def get_cf_recommendations(
    user_id: int,
    n: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """协同过滤推荐（path params 兼容格式）- 仅限访问自己的推荐"""
    if user_id != current_user.id:
        raise HTTPException(status_code=403, detail="无权限访问其他用户的推荐数据")
    recommender = get_recommender()
    recs = recommender.cf_recommend(user_id, n)
    return RecommendationResponse(
        user_id=user_id,
        recommendations=recs,
        total=len(recs),
        source="cf"
    )


@router.get("/svd/{user_id}", response_model=RecommendationResponse)
def get_svd_recommendations(
    user_id: int,
    n: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """SVD 矩阵分解推荐（path params 兼容格式）- 仅限访问自己的推荐"""
    if user_id != current_user.id:
        raise HTTPException(status_code=403, detail="无权限访问其他用户的推荐数据")
    recommender = get_recommender()
    recs = recommender.svd_recommend(user_id, n)
    return RecommendationResponse(
        user_id=user_id,
        recommendations=recs,
        total=len(recs),
        source="svd"
    )


@router.get("/hybrid/{user_id}", response_model=RecommendationResponse)
def get_hybrid_recommendations(
    user_id: int,
    n: int = Query(20, ge=1, le=100),
    diversity: bool = True,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """混合推荐（path params 兼容格式）- 仅限访问自己的推荐"""
    if user_id != current_user.id:
        raise HTTPException(status_code=403, detail="无权限访问其他用户的推荐数据")
    recommender = get_recommender()
    recs, explore_count, diversity_score = recommender.hybrid_recommend(user_id, n, diversity)
    return RecommendationResponse(
        user_id=user_id,
        recommendations=recs,
        total=len(recs),
        source="hybrid",
        explore_count=explore_count,
        diversity_score=diversity_score
    )


@router.get("/cold-start/{user_id}", response_model=RecommendationResponse)
def get_cold_start_recommendations(
    user_id: int,
    n: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """冷启动推荐（path params 兼容格式）- 仅限访问自己的推荐"""
    if user_id != current_user.id:
        raise HTTPException(status_code=403, detail="无权限访问其他用户的推荐数据")
    recommender = get_recommender()
    recs = recommender.cold_start_recommend(user_id, n)
    return RecommendationResponse(
        user_id=user_id,
        recommendations=recs,
        total=len(recs),
        source="cold_start"
    )


@router.get("/explore/{user_id}", response_model=RecommendationResponse)
def get_explore_recommendations(
    user_id: int,
    n: int = Query(10, ge=1, le=50),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """探索性推荐（path params 兼容格式）- 仅限访问自己的推荐"""
    if user_id != current_user.id:
        raise HTTPException(status_code=403, detail="无权限访问其他用户的推荐数据")
    recommender = get_recommender()
    recs = recommender.cold_start_recommend(user_id, n)
    return RecommendationResponse(
        user_id=user_id,
        recommendations=recs,
        total=len(recs),
        source="explore"
    )


@router.get("/evaluation/system")
def get_system_evaluation(
    sample_size: int = Query(100, ge=10, le=500),
    db: Session = Depends(get_db)
):
    """获取系统整体评估指标"""
    ctr = EvaluationService.calculate_ctr()
    report = EvaluationService.generate_evaluation_report()
    
    return {
        "sample_size": sample_size,
        "system_metrics": report
    }


@router.get("/evaluation/{user_id}")
def get_recommendation_evaluation(
    user_id: int,
    k: int = Query(10, ge=1, le=20),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取推荐系统评估指标（仅限访问自己的评估）"""
    if user_id != current_user.id:
        raise HTTPException(status_code=403, detail="无权限访问其他用户的评估数据")
    precision = EvaluationService.calculate_precision_at_k(user_id, k)
    recall = EvaluationService.calculate_recall_at_k(user_id, k)
    diversity = EvaluationService.calculate_diversity_score(user_id)
    ctr = EvaluationService.calculate_ctr(user_id)
    
    return {
        "user_id": user_id,
        "k": k,
        "metrics": {
            "precision_at_k": precision,
            "recall_at_k": recall,
            "diversity": diversity,
            "ctr": ctr
        }
    }


@router.get("/explain/{user_id}/{book_id}")
def explain_recommendation(
    user_id: int,
    book_id: int,
    source: str = Query("cf", regex="^(cf|svd|hybrid)$"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取推荐理由（仅限查看自己的推荐理由）"""
    if user_id != current_user.id:
        raise HTTPException(status_code=403, detail="无权限访问其他用户的推荐数据")
    explanation_service = ExplanationService()
    explanation = explanation_service.generate_explanation(db, user_id, book_id, source)
    return {
        "user_id": user_id,
        "book_id": book_id,
        "explanation": explanation
    }


@router.get("/explain-batch/{user_id}")
def explain_recommendations_batch(
    user_id: int,
    n: int = Query(10, ge=1, le=50),
    source: str = Query("hybrid", regex="^(cf|svd|hybrid)$"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """批量获取推荐理由（仅限查看自己的推荐理由）"""
    if user_id != current_user.id:
        raise HTTPException(status_code=403, detail="无权限访问其他用户的推荐数据")
    recommender = get_recommender()

    if source == "cf":
        recs = recommender.cf_recommend(user_id, n)
    elif source == "svd":
        recs = recommender.svd_recommend(user_id, n)
    else:
        recs, _, _ = recommender.hybrid_recommend(user_id, n)

    explanation_service = ExplanationService()
    recs_with_explanation = explanation_service.batch_generate_explanations(
        db, user_id, recs, source
    )

    return {
        "user_id": user_id,
        "source": source,
        "recommendations": recs_with_explanation
    }


@router.get("/gnn/{user_id}")
def get_gnn_recommendations(
    user_id: int,
    n: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """基于图神经网络的书籍推荐（仅限查看自己的推荐）"""
    if user_id != current_user.id:
        raise HTTPException(status_code=403, detail="无权限访问其他用户的推荐数据")
    try:
        gnn = get_gnn_recommender()

        if gnn.user_embedding is None:
            gnn.load_data(db)

        recs = gnn.recommend(db, user_id, n)
        return {
            "user_id": user_id,
            "source": "gnn",
            "total": len(recs),
            "recommendations": recs
        }
    except Exception as e:
        return {
            "user_id": user_id,
            "source": "gnn",
            "total": 0,
            "recommendations": [],
            "warning": f"GNN model not available: {str(e)}"
        }


@router.post("/gnn/train")
def train_gnn_model(
    epochs: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """训练 GNN 模型（需要认证以防止滥用）"""
    try:
        from app.services.gnn_recommender import load_gnn_model
        load_gnn_model(db)
        return {"status": "success", "message": "GNN 模型训练完成"}
    except Exception as e:
        return {"status": "error", "message": f"训练失败: {str(e)}"}
