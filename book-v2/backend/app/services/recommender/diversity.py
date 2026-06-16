import random
from typing import List, Dict, Set
from collections import Counter


class DiversitySampler:
    """Ensure diversity in recommendations"""

    def __init__(
        self,
        max_same_category: int = 3,
        max_same_author: int = 2,
        explore_ratio: float = 0.15
    ):
        self.max_same_category = max_same_category
        self.max_same_author = max_same_author
        self.explore_ratio = explore_ratio

    def sample(
        self,
        candidates: List[Dict],
        n: int,
        user_interacted: Set[int] = None
    ) -> tuple:
        """
        Sample recommendations ensuring diversity.
        Returns (final_recommendations, explore_count, diversity_score)
        """
        if not candidates:
            return [], 0, 0.0

        if user_interacted is None:
            user_interacted = set()

        # Filter out already interacted books
        filtered = [c for c in candidates if c["book_id"] not in user_interacted]

        if len(filtered) <= n:
            diversity = self._calculate_diversity(filtered)
            return filtered, 0, diversity

        # Separate exploit and explore
        exploit_count = max(1, int(n * (1 - self.explore_ratio)))
        explore_count = n - exploit_count

        # Greedy selection for exploit part
        result = []
        category_count = Counter()
        author_count = Counter()

        # Sort by score for exploit
        sorted_candidates = sorted(filtered, key=lambda x: x["score"], reverse=True)

        for candidate in sorted_candidates:
            if len(result) >= exploit_count:
                break

            category = candidate.get("category") or "unknown"
            author = candidate.get("author") or "unknown"

            # Check diversity constraints
            if category_count[category] >= self.max_same_category:
                continue
            if author_count[author] >= self.max_same_author:
                continue

            result.append(candidate)
            category_count[category] += 1
            author_count[author] += 1

        # Fill remaining with random selection
        selected_ids = {c["book_id"] for c in result}
        remaining = [c for c in filtered if c["book_id"] not in selected_ids]
        random.shuffle(remaining)

        while len(result) < n and remaining:
            candidate = remaining.pop(0)
            category = candidate.get("category") or "unknown"
            author = candidate.get("author") or "unknown"

            if category_count[category] < self.max_same_category and author_count[author] < self.max_same_author:
                result.append(candidate)
                category_count[category] += 1
                author_count[author] += 1

        diversity = self._calculate_diversity(result)

        return result, len(result) - exploit_count, diversity

    def _calculate_diversity(self, recommendations: List[Dict]) -> float:
        """Calculate diversity score (0-1, higher is more diverse)"""
        if not recommendations:
            return 0.0

        categories = [r.get("category") for r in recommendations if r.get("category")]
        authors = [r.get("author") for r in recommendations if r.get("author")]

        if not categories or not authors:
            return 0.5

        category_diversity = 1 - max(Counter(categories).values()) / len(categories)
        author_diversity = 1 - max(Counter(authors).values()) / len(authors)

        return round((category_diversity + author_diversity) / 2, 2)
