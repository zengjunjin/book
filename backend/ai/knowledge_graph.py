"""
🧠 书籍知识图谱生成器

将书籍内容结构化为可视化的知识图谱
"""

import random
import re
from typing import Dict, List, Optional
from dataclasses import dataclass, field

from .llm_engine import get_llm_engine
from .book_analyzer import get_book_analyzer


@dataclass
class KnowledgeNode:
    """知识节点"""
    id: str
    label: str
    type: str  # "theme", "character", "concept", "event", "motif"
    importance: float = 0.5

    def to_dict(self):
        return {"id": self.id, "label": self.label, "type": self.type, "importance": self.importance}


@dataclass
class KnowledgeEdge:
    """知识关系边"""
    source: str
    target: str
    relation: str
    weight: float = 0.5

    def to_dict(self):
        return {
            "source": self.source,
            "target": self.target,
            "relation": self.relation,
            "weight": self.weight
        }


@dataclass
class BookKnowledgeGraph:
    """书籍知识图谱"""
    book_id: int
    book_title: str
    nodes: List[KnowledgeNode] = field(default_factory=list)
    edges: List[KnowledgeEdge] = field(default_factory=list)
    themes: List[str] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
    summary: str = ""

    def to_dict(self):
        return {
            "book_id": self.book_id,
            "book_title": self.book_title,
            "nodes": [n.to_dict() for n in self.nodes],
            "edges": [e.to_dict() for e in self.edges],
            "themes": self.themes,
            "tags": self.tags,
            "summary": self.summary,
        }


class KnowledgeGraphGenerator:
    """
    书籍知识图谱生成器
    
    从多维度分析书籍的知识结构：
    - 主题层级 (核心主题 -> 子主题 -> 具体概念)
    - 关键概念和思想
    - 与其他书籍的关联
    """

    # 通用主题库
    THEME_LIBRARY = {
        "成长": ["自我认知", "蜕变", "选择", "人生阶段"],
        "爱情": ["相遇", "分离", "牺牲", "坚守", "遗憾"],
        "命运": ["宿命", "自由意志", "抗争", "偶然性"],
        "人性": ["善恶", "欲望", "理性", "情感", "道德"],
        "孤独": ["存在", "归属", "疏离", "自我"],
        "理想与现实": ["梦想", "现实", "妥协", "坚持"],
        "时间": ["记忆", "遗忘", "历史", "当下"],
        "宇宙": ["存在", "规律", "未知", "人类的位置"],
        "文明": ["进步", "衰落", "传承", "冲突"],
        "生死": ["生命的意义", "死亡", "延续", "告别"],
        "权力": ["控制", "反抗", "秩序", "自由"],
        "信仰": ["信念", "怀疑", "救赎", "希望"],
        "家庭": ["血缘", "传承", "冲突", "理解"],
        "社会": ["阶层", "规则", "变迁", "正义"],
        "自我": ["身份认同", "自我实现", "迷失", "觉醒"],
        "友谊": ["忠诚", "背叛", "陪伴", "成长"],
        "战争": ["冲突", "和平", "代价", "英雄"],
        "科技": ["进步", "伦理", "人性", "未来"],
        "自然": ["环境", "生命", "和谐", "力量"],
        "记忆": ["过去", "现在", "遗忘", "传承"],
    }

    # 通用标签库
    TAG_LIBRARY = [
        "成长", "爱情", "命运", "人性", "孤独", "理想", "现实",
        "时间", "历史", "哲学", "存在", "自由", "选择", "希望",
        "死亡", "生命", "社会", "家庭", "友谊", "救赎",
        "科幻", "奇幻", "现实", "冒险", "推理", "情感",
        "经典", "现代", "古典", "外国", "中国",
    ]

    # 关系类型
    RELATION_TYPES = [
        "引出", "影响", "关联", "包含", "发展",
        "对比", "延伸", "象征", "启发", "组成",
    ]

    def __init__(self):
        self.engine = get_llm_engine()
        self.analyzer = get_book_analyzer()

    def generate(self, book_id: int) -> BookKnowledgeGraph:
        """生成书籍知识图谱"""
        profile = self.analyzer.get_book_profile(book_id)

        if not profile:
            return self._generate_fallback(book_id)

        # 构建基础图谱
        graph = BookKnowledgeGraph(
            book_id=book_id,
            book_title=profile.title,
        )

        # 选择相关主题
        graph.themes = self._select_themes(profile)
        graph.tags = self._select_tags(profile.tags)

        # 生成节点
        graph.nodes = self._generate_nodes(profile, graph.themes)

        # 生成关系边
        graph.edges = self._generate_edges(graph.nodes)

        # 生成摘要
        graph.summary = self._generate_summary(profile, graph.themes)

        # LLM 增强（如果可用）
        if self.engine.ollama_available and random.random() > 0.3:
            self._enhance_with_llm(graph, profile)

        return graph

    def _generate_fallback(self, book_id: int) -> BookKnowledgeGraph:
        """无书籍信息时的兜底"""
        themes = random.sample(list(self.THEME_LIBRARY.keys()), 4)
        nodes = [
            KnowledgeNode(id="core", label="书籍核心", type="theme", importance=1.0),
        ]
        for i, theme in enumerate(themes):
            nodes.append(KnowledgeNode(
                id=f"theme_{i}",
                label=theme,
                type="theme",
                importance=random.uniform(0.5, 0.9)
            ))

        return BookKnowledgeGraph(
            book_id=book_id,
            book_title="目标书籍",
            nodes=nodes,
            edges=[
                KnowledgeEdge(source="core", target=f"theme_{i}",
                              relation=random.choice(self.RELATION_TYPES))
                for i in range(len(themes))
            ],
            themes=themes,
            tags=random.sample(self.TAG_LIBRARY, 6),
            summary="这本书从多个维度探讨了深刻的主题。",
        )

    def _select_themes(self, profile) -> List[str]:
        """根据书籍信息选择相关主题"""
        selected = []

        # 从书籍标签中找到匹配的主题
        for tag in profile.tags:
            if tag in self.THEME_LIBRARY:
                selected.append(tag)

        # 从标题关键词中找匹配
        title_keywords = {
            "三体": ["宇宙", "命运", "文明", "科技"],
            "活着": ["生命", "命运", "现实", "希望"],
            "百年孤独": ["时间", "命运", "孤独", "家族"],
            "红楼": ["人性", "爱情", "命运", "社会", "家族"],
            "西游": ["冒险", "成长", "信仰", "友谊"],
            "水浒": ["社会", "正义", "忠诚", "反抗"],
            "三国": ["战争", "权力", "策略", "命运"],
            "人类简史": ["历史", "文明", "人类", "社会"],
            "时间简史": ["宇宙", "时间", "科学", "存在"],
            "小王子": ["成长", "孤独", "爱情", "友谊"],
        }

        for keyword, themes in title_keywords.items():
            if keyword in profile.title:
                selected.extend(themes)
                break

        # 如果匹配太少，随机补充
        if len(selected) < 4:
            additional = random.sample(list(self.THEME_LIBRARY.keys()), 4 - len(selected))
            selected.extend(additional)

        # 去重并限制数量
        return list(dict.fromkeys(selected))[:6]

    def _select_tags(self, base_tags: List[str]) -> List[str]:
        """选择标签"""
        tags = list(base_tags)
        available = [t for t in self.TAG_LIBRARY if t not in tags]
        tags.extend(random.sample(available, min(6 - len(tags), len(available))))
        return tags[:8]

    def _generate_nodes(self, profile, themes: List[str]) -> List[KnowledgeNode]:
        """生成知识节点"""
        nodes = []

        # 根节点 - 书籍本身
        nodes.append(KnowledgeNode(
            id="root",
            label=profile.title,
            type="book",
            importance=1.0
        ))

        # 主题节点
        for i, theme in enumerate(themes):
            nodes.append(KnowledgeNode(
                id=f"theme_{i}",
                label=theme,
                type="theme",
                importance=round(random.uniform(0.6, 0.95), 2)
            ))

            # 每个主题的子概念
            sub_concepts = self.THEME_LIBRARY.get(theme, [])[:3]
            for j, concept in enumerate(sub_concepts):
                nodes.append(KnowledgeNode(
                    id=f"concept_{i}_{j}",
                    label=concept,
                    type="concept",
                    importance=round(random.uniform(0.3, 0.7), 2)
                ))

        return nodes

    def _generate_edges(self, nodes: List[KnowledgeNode]) -> List[KnowledgeEdge]:
        """生成关系边"""
        edges = []
        theme_nodes = [n for n in nodes if n.type == "theme"]
        concept_nodes = [n for n in nodes if n.type == "concept"]

        # 根节点连接到所有主题
        root = next((n for n in nodes if n.id == "root"), None)
        if root:
            for theme in theme_nodes:
                edges.append(KnowledgeEdge(
                    source=root.id,
                    target=theme.id,
                    relation="包含",
                    weight=0.9
                ))

        # 主题连接到子概念
        for concept in concept_nodes:
            # 找到"父亲"主题节点
            parts = concept.id.split("_")
            if len(parts) >= 2:
                theme_idx = parts[1]
                theme_id = f"theme_{theme_idx}"

                if any(n.id == theme_id for n in theme_nodes):
                    edges.append(KnowledgeEdge(
                        source=theme_id,
                        target=concept.id,
                        relation=random.choice(self.RELATION_TYPES),
                        weight=round(random.uniform(0.4, 0.7), 2)
                    ))

        # 主题之间的横向关联
        if len(theme_nodes) >= 2:
            for i in range(len(theme_nodes)):
                for j in range(i + 1, len(theme_nodes)):
                    if random.random() > 0.5:  # 随机建立连接
                        edges.append(KnowledgeEdge(
                            source=theme_nodes[i].id,
                            target=theme_nodes[j].id,
                            relation=random.choice(["关联", "对比", "影响"]),
                            weight=round(random.uniform(0.2, 0.5), 2)
                        ))

        return edges

    def _generate_summary(self, profile, themes: List[str]) -> str:
        """生成图谱摘要"""
        summaries = [
            f"《{profile.title}》从以下核心维度展开："
            f"{', '.join(themes[:3])}。这些主题相互交织，"
            f"构成了作品的思想深度。",

            f"通过分析《{profile.title}》的内容结构，"
            f"我们可以看到围绕{themes[0]}、{themes[1]}、"
            f"{themes[2]}等主题展开的叙事脉络。",

            f"《{profile.title}》的知识图谱揭示了作品的深层结构。"
            f"核心主题包括{themes[0]}、{themes[1]}和{themes[2]}，"
            f"这些主题在书中相互呼应、层层递进。",
        ]
        return random.choice(summaries)

    def _enhance_with_llm(self, graph: BookKnowledgeGraph, profile):
        """使用 LLM 增强图谱"""
        try:
            prompt = f"""请分析《{profile.title}》的核心主题。
用简短的 JSON 格式返回 3-5 个核心主题词，以及一句话摘要。
格式：{{"themes": ["主题1", "主题2"], "summary": "一句话摘要"}}"""

            response = self.engine.generate(prompt, use_cache=True)

            # 尝试从响应中提取 JSON
            import json as json_lib
            json_match = re.search(r'\{[^{}]*\}', response.content)
            if json_match:
                try:
                    data = json_lib.loads(json_match.group())
                    if "themes" in data and data["themes"]:
                        # 用 LLM 的主题覆盖原有主题
                        new_themes = data["themes"][:5]
                        if len(new_themes) >= 2:
                            graph.themes = new_themes
                    if "summary" in data:
                        graph.summary = data["summary"]
                except:
                    pass  # JSON 解析失败，保持原有内容
        except Exception as e:
            print(f"[KG] LLM 增强失败: {e}")

    # ========== 可视化辅助方法 ==========

    def to_graphviz(self, graph: BookKnowledgeGraph) -> str:
        """生成 Graphviz DOT 格式（用于外部可视化）"""
        lines = ["digraph KnowledgeGraph {", "  rankdir=LR;"]

        for node in graph.nodes:
            style_map = {
                "book": "filled,color=gold",
                "theme": "filled,color=lightblue",
                "concept": "filled,color=lightgray",
            }
            style = style_map.get(node.type, "")
            lines.append(f'  "{node.id}" [label="{node.label}", {style}];')

        for edge in graph.edges:
            lines.append(f'  "{edge.source}" -> "{edge.target}" [label="{edge.relation}"];')

        lines.append("}")
        return "\n".join(lines)

    def to_mermaid(self, graph: BookKnowledgeGraph) -> str:
        """生成 Mermaid 思维导图格式"""
        lines = ["mindmap"]
        lines.append(f'  root((《{graph.book_title}》))')

        theme_nodes = [n for n in graph.nodes if n.type == "theme"]

        for theme in theme_nodes:
            lines.append(f'    {theme.label}')

            # 找到这个主题的子概念
            theme_id_num = theme.id.split("_")[-1] if "_" in theme.id else ""
            related_concepts = [
                n for n in graph.nodes
                if n.type == "concept" and theme_id_num in n.id
            ]

            for concept in related_concepts[:3]:
                lines.append(f'      {concept.label}')

        return "\n".join(lines)


# ========== 单例 ==========

_kg_instance: Optional[KnowledgeGraphGenerator] = None


def get_knowledge_graph_generator() -> KnowledgeGraphGenerator:
    global _kg_instance
    if _kg_instance is None:
        _kg_instance = KnowledgeGraphGenerator()
    return _kg_instance
