from app.models.user import User
from app.models.book import Book
from app.models.rating import Rating
from app.models.interaction import Interaction
from app.models.user_tag import UserTag
from app.models.recommendation_log import RecommendationLog
from app.models.social import Review, Comment, ReviewLike, Follow, Discussion, DiscussionReply

__all__ = [
    "User", "Book", "Rating", "Interaction", "UserTag", "RecommendationLog",
    "Review", "Comment", "ReviewLike", "Follow", "Discussion", "DiscussionReply"
]
