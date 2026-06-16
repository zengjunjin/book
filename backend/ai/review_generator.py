"""
📝 书评生成器

基于 LLM 的个性化书评生成
"""

import random
import re
from typing import Dict, List, Optional
from dataclasses import dataclass

from .llm_engine import get_llm_engine, LLMResponse
from .book_analyzer import get_book_analyzer


@dataclass
class GeneratedReview:
    """生成的书评"""
    book_id: int
    title: str
    book_title: str
    author: str
    content: str
    rating: float
    tags: List[str]
    target_readers: str
    highlights: List[str]
    model: str
    mode: str

    def to_dict(self):
        return {
            "book_id": self.book_id,
            "title": self.title,
            "book_title": self.book_title,
            "author": self.author,
            "content": self.content,
            "rating": self.rating,
            "tags": self.tags,
            "target_readers": self.target_readers,
            "highlights": self.highlights,
            "model": self.model,
            "mode": self.mode,
        }


class ReviewGenerator:
    """
    书评生成器
    
    策略:
    - LLM 模式: 使用真实模型生成高质量书评
    - 模拟模式: 基于模板 + 书籍数据生成有个性的书评
    """

    # 书评风格（不同风格给用户选择）
    STYLES = {
        "professional": {
            "name": "专业书评",
            "tone": "专业、客观、有深度",
        },
        "personal": {
            "name": "个人读后感",
            "tone": "感性、个人、有温度",
        },
        "humorous": {
            "name": "幽默吐槽",
            "tone": "轻松、幽默、有趣",
        },
        "academic": {
            "name": "学术分析",
            "tone": "严谨、分析、有论据",
        },
    }

    def __init__(self):
        self.engine = get_llm_engine()
        self.analyzer = get_book_analyzer()

    def generate(self, book_id: int, style: str = "personal",
                 custom_prompt: str = None) -> GeneratedReview:
        """
        生成书评
        
        Args:
            book_id: 书籍ID
            style: 风格 (professional/personal/humorous/academic)
            custom_prompt: 可选的自定义提示
        """
        profile = self.analyzer.get_book_profile(book_id)

        if not profile:
            # 没有书籍信息，生成通用书评
            return self._generate_generic(book_id, style)

        # 使用 LLM 生成
        if self.engine.ollama_available:
            return self._generate_with_llm(profile, style, custom_prompt)

        # 降级到模板模式
        return self._generate_from_template(profile, style)

    def _generate_with_llm(self, profile, style: str, custom_prompt: str = None) -> GeneratedReview:
        """使用 LLM 生成书评"""
        from .prompts import get_prompt

        style_info = self.STYLES.get(style, self.STYLES["personal"])

        system_prompt = f"""你是一位经验丰富的书评人，擅长写{style_info['name']}。
风格要求：{style_info['tone']}。
用中文写作，大约 400-600 字。
使用 markdown 格式，配合 emojis。
"""

        user_prompt = custom_prompt or f"""请为《{profile.title}》写一篇{style_info['name']}。

书籍信息:
- 书名：《{profile.title}》
- 作者：{profile.author}
- 社区评分：{profile.avg_rating:.1f}/10
- 读者评价数：{profile.rating_count}
- 关键词：{', '.join(profile.tags)}

{get_prompt('review', 'user')}
"""

        response = self.engine.generate(
            prompt=user_prompt,
            system_prompt=system_prompt,
            use_cache=False
        )

        # 从响应中提取信息
        rating = self._extract_rating(response.content) or profile.avg_rating
        tags = self._extract_tags(response.content) or profile.tags[:5]
        highlights = self._extract_highlights(response.content)

        return GeneratedReview(
            book_id=profile.book_id,
            title=f"《{profile.title}》读书有感",
            book_title=profile.title,
            author=profile.author,
            content=response.content,
            rating=rating,
            tags=tags,
            target_readers=self._infer_target_readers(profile),
            highlights=highlights,
            model=response.model,
            mode=response.mode,
        )

    def _generate_from_template(self, profile, style: str) -> GeneratedReview:
        """基于模板生成（模拟模式）"""
        templates = self._get_templates()
        template = random.choice(templates)

        content = template.format(
            title=profile.title,
            author=profile.author,
            rating=profile.avg_rating,
            count=profile.rating_count,
            tags=", ".join(profile.tags[:3])
        )

        return GeneratedReview(
            book_id=profile.book_id,
            title=f"《{profile.title}》书评",
            book_title=profile.title,
            author=profile.author,
            content=content,
            rating=profile.avg_rating,
            tags=profile.tags[:5],
            target_readers=self._infer_target_readers(profile),
            highlights=["情节精彩", "人物生动", "值得深思"][:random.randint(2, 3)],
            model="template-generator",
            mode="simulate",
        )

    def _generate_generic(self, book_id: int, style: str) -> GeneratedReview:
        """通用书评（无书籍信息时）"""
        return GeneratedReview(
            book_id=book_id,
            title="这本书的书评",
            book_title="目标书籍",
            author="未知",
            content="📖 这本书值得一读。\n\n**⭐ 亮点：**\n作者在书中展现了独特的视角。\n\n**💭 感想：**\n这是一本让人思考的书，不同读者会有不同的感悟。\n\n**📌 评分：8.0/10**",
            rating=8.0,
            tags=["小说", "文学", "阅读"],
            target_readers="喜欢深度阅读的读者",
            highlights=["情节引人入胜", "主题深刻"],
            model="fallback",
            mode="simulate",
        )

    def _get_templates(self) -> List[str]:
        """获取书评模板"""
        return [
            """📖 《{title}》深度书评

**⭐ 亮点概述：**
{author} 在《{title}》中展现了令人印象深刻的叙事功力。全书围绕核心主题展开，每一页都有新的发现。

**🌟 为什么值得读：**

1. **独特的视角** — 作者没有选择常规的叙事角度，而是从一个出人意料的切入点开始，这让整本书充满了新鲜感。

2. **立体的人物** — 书中的角色不是简单的好坏标签，而是有血有肉、有优点有缺点的真实人物。

3. **深刻的主题** — 这本书探讨的主题具有普适性，任何读者都能从中找到共鸣。

**💭 个人感想：**
阅读的过程就像在一个陌生的城市漫步，虽然偶尔会迷路，但总能发现意外的风景。

{author} 的文字有一种魔力，能够让读者在不知不觉中被故事吸引。

**📌 结语：**
这不是一本适合所有人的书，但如果你是那种愿意花时间与一本书对话的读者，它一定会给你丰厚的回报。

**⭐ 评分：{rating}/10**

适合读者：{tags}爱好者。
""",

            """📖 《{title}》— 一份真诚的读后感

初次接触《{title}》是一次偶然，但很快就被它吸引。

**🎯 这本书给我的三个惊喜：**

**1. 超出预期的深度**
一开始以为只是普通的{tags}故事，读后发现作者对主题的思考远远比表面看起来要复杂。

**2. 令人难忘的人物**
书中没有一个角色是"摆设"，每个人都有自己的故事和动机。

**3. 诗意的语言**
{author} 的文字有一种独特的节奏感。

**📊 数据参考：**
• 社区评分：{rating}/10
• {count} 位读者给出评价
• 关键词：{tags}

**⭐ 评分：{rating}/10**

如果你正在寻找一本能够让你"慢下来"的书，《{title}》是一个不错的选择。
""",

            """📖 《{title}》读后感

在读完《{title}》后，我的第一反应是：这是一本需要慢慢品味的书。

**📝 为什么是一本好书：**

• **主题选择** — {author} 选择了一个既经典又常新的主题
• **叙事手法** — 结构精巧，节奏感把握得很好
• **语言风格** — 文字有质感，不空洞
• **思想深度** — 给读者留有思考空间

**💫 我最喜欢的部分：**
书中有几个场景让人久久不能忘怀。特别是当主角面临关键抉择时，作者的处理方式非常细腻。

**🎯 推荐给谁：**

✅ 喜欢高质量文学作品的读者
✅ 愿意花时间深入阅读的人
✅ 对{tags}主题感兴趣的读者

**⭐ 最终评分：{rating}/10**

📌 一句话总结：一本值得反复阅读的佳作。
""",
        ]

    def _extract_rating(self, text: str) -> Optional[float]:
        """从文本中提取评分"""
        match = re.search(r"(\d+(?:\.\d+)?)\s*(?:/|分|星)", text)
        if match:
            try:
                return float(match.group(1))
            except:
                pass
        return None

    def _extract_tags(self, text: str) -> List[str]:
        """从文本中提取关键词/标签"""
        potential = re.findall(r"「([^」]+)」|《([^》]+)》|『([^』]+)』|\"([^\"]+)\"", text)
        tags = []
        for match in potential:
            for group in match:
                if group and 2 <= len(group) <= 10:
                    tags.append(group)
        return list(set(tags))[:5] if tags else []

    def _extract_highlights(self, text: str) -> List[str]:
        """提取亮点/摘要"""
        lines = text.split("\n")
        highlights = []
        for line in lines:
            if any(kw in line for kw in ["亮点", "优点", "喜欢", "精彩", "理由"]):
                highlights.append(line.strip("•- 123456789."))
        return highlights[:3] if highlights else []

    def _infer_target_readers(self, profile) -> str:
        """根据书籍信息推断目标读者"""
        readers_map = {
            "科幻": "喜欢思考和想象的科幻爱好者",
            "文学": "喜欢深度阅读的文学爱好者",
            "经典": "追求永恒价值的读者",
            "历史": "对过去感兴趣、喜欢思考的读者",
            "哲学": "喜欢深度思考的读者",
            "科普": "对知识有好奇心的读者",
        }

        for tag in profile.tags:
            if tag in readers_map:
                return readers_map[tag]

        return "对优质内容有鉴赏力的读者"

    def get_available_styles(self) -> Dict[str, Dict]:
        """获取可用的书评风格"""
        return self.STYLES


# ========== 单例 ==========

_review_generator_instance: Optional[ReviewGenerator] = None


def get_review_generator() -> ReviewGenerator:
    global _review_generator_instance
    if _review_generator_instance is None:
        _review_generator_instance = ReviewGenerator()
    return _review_generator_instance
