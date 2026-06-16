# 书籍推荐系统 V2 现代化重构设计文档

> 版本: V2.0
> 日期: 2026-06-13
> 状态: 设计完成，待评审

---

## 1. 项目概述

### 1.1 背景

当前系统（V1）使用 Flask + MySQL + 传统 CF/SVD 算法构建，功能基本可用但存在以下问题：
- **实时性差**：推荐结果一次性计算，用户行为变化无法实时反映
- **反馈单一**：仅有评分反馈，无法区分「不喜欢」和「想读但没读」
- **冷启动弱**：新用户无评分时推荐质量差，新书籍无法被推荐
- **推荐单一**：缺乏多样性探索，用户推荐结果越来越窄
- **代码耦合**：单体架构，算法与 API 高度耦合，难以扩展

### 1.2 目标

构建一个现代化的书籍推荐系统 V2，具备：
- **多维度用户反馈**：评分 + 收藏 + 不想看 + 想读
- **冷启动优化**：基于兴趣标签的新用户推荐 + 基于内容特征的新书籍推荐
- **探索-利用平衡**：在推荐中引入多样性探索，提升长尾内容曝光
- **可扩展架构**：微服务化设计，支持未来接入大模型/向量检索

### 1.3 技术栈

| 组件 | 技术选型 | 版本 |
|---|---|---|
| 后端框架 | FastAPI | 0.109+ |
| 数据库 | PostgreSQL | 15+ |
| 缓存/消息队列 | Redis + Celery | Redis 7+, Celery 5+ |
| ORM | SQLAlchemy 2.0 | 2.0+ |
| 前端框架 | Vue 3 + Vite | Vue 3.4+, Vite 5+ |
| UI 组件库 | Element Plus | 2.5+ |
| 容器化 | Docker + Docker Compose | 最新版 |
| 推荐算法 | Scikit-surprise + NumPy | - |

---

## 2. 系统架构

### 2.1 整体架构图

```
┌─────────────────────────────────────────────────────────────┐
│                        前端 (Vue 3)                          │
│   HomeView / BookDetailView / RecommendView / ProfileView    │
└─────────────────────────┬───────────────────────────────────┘
                          │ HTTP/WebSocket
                          ▼
┌─────────────────────────────────────────────────────────────┐
│                     API 网关层 (FastAPI)                      │
│  /api/auth  /api/books  /api/ratings  /api/recommend         │
│  /api/interactions  /api/users                               │
└──────────┬──────────────┬──────────────┬────────────────────┘
           │              │              │
           ▼              ▼              ▼
┌──────────────────┐ ┌──────────┐ ┌──────────────────────────┐
│   PostgreSQL     │ │  Redis   │ │   Celery Worker          │
│  - users         │ │  - 会话  │ │  - 模型训练任务          │
│  - books         │ │  - 推荐缓存│ │  - 每日重训练任务        │
│  - ratings       │ │  - 特征缓存│ │  - 数据统计任务          │
│  - interactions  │ └──────────┘ └──────────────────────────┘
│  - user_tags     │
│  - book_features │
└──────────────────┘
           │
           ▼
┌─────────────────────────────────────────────────────────────┐
│                    推荐算法服务层                              │
│   CollaborativeFiltering / SVD / HybridRecommender            │
│   InterestMatcher / ColdStartHandler / DiversityExplorer       │
└─────────────────────────────────────────────────────────────┘
```

### 2.2 目录结构

```
book-v2/
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py              # FastAPI 入口
│   │   ├── config.py            # 配置管理
│   │   ├── database.py          # 数据库连接
│   │   ├── redis_client.py      # Redis 客户端
│   │   ├── celery_app.py        # Celery 配置
│   │   ├── models/              # SQLAlchemy 模型
│   │   │   ├── __init__.py
│   │   │   ├── user.py
│   │   │   ├── book.py
│   │   │   ├── rating.py
│   │   │   ├── interaction.py
│   │   │   └── user_tag.py
│   │   ├── schemas/             # Pydantic 模型
│   │   │   ├── __init__.py
│   │   │   ├── user.py
│   │   │   ├── book.py
│   │   │   ├── rating.py
│   │   │   ├── interaction.py
│   │   │   └── recommend.py
│   │   ├── api/                 # API 路由
│   │   │   ├── __init__.py
│   │   │   ├── deps.py          # 依赖注入
│   │   │   ├── auth.py
│   │   │   ├── books.py
│   │   │   ├── ratings.py
│   │   │   ├── interactions.py
│   │   │   ├── recommend.py
│   │   │   └── users.py
│   │   ├── services/            # 业务逻辑
│   │   │   ├── __init__.py
│   │   │   ├── auth.py
│   │   │   ├── rating.py
│   │   │   ├── interaction.py
│   │   │   └── recommender/
│   │   │       ├── __init__.py
│   │   │       ├── base.py
│   │   │       ├── cf_engine.py
│   │   │       ├── svd_engine.py
│   │   │       ├── hybrid_engine.py
│   │   │       ├── cold_start.py
│   │   │       └── diversity.py
│   │   └── tasks/               # Celery 异步任务
│   │       ├── __init__.py
│   │       ├── model_training.py
│   │       └── daily_stats.py
│   ├── tests/                   # 单元测试
│   ├── alembic/                 # 数据库迁移
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── api/                 # API 调用
│   │   ├── components/          # 公共组件
│   │   ├── composables/         # 组合式函数
│   │   ├── router/
│   │   ├── stores/              # Pinia 状态管理
│   │   ├── views/
│   │   └── utils/
│   ├── package.json
│   ├── vite.config.ts
│   └── Dockerfile
├── docker-compose.yml
├── .env.example
└── README.md
```

---

## 3. 数据模型设计

### 3.1 数据库 Schema

#### users 表（扩展）
```sql
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(50) UNIQUE NOT NULL,
    email VARCHAR(100) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    avatar_url VARCHAR(500),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    is_active BOOLEAN DEFAULT TRUE
);
```

#### user_tags 表（新 - 兴趣标签）
```sql
CREATE TABLE user_tags (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    tag_name VARCHAR(50) NOT NULL,     -- 如: "科幻", "历史", "悬疑"
    weight FLOAT DEFAULT 1.0,          -- 标签权重 0-1
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(user_id, tag_name)
);
```

#### books 表（扩展）
```sql
CREATE TABLE books (
    id SERIAL PRIMARY KEY,
    isbn VARCHAR(20) UNIQUE NOT NULL,
    title VARCHAR(255) NOT NULL,
    author VARCHAR(255),
    year INTEGER,
    publisher VARCHAR(255),
    image_url VARCHAR(500),
    description TEXT,                  -- 新增：书籍简介
    category VARCHAR(100),             -- 新增：主分类
    tags TEXT[],                      -- 新增：标签数组 ["科幻", "悬疑", "美国文学"]
    avg_rating FLOAT DEFAULT 0,        -- 预计算：平均评分
    rating_count INTEGER DEFAULT 0,    -- 预计算：评分人数
    created_at TIMESTAMP DEFAULT NOW()
);
```

#### ratings 表（保留）
```sql
CREATE TABLE ratings (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    book_id INTEGER REFERENCES books(id) ON DELETE CASCADE,
    rating INTEGER NOT NULL CHECK (rating >= 1 AND rating <= 10),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(user_id, book_id)
);
```

#### interactions 表（新 - 多维度反馈）
```sql
CREATE TABLE interactions (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    book_id INTEGER REFERENCES books(id) ON DELETE CASCADE,
    interaction_type VARCHAR(20) NOT NULL,  -- 'view', 'like', 'dislike', 'want_to_read', 'read'
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(user_id, book_id, interaction_type)
);

-- interaction_type 说明:
-- 'view': 浏览（不计入推荐偏好）
-- 'like': 喜欢（正向反馈，提高推荐权重）
-- 'dislike': 不喜欢（负向反馈，降低相似内容推荐）
-- 'want_to_read': 想读（强正反馈，预测评分的先验）
-- 'read': 已读（完成反馈）
```

### 3.2 Redis 缓存设计

| Key Pattern | 类型 | TTL | 说明 |
|---|---|---|---|
| `user:{id}:profile` | Hash | 1h | 用户基本信息缓存 |
| `user:{id}:recommendations:{algo}` | List | 5min | 推荐结果缓存 |
| `book:{id}:similar` | ZSet | 1h | 相似书籍缓存 |
| `popular:books` | ZSet | 10min | 热门书籍排行 |
| `tags:popular` | ZSet | 1h | 热门标签排行 |

---

## 4. 核心功能设计

### 4.1 多维度反馈系统

#### 4.1.1 交互行为建模

每种交互类型对推荐的影响：

| 交互类型 | 对评分预测的影响 | 对推荐排序的影响 |
|---|---|---|
| view | 无 | 轻微正向 |
| like | +1.5 预测分 | 大幅提升 |
| dislike | -2 预测分 | 降低同类内容 |
| want_to_read | +1 预测分（先验） | 中等提升 |
| read | 无（需结合评分） | 无 |

#### 4.1.2 综合偏好分数计算

用户对书籍的「综合偏好分数」：

```
preference_score = (
    rating * 0.5 +                              # 评分权重 50%
    like_weight * 0.2 +                        # 喜欢权重 20%
    want_to_read_weight * 0.2 +                # 想读权重 20%
    view_weight * 0.1                          # 浏览权重 10%
) - dislike_penalty                            # 不喜欢惩罚

其中：
- rating = 归一化评分 (rating / 10)
- like_weight = 1 if liked else 0
- want_to_read_weight = 1 if wanted else 0
- view_weight = min(view_count / 10, 1)
- dislike_penalty = 0.3 if disliked else 0
```

#### 4.1.3 API 接口

```
POST /api/interactions
Body: { user_id, book_id, interaction_type }
Response: { success: true, message: "已添加喜欢" }

GET /api/interactions/{user_id}
Query: ?type=like&type=dislike
Response: { interactions: [...] }
```

#### 4.1.4 前端交互设计

在书籍详情页和推荐列表中增加交互按钮：

```
[★ 评分] [♥ 喜欢] [👀 想读] [✕ 不喜欢]
```

- **喜欢**：收藏到书单，提升同类推荐
- **想读**：加入待读清单，未评分时作为预测先验
- **不喜欢**：减少同类推荐，可选择理由（文笔差/情节无聊/不喜欢类型）

---

### 4.2 冷启动优化

#### 4.2.1 新用户冷启动：兴趣标签引导

**注册流程**：
1. 用户注册时，选择 3-5 个感兴趣的书籍类型
2. 系统记录 `user_tags` 表，权重均为 1.0
3. 基于标签匹配热门书籍，生成初始推荐

**推荐逻辑（新用户，无评分）**：

```
1. 获取用户兴趣标签列表: tags = [t1, t2, t3]
2. 匹配标签的书籍:
   - 优先: books WHERE tags && tags  (有交集)
   - 按 avg_rating DESC, rating_count DESC 排序
3. 混入 30% 热门书籍，增加多样性
4. 返回 20 本初始推荐
```

#### 4.2.2 新书籍冷启动：内容特征匹配

**书籍特征提取**：
- 从 `category` 和 `tags` 字段提取内容标签
- 从 `author` 提取作者特征（同一作者的书具有相似性）
- 从 `publisher` 提取出版社特征

**推荐逻辑（新书籍，无评分）**：

```
1. 提取新书特征: tags, author, publisher, category
2. 找到喜欢过「相似特征书籍」的用户
3. 向这些用户推荐新书
4. 结合用户标签匹配，过滤不相关用户
```

#### 4.2.3 API 接口

```
# 获取可用标签
GET /api/tags
Response: { tags: ["科幻", "悬疑", "历史", "言情", "心理", ...] }

# 设置用户兴趣标签
POST /api/users/{user_id}/tags
Body: { tags: ["科幻", "历史"] }
Response: { success: true, message: "已更新兴趣标签" }

# 获取新用户推荐
GET /api/recommend/cold-start/{user_id}?n=20
Response: { recommendations: [...], source: "tag_based" }
```

#### 4.2.4 前端设计

**注册页面改进**：
- 第 3 步：选择感兴趣的书籍类型（可多选）
- 显示标签云，用户点击选择
- 完成后立即展示个性化推荐

**书籍详情页**：
- 新书标识：「新书上架，暂无评分」
- 显示书籍标签，帮助用户了解内容

---

### 4.3 探索-利用平衡 (EE 策略)

#### 4.3.1 策略设计

采用 **ε-Greedy + 多样性约束** 混合策略：

```
推荐列表 = [
    Exploit 部分 (85%):
        - 基于用户偏好预测的最高分书籍
        - 协同过滤推荐
        - SVD 矩阵分解推荐

    Explore 部分 (15%):
        - 随机选择 1-2 本探索书籍
        - 来自用户未探索过的类别/作者
        - 使用 Diversity Sampler 确保多样性
]
```

#### 4.3.2 多样性约束

**多样性指标**：
- 类别多样性：`1 - (同类书籍数 / 总数)`，目标 > 0.7
- 作者多样性：`1 - (同作者书籍数 / 总数)`，目标 > 0.8
- 出版商多样性：`1 - (同出版社书籍数 / 总数)`，目标 > 0.6

**Diversity Sampler 算法**：
```python
def diversity_sample(candidates, n, max_same_category=3, max_same_author=2):
    """
    从候选集中采样 n 本书，同时满足多样性约束
    """
    result = []
    category_count = {}
    author_count = {}

    for book in candidates:
        cat = book.category
        author = book.author

        # 检查约束
        if category_count.get(cat, 0) >= max_same_category:
            continue
        if author_count.get(author, 0) >= max_same_author:
            continue

        result.append(book)
        category_count[cat] = category_count.get(cat, 0) + 1
        author_count[author] = author_count.get(author, 0) + 1

        if len(result) >= n:
            break

    return result
```

#### 4.3.3 API 接口

```
GET /api/recommend/explore/{user_id}?n=10&diversity=true
Response: {
    recommendations: [...],
    explore_count: 2,        # 探索书籍数量
    exploit_count: 8,        # 利用书籍数量
    diversity_score: 0.75    # 多样性分数
}
```

#### 4.3.4 前端展示

在推荐列表中区分「推荐」和「发现」：

```
┌────────────────────────────────────┐
│ 🎯 为你推荐          🔮 探索发现     │
├────────────────────────────────────┤
│ [推荐书籍...]    [探索书籍: 随机混入] │
└────────────────────────────────────┘
```

---

## 5. API 设计

### 5.1 认证相关

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/api/auth/register` | 用户注册 |
| POST | `/api/auth/login` | 用户登录 |
| POST | `/api/auth/logout` | 用户登出 |
| GET | `/api/auth/me` | 获取当前用户信息 |

### 5.2 用户相关

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/users/{id}` | 获取用户信息 |
| PUT | `/api/users/{id}` | 更新用户信息 |
| GET | `/api/users/{id}/tags` | 获取用户兴趣标签 |
| PUT | `/api/users/{id}/tags` | 更新用户兴趣标签 |

### 5.3 书籍相关

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/books` | 书籍列表/搜索 |
| GET | `/api/books/{id}` | 书籍详情（含社区评分） |
| GET | `/api/books/{id}/similar` | 相似书籍 |

### 5.4 评分相关

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/api/ratings` | 创建/更新评分 |
| GET | `/api/ratings/user/{user_id}` | 用户评分列表 |

### 5.5 交互相关（新）

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/api/interactions` | 添加交互（喜欢/不喜欢/想读） |
| GET | `/api/interactions/{user_id}` | 获取用户交互列表 |
| DELETE | `/api/interactions/{id}` | 删除交互 |

### 5.6 推荐相关

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/recommend/cf/{user_id}` | 协同过滤推荐 |
| GET | `/api/recommend/svd/{user_id}` | SVD 推荐 |
| GET | `/api/recommend/hybrid/{user_id}` | 混合推荐（含多样性） |
| GET | `/api/recommend/cold-start/{user_id}` | 新用户冷启动推荐 |
| POST | `/api/recommend/refresh/{user_id}` | 刷新推荐（触发重计算） |

---

## 6. 前端设计

### 6.1 页面结构

| 页面 | 路径 | 说明 |
|---|---|---|
| 首页 | `/` | 书籍广场、搜索、热门推荐 |
| 登录 | `/login` | 用户登录 |
| 注册 | `/register` | 用户注册（增加兴趣标签选择） |
| 书籍详情 | `/book/:id` | 书籍详情、社区评分、交互按钮 |
| 推荐页 | `/recommend` | 个性化推荐、算法对比 |
| 个人中心 | `/profile` | 评分历史、收藏书单、交互记录 |
| 标签选择 | `/onboarding` | 新用户兴趣标签引导页 |

### 6.2 组件设计

#### 6.2.1 BookCard 组件（增强）
```vue
<template>
  <div class="book-card">
    <img :src="book.image_url" :alt="book.title" />
    <div class="info">
      <h3>{{ book.title }}</h3>
      <p class="author">{{ book.author }}</p>
      <div class="rating">
        <span class="avg">{{ book.avg_rating?.toFixed(1) || 'N/A' }}</span>
        <span class="count">({{ book.rating_count }}人评)</span>
      </div>
      <!-- 交互按钮 -->
      <div class="actions">
        <button @click="toggleLike" :class="{ active: isLiked }">
          {{ isLiked ? '♥' : '♡' }}
        </button>
        <button @click="toggleWant" :class="{ active: isWanted }">
          {{ isWanted ? '👀' : '📖' }}
        </button>
        <button @click="toggleDislike" v-if="showDislike" class="dislike">
          {{ isDisliked ? '✕' : '✕' }}
        </button>
      </div>
    </div>
  </div>
</template>
```

#### 6.2.2 兴趣标签选择组件
```vue
<template>
  <div class="tag-selector">
    <h3>选择你感兴趣的书籍类型</h3>
    <p class="hint">选择 3-5 个标签，帮助我们为你推荐好书</p>
    <div class="tag-cloud">
      <button
        v-for="tag in availableTags"
        :key="tag"
        :class="{ selected: selectedTags.includes(tag) }"
        @click="toggleTag(tag)"
      >
        {{ tag }}
      </button>
    </div>
    <div class="selected-info">
      已选择: {{ selectedTags.length }}/5
    </div>
  </div>
</template>
```

### 6.3 状态管理（Pinia）

```typescript
// stores/user.ts
export const useUserStore = defineStore('user', {
  state: () => ({
    id: null,
    username: '',
    tags: [] as string[],
    preferences: {
      likedBooks: [],
      dislikedBooks: [],
      wantedBooks: [],
      ratedBooks: []
    }
  }),
  actions: {
    async fetchInteractions() {
      // 获取用户所有交互数据
    },
    async toggleLike(bookId) {
      // 切换喜欢状态
    }
  }
})
```

---

## 7. 推荐算法详细设计

### 7.1 混合推荐引擎

```python
class HybridRecommender:
    def __init__(self):
        self.cf_engine = CFEngine()
        self.svd_engine = SVDEngine()
        self.cold_start = ColdStartHandler()
        self.diversity = DiversitySampler()

    def recommend(self, user_id, n=20, include_explore=True):
        """
        混合推荐主流程
        """
        # 1. 获取用户偏好信息
        user_prefs = self._get_user_prefs(user_id)

        # 2. 判断冷启动
        if self._is_cold_start(user_prefs):
            return self.cold_start.get_recommendations(user_id, n)

        # 3. 并行计算多种推荐
        cf_recs = self.cf_engine.recommend(user_id, n * 2)
        svd_recs = self.svd_engine.recommend(user_id, n * 2)

        # 4. 合并去重
        merged = self._merge_recommendations(cf_recs, svd_recs)

        # 5. 加入交互反馈调整
        adjusted = self._apply_interaction_adjustment(merged, user_prefs)

        # 6. 多样性采样
        if include_explore:
            final = self.diversity.sample(adjusted, n)
        else:
            final = adjusted[:n]

        return final

    def _apply_interaction_adjustment(self, recs, user_prefs):
        """
        应用交互反馈调整推荐分数
        """
        for rec in recs:
            book_id = rec['book_id']

            if book_id in user_prefs['liked_books']:
                rec['score'] += 1.5
            if book_id in user_prefs['disliked_books']:
                rec['score'] -= 2.0
            if book_id in user_prefs['wanted_books']:
                rec['score'] += 1.0

            rec['score'] = max(0, rec['score'])

        return recs
```

### 7.2 探索推荐

```python
class ExplorationSampler:
    def __init__(self, explore_ratio=0.15):
        self.explore_ratio = explore_ratio

    def add_exploration(self, recs, user_id, n):
        """
        在推荐列表中加入探索性内容
        """
        explore_count = max(1, int(n * self.explore_ratio))

        # 1. 获取用户已交互过的书籍
        interacted = self._get_interacted_books(user_id)

        # 2. 获取用户不熟悉的类别
        user_categories = self._get_user_categories(user_id)
        unexplored_cats = self._get_unexplored_categories(user_categories)

        # 3. 从不熟悉的类别中随机选择
        explore_books = Book.query.filter(
            Book.category.in_(unexplored_cats),
            Book.id.notin_(interacted)
        ).order_by(func.random()).limit(explore_count).all()

        # 4. 合并到推荐列表
        result = recs[:-explore_count] + explore_books
        return result
```

---

## 8. 异步任务设计（Celery）

### 8.1 任务列表

| 任务名 | 触发方式 | 说明 |
|---|---|---|
| `train_cf_model` | 每日凌晨 / 手动触发 | 重新训练协同过滤模型 |
| `train_svd_model` | 每日凌晨 / 手动触发 | 重新训练 SVD 模型 |
| `update_book_stats` | 每小时 | 更新书籍统计数据（avg_rating, rating_count） |
| `generate_user_recommendations` | 用户交互后延迟 5min | 为用户生成新的推荐缓存 |
| `cleanup_old_interactions` | 每周 | 清理过期交互数据 |

### 8.2 任务流程

```python
# tasks/model_training.py
@celery_app.task
def train_cf_model():
    """每日模型训练任务"""
    logger.info("开始训练 CF 模型...")

    # 1. 加载最新评分数据
    ratings = load_ratings()

    # 2. 训练模型
    model = CollaborativeFiltering()
    model.fit(ratings)

    # 3. 保存模型
    save_model(model, "cf_model_v2.pkl")

    # 4. 清除用户推荐缓存
    redis_client.flush_pattern("user:*:recommendations:*")

    logger.info("CF 模型训练完成")
```

---

## 9. Docker 部署设计

### 9.1 Docker Compose 配置

```yaml
version: '3.8'

services:
  postgres:
    image: postgres:15-alpine
    environment:
      POSTGRES_DB: book_recommend
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: postgres123
    volumes:
      - postgres_data:/var/lib/postgresql/data
    ports:
      - "5432:5432"

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data

  backend:
    build: ./backend
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=postgresql://postgres:postgres123@postgres:5432/book_recommend
      - REDIS_URL=redis://redis:6379/0
    depends_on:
      - postgres
      - redis
    volumes:
      - ./backend:/app

  celery_worker:
    build: ./backend
    command: celery -A app.celery_app worker --loglevel=info
    depends_on:
      - postgres
      - redis
      - backend

  frontend:
    build: ./frontend
    ports:
      - "3000:80"
    depends_on:
      - backend
```

### 9.2 环境变量

```bash
# .env
DATABASE_URL=postgresql://postgres:postgres123@localhost:5432/book_recommend
REDIS_URL=redis://localhost:6379/0
SECRET_KEY=your-secret-key-here
DEBUG=false
CELERY_BROKER_URL=redis://localhost:6379/1
CELERY_RESULT_BACKEND=redis://localhost:6379/2
```

---

## 10. 迁移计划

### 10.1 数据迁移

1. **导出现有数据**
   - users, books, ratings 表数据导出为 JSON
   - 保留原有 user_id, book_id 映射关系

2. **数据库迁移**
   - 使用 Alembic 创建新数据库结构
   - 执行数据迁移脚本

3. **验证数据完整性**
   - 检查用户数量、书籍数量、评分数量
   - 验证关联关系正确

### 10.2 部署步骤

1. 克隆项目到新目录
2. 配置环境变量
3. 启动 Docker Compose
4. 执行数据库迁移
5. 导入历史数据
6. 验证功能正常

---

## 11. 测试计划

### 11.1 单元测试

- 各算法模块单元测试
- API 接口测试
- 数据模型验证测试

### 11.2 集成测试

- 推荐流程端到端测试
- 冷启动流程测试
- 交互反馈测试

### 11.3 性能测试

- 并发用户推荐请求压测
- 数据库查询性能
- Redis 缓存命中率

---

## 12. 风险与应对

| 风险 | 影响 | 应对措施 |
|---|---|---|
| 数据迁移丢失 | 高 | 迁移前完整备份，迁移后双重验证 |
| Docker 环境配置复杂 | 中 | 提供详细文档和 FAQ |
| 冷启动效果不佳 | 中 | A/B 测试对比，逐步优化标签匹配算法 |
| Redis/PostgreSQL 连接问题 | 中 | Docker 网络配置检查，提供本地开发模式 |

---

## 13. 后续扩展方向

本版本实现后，可进一步扩展：

1. **引入向量数据库**：使用 Milvus/Pinecone 存储书籍 embedding，支持语义搜索
2. **接入大模型**：用 LLM 生成推荐理由，实现对话式推荐
3. **实时特征工程**：使用 Flink 流处理用户实时行为
4. **A/B 测试平台**：支持流量分割和效果对比
5. **推荐多样性监控**：实时监控推荐列表多样性指标

---

## 附录

### A. 可用书籍标签列表（初始）

```
科幻, 奇幻, 悬疑, 推理, 爱情, 言情, 历史, 传记, 心理,
哲学, 宗教, 社会, 政治, 经济, 管理, 励志, 成长, 旅行,
美食, 运动, 科技, 编程, 设计, 艺术, 摄影, 音乐, 电影,
儿童, 青少年, 漫画, 武侠, 恐怖, 惊悚, 美国文学, 英国文学,
日本文学, 中国文学, 经典, 现代文学
```

### B. API 响应示例

#### 获取用户推荐
```json
{
  "user_id": 8,
  "recommendations": [
    {
      "book_id": 5409,
      "title": "The Lovely Bones",
      "author": "Alice Sebold",
      "image_url": "...",
      "score": 8.5,
      "reason": "因为你评分过《A Wrinkle In Time》，这类科幻小说你会喜欢",
      "source": "cf"
    }
  ],
  "total": 20,
  "explore_count": 3,
  "diversity_score": 0.78
}
```

---

*文档版本: 1.0*
*最后更新: 2026-06-13*
