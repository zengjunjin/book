# v1 ↔ v2 整合清点报告

> 生成时间：2026-06-17
> 整合策略：以 v2（FastAPI + PG + TS）为主框架，把 v1 业务能力迁入
> 清理策略：所有可删项集中到本文档，**测试通过前不实际删除**

---

## 一、v1 → v2 需迁入的资产（v2 缺失）

| v1 资产 | 路径 | v2 落地位置 | 状态 |
|---------|------|------------|------|
| Embedding 服务（FAISS + sentence-transformers） | [backend/services/embedding_service.py](file:///C:/Users/15116/Desktop/book/backend/services/embedding_service.py) | v2: `app/ml/embedding_service.py`（仅占位，待补） | 待迁移 |
| Ollama Embedding（备用） | [backend/services/ollama_embedding.py](file:///C:/Users/15116/Desktop/book/backend/services/ollama_embedding.py) | v2: `app/ml/ollama_embedding.py` | 待迁移 |
| RAG / 智能体（AI 助手） | [backend/ai/routes.py](file:///C:/Users/15116/Desktop/book/backend/ai/routes.py) | v2: 新建 `app/api/ai.py` | 待迁移 |
| AI 子模块（knowledge_graph、review_generator、report_generator、conversation、book_analyzer、llm_engine、prompts） | [backend/ai/](file:///C:/Users/15116/Desktop/book/backend/ai/) | v2: 新建 `app/services/ai/` | 待迁移 |
| User profile（基于评分的画像） | [backend/services/user_profile.py](file:///C:/Users/15116/Desktop/book/backend/services/user_profile.py) | v2: `app/services/user_profile.py` | 待迁移 |
| Content filter | [backend/services/content_filter.py](file:///C:/Users/15116/Desktop/book/backend/services/content_filter.py) | v2: `app/services/recommender/content_filter.py` | 待迁移 |
| SVD 算法（surprise 库） | [backend/services/svd_algorithm.py](file:///C:/Users/15116/Desktop/book/backend/services/svd_algorithm.py) | v2: 完善 `app/services/recommender/svd_engine.py` | 待迁移 |
| Search service（BM25 + MeiliSearch） | [backend/services/search_service.py](file:///C:/Users/15116/Desktop/book/backend/services/search_service.py) | v2: `app/services/search_service.py` | 待迁移 |
| 多级缓存（L1/L2） | [backend/services/cache.py](file:///C:/Users/15116/Desktop/book/backend/services/cache.py) | v2: `app/services/cache.py` | 待迁移 |
| 限流/熔断/中间件 | [backend/services/middleware.py](file:///C:/Users/15116/Desktop/book/backend/services/middleware.py) | v2: `app/middleware.py` | 待迁移 |
| Prometheus metrics | [backend/services/metrics.py](file:///C:/Users/15116/Desktop/book/backend/services/metrics.py) | v2: `app/metrics.py` | 待迁移 |
| Validators | [backend/services/validators.py](file:///C:/Users/15116/Desktop/book/backend/services/validators.py) | v2: `app/schemas/validators.py` | 待迁移 |
| 前端深色玻璃 UI（HomeView、BookDetailView、BookCard、AppSidebar、App.vue） | [frontend/src/](file:///C:/Users/15116/Desktop/book/frontend/src/) | v2: `frontend-v2/src/views/` 补全 | 待迁移 |
| 前端 API 封装 | [frontend/src/api/index.js](file:///C:/Users/15116/Desktop/book/frontend/src/api/index.js) | v2: `frontend-v2/src/api/` | 待迁移 |
| 前端 Pinia stores | [frontend/src/stores/](file:///C:/Users/15116/Desktop/book/frontend/src/stores/) | v2: 补全 pinia | 待迁移 |

---

## 二、v2 缺口清单（需补全/重写）

| v2 文件 | 问题 | 行动 |
|---------|------|------|
| [app/api/recommend.py](file:///C:/Users/15116/Desktop/book/book-v2/backend/app/api/recommend.py#L12-L29) | 4 个 `*_placeholder` 函数返回空 | 接入 v1 真实算法 |
| [app/api/social.py](file:///C:/Users/15116/Desktop/book/book-v2/backend/app/api/social.py) | 实现不完整（v1 已有完整版） | 用 v1 替换 |
| [app/api/discussions.py](file:///C:/Users/15116/Desktop/book/book-v2/backend/app/api/discussions.py) | 待审查是否完整 | 端点测一遍 |
| [app/api/reviews.py](file:///C:/Users/15116/Desktop/book/book-v2/backend/app/api/reviews.py) | 待审查 | 端点测一遍 |
| [app/api/users.py](file:///C:/Users/15116/Desktop/book/book-v2/backend/app/api/users.py) | 待审查 | 端点测一遍 |
| [app/ml/embedding_service.py](file:///C:/Users/15116/Desktop/book/book-v2/backend/app/ml/embedding_service.py) | 仅有占位 config | 接入 v1 真实实现 |
| [app/services/recommender/](file:///C:/Users/15116/Desktop/book/book-v2/backend/app/services/recommender/) | cf/svd/cold_start 框架有但未接 DB/缓存 | 接线 + 测试 |
| 缺 AI 助手模块 | v2 没有 ai/* | 从 v1 迁入 |
| 缺搜索引擎 | v2 没有 search_service | 从 v1 迁入 |
| 缺 pytest 测试 | v2 无 tests/ | 建立 tests/ |

---

## 三、待删除清单（测试通过前不执行）

### 3.1 v1 中会被 v2 替代的资产
- [ ] `backend/` 整个目录（迁入完成后）
- [ ] `frontend/` 整个目录（迁入完成后）
- [ ] `backend/static/` 整个目录（旧的 SPA 构建产物）
- [ ] `frontend/dist/` 整个目录
- [ ] `backend/_diag.py` 临时诊断脚本（v1 的）
- [ ] `backend/scripts/acceptance_*.py` 旧的验收脚本（用 pytest 替代）

### 3.2 v2 中的冗余/占位代码
- [ ] `app/api/recommend.py` 中的 `*_placeholder` 函数（被真实算法替换后）
- [ ] v2 中任何仅 print "TODO" 的空函数
- [ ] `frontend-v2/src/views/RecommendView.vue` 的极简版（用 v1 的 UI 替换）

### 3.3 临时/调试文件
- [ ] 项目根目录的 `_test_*.py`、`_check_*.py`、`_kill_*.py`（继续保留 .gitignore）
- [ ] `pgsql/`、`dump.rdb`（已加 .gitignore）
- [ ] `book-v2/pgsql/`（已加 .gitignore）

### 3.4 文档
- [ ] `docs/superpowers/plans/2026-06-13-book-recommend-v2-implementation-plan.md` 完成后归档
- [ ] `docs/superpowers/specs/2026-06-13-book-recommend-v2-design.md` 完成后归档
- [ ] `docs/superpowers/specs/2026-06-13-ui-optimization-design.md` 完成后归档
- [ ] 根目录的 `plan.md` 和 `design.md`（被 docs/ 替代后）

---

## 四、迁移顺序（执行计划）

1. **数据层迁移**（独立可测）
   - v2 增加迁移脚本：从 MySQL 导出 books/ratings/users → 导入 PG
   - v2 增加 `pgvector` 扩展 + books.embedding 列
   - v2 embedding_service 接入 PG 的 embedding

2. **后端核心路由迁移**
   - auth → 用 v2 现有（更现代，JWT 完整）
   - books → 验证 v2 完整后保留
   - ratings → 验证 v2
   - recommend → 用 v1 真实算法替换 placeholder
   - reviews/social → 用 v1 完整版替换
   - 新增 ai.py

3. **前端迁移**
   - frontend-v2 改用 frontend 的 HomeView 玻璃态设计
   - frontend-v2 补全所有缺失页面（详情、搜索、登录、注册、AI 助手、对比、资料）
   - 接入 Pinia stores

4. **测试 & 验证**
   - pytest 端到端覆盖核心路由
   - 启动 uvicorn + frontend-v2 dev，浏览器走完 5 个核心场景

5. **清理**（仅 4 通过后）
   - 删除 v1 整个 backend/ 和 frontend/
   - 删除 v2 的 placeholder 代码
   - 删除 docs/_DEPRECATED.md 中标记的文件

---

## 五、风险与缓解

| 风险 | 影响 | 缓解 |
|------|------|------|
| v2 recommender 框架不完整 | 推荐功能可能跑不通 | 阶段 2 先把 v1 算法接线 + 单测，再继续 |
| MySQL→PG 数据迁移字段名差异 | 评分数据丢失 | 写两套 schema 对照表 + 抽样验证 |
| embedding 模型 v1 用 FAISS 文件 / v2 用 PG vector | 检索结果不一致 | 双索引并行跑一周比对 |
| 删 v1 后无 fallback | 测试出问题回不去 | 整库 git stash + 分支保护 |
