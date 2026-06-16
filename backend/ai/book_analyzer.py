"""
📖 书籍智能分析器 v2.0

基于书籍元数据和评分数据的智能分析 + 摘要生成
"""

import random
import time
import hashlib
from typing import Dict, List, Optional
from dataclasses import dataclass

from .llm_engine import get_llm_engine, LLMResponse


@dataclass
class BookProfile:
    """书籍画像"""
    book_id: int
    title: str
    author: str
    publisher: str = ""
    year: str = ""
    avg_rating: float = 7.5
    rating_count: int = 0
    tags: List[str] = None
    categories: List[str] = None
    description: str = ""

    def __post_init__(self):
        if self.tags is None:
            self.tags = []
        if self.categories is None:
            self.categories = []

    def to_dict(self):
        return {
            'book_id': self.book_id,
            'title': self.title,
            'author': self.author,
            'publisher': self.publisher,
            'year': self.year,
            'avg_rating': self.avg_rating,
            'rating_count': self.rating_count,
            'tags': self.tags,
            'categories': self.categories,
            'description': self.description,
        }


@dataclass
class BookSummary:
    """书籍摘要"""
    book_id: int
    title: str
    author: str
    one_line: str  # 一句话简介
    overview: str  # 整体概述
    themes: List[str]  # 核心主题
    highlights: List[str]  # 亮点
    target_audience: str  # 目标读者
    reading_guide: str  # 阅读建议
    model: str = ""
    mode: str = ""

    def to_dict(self):
        return {
            'book_id': self.book_id,
            'title': self.title,
            'author': self.author,
            'one_line': self.one_line,
            'overview': self.overview,
            'themes': self.themes,
            'highlights': self.highlights,
            'target_audience': self.target_audience,
            'reading_guide': self.reading_guide,
            'model': self.model,
            'mode': self.mode,
        }


class BookAnalyzer:
    """
    书籍智能分析器 v2.0

    功能:
    - 从数据库提取完整书籍画像
    - 分析社区评价
    - 生成书籍摘要
    - 生成书籍"指纹"用于相似推荐
    """

    def __init__(self, db=None):
        self.db = db
        self.engine = get_llm_engine()

    def get_book_profile(self, book_id: int) -> Optional[BookProfile]:
        """从数据库获取完整的书籍画像"""
        if self.db is None:
            try:
                from extensions import db as _db
                self.db = _db
            except:
                return None

        try:
            # 直接使用模型查询
            from models import Book, Rating

            book = Book.query.get(book_id)
            if not book:
                return None

            # 获取评分统计
            rating_result = Rating.query.filter_by(book_id=book_id).all()
            avg_rating = sum(r.rating for r in rating_result) / len(rating_result) if rating_result else 7.5
            rating_count = len(rating_result)

            # 提取标签
            tags = self._extract_tags(book.title or "")

            profile = BookProfile(
                book_id=book.id,
                title=book.title or "未知书名",
                author=book.author or "未知作者",
                publisher=book.publisher or "",
                year=str(book.year) if book.year else "",
                avg_rating=avg_rating,
                rating_count=rating_count,
                tags=tags,
                categories=self._categorize(tags, book.title or ""),
                description=f"{book.title or ''} ({book.publisher or ''}, {book.year or ''})"
            )

            return profile

        except Exception as e:
            print(f"[Analyzer] 获取书籍画像失败: {e}")
            return None

    def get_book_by_isbn(self, isbn: str) -> Optional[BookProfile]:
        """通过 ISBN 获取书籍"""
        if self.db is None:
            try:
                from extensions import db as _db
                self.db = _db
            except:
                return None

        try:
            conn = self.db.engine.connect()
            result = conn.execute(
                self.db.text("SELECT id FROM books WHERE isbn = :isbn LIMIT 1"),
                {"isbn": isbn}
            )
            row = result.fetchone()
            conn.close()

            if row:
                return self.get_book_profile(row[0])
            return None
        except:
            return None

    def search_books(self, query: str, limit: int = 10) -> List[Dict]:
        """搜索书籍"""
        try:
            from models import Book
            books = Book.query.filter(
                (Book.title.like(f"%{query}%")) | (Book.author.like(f"%{query}%"))
            ).limit(limit).all()

            return [
                {"id": b.id, "title": b.title, "author": b.author or "未知", "publisher": b.publisher or ""}
                for b in books
            ]
        except Exception as e:
            print(f"[Analyzer] 搜索失败: {e}")
            return []

    def _extract_tags(self, title: str) -> List[str]:
        """从书名提取关键词标签"""
        keyword_map = {
            "三体": ["科幻", "宇宙", "哲学", "硬科幻", "刘慈欣"],
            "活着": ["文学", "人生", "现实", "经典", "余华"],
            "平凡的世界": ["文学", "现实", "成长", "中国", "路遥"],
            "百年孤独": ["魔幻现实", "拉美", "经典", "文学", "马尔克斯"],
            "红楼梦": ["古典", "中国", "文学", "经典", "曹雪芹"],
            "西游记": ["古典", "神话", "冒险", "中国", "神魔"],
            "水浒传": ["古典", "侠义", "中国", "文学", "反抗"],
            "三国演义": ["历史", "战争", "谋略", "古典", "罗贯中"],
            "人类简史": ["历史", "人类学", "科普", "社会学", "思考"],
            "时间简史": ["科普", "物理", "宇宙", "霍金", "科学"],
            "小王子": ["童话", "哲学", "经典", "成长", "圣埃克苏佩里"],
            "围城": ["文学", "讽刺", "现代", "中国", "钱钟书"],
            "老人与海": ["文学", "勇气", "经典", "外国", "海明威"],
            "追风筝的人": ["文学", "成长", "阿富汗", "救赎", "胡赛尼"],
            "解忧杂货店": ["文学", "日本", "温暖", "推理", "东野圭吾"],
            "挪威的森林": ["文学", "日本", "青春", "爱情", "村上春树"],
            "哈利波特": ["奇幻", "魔法", "冒险", "英国", "罗琳"],
            "指环王": ["奇幻", "冒险", "史诗", "托尔金", "魔法"],
            "1984": ["反乌托邦", "政治", "经典", "外国", "奥威尔"],
            "动物庄园": ["政治", "寓言", "经典", "外国", "奥威尔"],
            "沉默的羔羊": ["推理", "悬疑", "心理", "外国", "惊悚"],
            "福尔摩斯": ["推理", "侦探", "经典", "英国", "柯南道尔"],
            "基地": ["科幻", "太空", "史诗", "阿西莫夫", "未来"],
            "星际穿越": ["科幻", "太空", "电影", "物理", "诺兰"],
            "黑客帝国": ["科幻", "哲学", "赛博朋克", "电影", "虚拟现实"],
            "流浪地球": ["科幻", "中国", "太空", "刘慈欣", "电影"],
            "金庸": ["武侠", "中国", "江湖", "侠义", "武功"],
            "古龙": ["武侠", "中国", "江湖", "侦探", "武侠小说"],
        }

        for key, tags in keyword_map.items():
            if key.lower() in title.lower():
                return tags

        # 默认随机选择一些通用标签
        return random.sample([
            "小说", "文学", "阅读", "经典", "成长", "人生",
            "社会", "心理", "历史", "文化", "哲学", "科学"
        ], 3)

    def _categorize(self, tags: List[str], title: str) -> List[str]:
        """根据标签确定类别"""
        category_map = {
            "科幻": "Sci-Fi & Fantasy",
            "宇宙": "Science & Philosophy",
            "文学": "Literature & Fiction",
            "经典": "Classics",
            "历史": "History",
            "哲学": "Philosophy",
            "科普": "Science",
            "童话": "Children & Young Adult",
            "古典": "Classical Chinese",
            "神话": "Mythology",
            "成长": "Coming of Age",
            "人生": "Life & Reflection",
            "武侠": "Martial Arts Fiction",
            "推理": "Mystery & Thriller",
            "奇幻": "Fantasy",
            "心理": "Psychology",
        }

        categories = []
        for tag in tags:
            if tag in category_map:
                categories.append(category_map[tag])

        # 检查书名关键词
        if "简史" in title or "人类" in title:
            categories.append("Popular Science")
        if any(kw in title for kw in ["心理学", "心经", "心理"]):
            categories.append("Self-Help")

        return categories[:3] or ["General Reading"]

    def get_similar_books(self, book_id: int, limit: int = 5) -> List[Dict]:
        """获取相似书籍（基于标签/评分相似度）"""
        profile = self.get_book_profile(book_id)
        if not profile:
            return []

        try:
            from models import Book, Rating
            from sqlalchemy import func

            # 获取评分相似的其他书籍
            subquery = self.db.session.query(
                Rating.book_id,
                func.avg(Rating.rating).label('avg_rating'),
                func.count(Rating.id).label('rating_count')
            ).group_by(Rating.book_id).subquery()

            books = self.db.session.query(
                Book.id,
                Book.title,
                Book.author,
                subquery.c.avg_rating,
                subquery.c.rating_count
            ).outerjoin(subquery, Book.id == subquery.c.book_id).filter(
                Book.id != book_id
            ).limit(limit).all()

            results = []
            for row in books:
                book_avg = row.avg_rating or 7.5
                rating_diff = abs(book_avg - profile.avg_rating)
                similarity = max(0.5, 1 - rating_diff / 5) * 0.8 + random.uniform(0, 0.2)

                results.append({
                    "book_id": row.id,
                    "title": row.title,
                    "author": row.author or "未知",
                    "similarity": round(similarity, 2),
                    "avg_rating": round(book_avg, 1),
                    "rating_count": row.rating_count or 0,
                    "reason": self._generate_similarity_reason(profile, row.title, row.author)
                })

            # 按相似度排序
            results.sort(key=lambda x: x['similarity'], reverse=True)
            return results[:limit]

        except Exception as e:
            print(f"[Analyzer] 相似书籍获取失败: {e}")
            return []

    def _generate_similarity_reason(self, profile: BookProfile, other_title: str, other_author: str) -> str:
        """生成相似原因"""
        reasons = []
        for tag in profile.tags[:2]:
            reasons.append(f"与《{profile.title}》同样探讨{tag}主题")

        if not reasons:
            reasons.append(f"与《{profile.title}》评分相近，值得一读")

        return random.choice(reasons) if reasons else f"与《{profile.title}》风格相近"

    def analyze_book(self, book_id: int, use_llm: bool = True) -> Dict:
        """完整分析一本书"""
        profile = self.get_book_profile(book_id)
        if not profile:
            return {"error": "未找到书籍"}

        result = {
            "profile": profile.to_dict(),
            "similar_books": self.get_similar_books(book_id),
            "summary": None,
            "analysis": None,
        }

        # 生成摘要
        summary = self.generate_summary(book_id)
        if summary:
            result["summary"] = summary.to_dict()

        # LLM 深入分析
        if use_llm:
            prompt = f"""请分析《{profile.title}》（作者: {profile.author}）。
这本书获得了 {profile.avg_rating}/10 的平均评分，有 {profile.rating_count} 位读者评价。
关键词标签: {', '.join(profile.tags)}

请用中文生成一份简短的分析报告，包括主题、风格、读者定位。"""

            response = self.engine.generate(prompt)
            result["analysis"] = response.to_dict()

        return result

    def generate_summary(self, book_id: int) -> Optional[BookSummary]:
        """生成书籍摘要"""
        profile = self.get_book_profile(book_id)
        if not profile:
            return None

        # 如果 LLM 可用，生成更智能的摘要
        if self.engine.ollama_available:
            return self._generate_llm_summary(profile)

        # 否则使用模板模式
        return self._generate_template_summary(profile)

    def _generate_llm_summary(self, profile: BookProfile) -> BookSummary:
        """使用 LLM 生成摘要"""
        prompt = f"""请为《{profile.title}》（{profile.author}）生成书籍摘要。

书籍信息：
- 评分: {profile.avg_rating}/10（{profile.rating_count}人评价）
- 类别: {', '.join(profile.tags)}
- 出版社: {profile.publisher or '未知'}（{profile.year or '未知年份'}）

请用 JSON 格式返回：
{{
    "one_line": "一句话简介（15字内）",
    "overview": "整体概述（100字内）",
    "themes": ["主题1", "主题2", "主题3"],
    "highlights": ["亮点1", "亮点2", "亮点3"],
    "target_audience": "目标读者描述",
    "reading_guide": "阅读建议"
}}
只返回 JSON，不要其他文字。"""

        response = self.engine.generate(prompt, use_cache=True)

        # 尝试解析 JSON
        try:
            import json
            import re
            json_match = re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', response.content, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group())
                return BookSummary(
                    book_id=profile.book_id,
                    title=profile.title,
                    author=profile.author,
                    one_line=data.get("one_line", "一本值得阅读的书"),
                    overview=data.get("overview", "精彩的作品"),
                    themes=data.get("themes", profile.tags[:3]),
                    highlights=data.get("highlights", ["内容精彩", "值得一读"]),
                    target_audience=data.get("target_audience", "适合喜欢阅读的人"),
                    reading_guide=data.get("reading_guide", "建议仔细阅读"),
                    model=response.model,
                    mode=response.mode,
                )
        except:
            pass

        # 解析失败，返回模板摘要
        return self._generate_template_summary(profile)

    def _generate_template_summary(self, profile: BookProfile) -> BookSummary:
        """使用模板生成摘要"""
        templates = {
            "one_line": [
                f"《{profile.title}》是一部引人深思的{profile.tags[0] if profile.tags else '文学'}作品",
                f"{profile.author} 的《{profile.title}》展现了深刻的思想内涵",
                f"《{profile.title}》带你探索{profile.tags[0] if profile.tags else '人生'}的奥秘",
            ],
            "overview": [
                f"《{profile.title}》是{profile.author}的代表作之一，自出版以来深受读者喜爱。",
                f"这本书以独特的视角切入{profile.tags[0] if profile.tags else '文学'}主题，",
                f"通过细腻的描写和深刻的思想内涵，为读者呈现了一部不可多得的佳作。",
            ],
            "reading_guide": [
                "建议在安静的环境下细细品读，感受作者的思想脉络。",
                "可以先快速通读，再深入研读感兴趣的章节。",
                "阅读时可以配合相关背景资料，获得更好的理解。",
            ]
        }

        return BookSummary(
            book_id=profile.book_id,
            title=profile.title,
            author=profile.author,
            one_line=random.choice(templates["one_line"]),
            overview="".join(random.choice(templates["overview"]) for _ in range(2)),
            themes=profile.tags[:4],
            highlights=[
                f"评分 {profile.avg_rating}/10，{profile.rating_count} 位读者推荐",
                f"探讨{profile.tags[0] if profile.tags else '人生'}主题",
                f"{profile.author} 的经典之作",
            ],
            target_audience=f"喜欢{profile.tags[0] if profile.tags else '文学'}的读者",
            reading_guide=random.choice(templates["reading_guide"]),
            model="template-generator",
            mode="simulate",
        )


# ========== 单例 ==========

_analyzer_instance = None


def get_book_analyzer() -> BookAnalyzer:
    global _analyzer_instance
    if _analyzer_instance is None:
        _analyzer_instance = BookAnalyzer()
    return _analyzer_instance
