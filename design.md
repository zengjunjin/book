# 基于协同过滤与矩阵分解的校园二手书智能推荐系统 - 设计文档

## 一、项目概述

### 1.1 项目标题
《基于协同过滤与矩阵分解的校园二手书智能推荐系统实践报告》

### 1.2 项目目标
构建一个校园二手书智能推荐平台，基于Book-Crossing公开数据集，实现协同过滤（User-Based CF、Item-Based CF）与矩阵分解（SVD）两种推荐算法的对比实验，通过Vue 3前端与Flask后端提供完整的推荐服务系统。

### 1.3 核心功能
- 用户注册/登录系统
- 书籍浏览与详情查看
- 用户评分与收藏功能
- 基于协同过滤的个性化推荐
- 基于SVD矩阵分解的推荐
- 算法对比评估与可视化

---

## 二、系统架构

### 2.1 整体架构

```
┌─────────────────────────────────────────────────────────────┐
│                     前端层（Vue 3 + Vite）                    │
│   ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐ │
│   │  Vue Router │  │  Pinia状态  │  │   Axios API调用     │ │
│   │  页面路由   │  │  管理       │  │   与后端通信        │ │
│   └─────────────┘  └─────────────┘  └─────────────────────┘ │
│   ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐ │
│   │  首页/浏览   │  │  书籍详情   │  │   推荐结果页        │ │
│   │  书籍列表    │  │  评分/收藏  │  │   "为你推荐"        │ │
│   └─────────────┘  └─────────────┘  └─────────────────────┘ │
└──────────────────────────────┬──────────────────────────────┘
                               │ RESTful API
┌──────────────────────────────▼──────────────────────────────┐
│                     后端层（Flask API）                       │
│   ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐ │
│   │  用户API    │  │  书籍API    │  │   推荐引擎API       │ │
│   │  /api/users │  │  /api/books │  │   /api/recommend    │ │
│   └─────────────┘  └─────────────┘  └─────────────────────┘ │
│   ┌─────────────────────────────────────────────────────────┐│
│   │  推荐算法模块                                           ││
│   │  ├── 协同过滤（User-Based / Item-Based）               ││
│   │  ├── 矩阵分解（SVD - Surprise库）                      ││
│   │  └── 对比评估（RMSE、MAE、准确率、召回率）             ││
│   └─────────────────────────────────────────────────────────┘│
└──────────────────────────────┬──────────────────────────────┘
                               │
┌──────────────────────────────▼──────────────────────────────┐
│                     数据层（MySQL）                          │
│   ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐ │
│   │  users表    │  │  books表    │  │   ratings表         │ │
│   │  用户信息   │  │  书籍信息   │  │   评分记录          │ │
│   └─────────────┘  └─────────────┘  └─────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
```

### 2.2 技术栈

| 层级 | 技术 | 版本/说明 |
|------|------|----------|
| 前端框架 | Vue 3 | Composition API |
| 构建工具 | Vite | 快速开发 |
| 状态管理 | Pinia | 轻量状态管理 |
| UI组件 | 自定义CSS + Element Plus | 克制使用 |
| HTTP请求 | Axios | RESTful API通信 |
| 图表 | ECharts | 算法对比可视化 |
| 后端 | Flask | Python轻量框架 |
| ORM | SQLAlchemy | 数据库操作 |
| 数据库 | MySQL | 已安装部署 |
| 推荐算法 | NumPy + Scikit-learn + Surprise | CF + SVD |
| 数据集 | Book-Crossing | 公开数据集 |

---

## 三、数据库设计

### 3.1 数据表结构

#### users表（用户表）
| 字段 | 类型 | 说明 |
|------|------|------|
| id | INT PK AUTO_INCREMENT | 用户ID |
| username | VARCHAR(50) UNIQUE | 用户名 |
| password_hash | VARCHAR(255) | 密码哈希 |
| email | VARCHAR(100) | 邮箱 |
| created_at | TIMESTAMP | 注册时间 |

#### books表（书籍表）
| 字段 | 类型 | 说明 |
|------|------|------|
| id | INT PK AUTO_INCREMENT | 书籍ID |
| isbn | VARCHAR(20) UNIQUE | ISBN编号 |
| title | VARCHAR(255) | 书名 |
| author | VARCHAR(255) | 作者 |
| year | INT | 出版年份 |
| publisher | VARCHAR(255) | 出版社 |
| image_url | VARCHAR(500) | 封面图片URL |
| category | VARCHAR(100) | 分类 |

#### ratings表（评分表）
| 字段 | 类型 | 说明 |
|------|------|------|
| id | INT PK AUTO_INCREMENT | 评分ID |
| user_id | INT FK | 用户ID |
| book_id | INT FK | 书籍ID |
| rating | INT (1-10) | 评分 |
| created_at | TIMESTAMP | 评分时间 |

### 3.2 MySQL连接配置
```python
# Flask SQLAlchemy配置
SQLALCHEMY_DATABASE_URI = 'mysql+pymysql://username:password@localhost:3306/book_recommend'
SQLALCHEMY_TRACK_MODIFICATIONS = False
```

---

## 四、推荐算法设计

### 4.1 基于用户的协同过滤（User-Based CF）

**原理**：找到与目标用户兴趣相似的其他用户，推荐这些用户喜欢但目标用户未评分的书籍。

**步骤**：
1. 构建用户-物品评分矩阵 R (m×n)
2. 计算用户相似度：cosine_similarity(u_i, u_j)
3. 为每个用户找到Top-K近邻
4. 预测评分：r̂_ui = Σ(sim(u,u') × r_u'i) / Σ|sim(u,u')|
5. 取预测评分最高的Top-N本书推荐

**核心代码**：
```python
def user_based_cf(user_id, n_recommendations=10, k=20):
    # 1. 构建用户-物品矩阵
    user_item_matrix = build_rating_matrix()
    
    # 2. 计算用户相似度
    user_similarities = cosine_similarity(user_item_matrix)
    
    # 3. 找到Top-K相似用户
    similar_users = user_similarities[user_id].argsort()[-k:]
    
    # 4. 聚合评分预测
    predictions = aggregate_ratings(similar_users, user_similarities)
    
    # 5. 过滤已评分书籍，取Top-N
    recommendations = filter_and_rank(predictions, user_id, n_recommendations)
    return recommendations
```

### 4.2 基于物品的协同过滤（Item-Based CF）

**原理**：找到与用户已评分书籍相似的其他书籍进行推荐。

**步骤**：
1. 计算物品相似度矩阵
2. 对用户已评分的每本书，找到最相似的Top-K本书
3. 加权聚合，生成推荐列表

### 4.3 矩阵分解（SVD）

**原理**：将高维稀疏的用户-物品评分矩阵分解为低维的隐因子矩阵，捕捉用户和物品的潜在特征。

**数学模型**：R ≈ U × Σ × V^T
- U: 用户隐因子矩阵 (m×k)
- Σ: 奇异值对角矩阵 (k×k)
- V: 物品隐因子矩阵 (n×k)

**实现**：使用Surprise库的SVD算法
```python
from surprise import SVD, Dataset, Reader

svd = SVD(n_factors=50, n_epochs=20, lr_all=0.005, reg_all=0.02)
svd.fit(trainset)
predictions = svd.test(testset)
```

### 4.4 评估指标

| 指标 | 说明 | 用途 |
|------|------|------|
| RMSE | 均方根误差 | 衡量预测评分与实际评分的偏差 |
| MAE | 平均绝对误差 | 更直观的平均误差 |
| Precision@K | Top-K准确率 | 推荐列表中用户实际喜欢的比例 |
| Recall@K | Top-K召回率 | 用户喜欢的物品中被推荐的比例 |
| Coverage | 覆盖率 | 推荐系统能覆盖多少物品 |

---

## 五、前端页面设计

### 5.1 视觉主题
- **色调**：深灰底色(#1a1a2e) + 暖橙accent(#F97316) + 纯白文字
- **字体**：Inter（英文）+ 系统默认中文字体
- **布局**：侧边导航 + 主工作区，Linear风格克制美学

### 5.2 页面列表

| 页面 | 路由 | 功能 | 核心组件 |
|------|------|------|----------|
| 登录 | /login | 用户认证 | LoginForm |
| 注册 | /register | 用户注册 | RegisterForm |
| 首页 | / | 书籍广场 | BookGrid, SearchBar, CategoryFilter |
| 书籍详情 | /book/:id | 单本书信息 | BookDetail, StarRating, SimilarBooks |
| 为你推荐 | /recommend | 个性化推荐 | RecommendList, AlgorithmSelector |
| 算法对比 | /compare | 实验结果 | CompareChart, MetricTable |
| 个人中心 | /profile | 评分历史 | RatingHistory, UserStats |

### 5.3 关键交互
- 书籍卡片hover：轻微上浮 + 阴影加深
- 评分：五星点击动画
- 推荐结果：两种算法结果并排，带标签区分
- 图表：ECharts展示算法对比数据

---

## 六、API接口设计

### 6.1 用户相关
| 方法 | 路径 | 说明 |
|------|------|------|
| POST | /api/auth/register | 用户注册 |
| POST | /api/auth/login | 用户登录 |
| GET | /api/auth/me | 获取当前用户信息 |

### 6.2 书籍相关
| 方法 | 路径 | 说明 |
|------|------|------|
| GET | /api/books | 获取书籍列表（支持分页、搜索、筛选） |
| GET | /api/books/:id | 获取单本书详情 |
| GET | /api/books/:id/similar | 获取相似书籍 |

### 6.3 评分相关
| 方法 | 路径 | 说明 |
|------|------|------|
| POST | /api/ratings | 提交评分 |
| GET | /api/ratings/user | 获取当前用户评分历史 |

### 6.4 推荐相关
| 方法 | 路径 | 说明 |
|------|------|------|
| GET | /api/recommend/cf | 协同过滤推荐 |
| GET | /api/recommend/svd | SVD推荐 |
| GET | /api/recommend/compare | 算法对比评估结果 |

---

## 七、项目文件结构

```
campus-book-recommend/
├── backend/                    # Flask后端
│   ├── app.py                  # 主应用入口
│   ├── config.py               # 配置（含MySQL连接）
│   ├── models/                 # 数据模型
│   │   ├── __init__.py
│   │   ├── user.py
│   │   ├── book.py
│   │   └── rating.py
│   ├── routes/                 # API路由
│   │   ├── __init__.py
│   │   ├── auth.py
│   │   ├── books.py
│   │   ├── ratings.py
│   │   └── recommend.py
│   ├── services/               # 业务逻辑
│   │   ├── __init__.py
│   │   ├── cf_algorithm.py     # 协同过滤
│   │   ├── svd_algorithm.py    # SVD矩阵分解
│   │   └── evaluator.py        # 评估指标计算
│   ├── utils/
│   │   └── data_loader.py      # 数据加载预处理
│   ├── data/
│   │   ├── BX-Books.csv        # Book-Crossing书籍数据
│   │   ├── BX-Book-Ratings.csv # 评分数据
│   │   └── BX-Users.csv        # 用户数据
│   └── requirements.txt
│
├── frontend/                   # Vue 3前端
│   ├── index.html
│   ├── vite.config.js
│   ├── package.json
│   ├── src/
│   │   ├── main.js             # 入口
│   │   ├── App.vue             # 根组件
│   │   ├── router/             # 路由
│   │   │   └── index.js
│   │   ├── stores/             # Pinia状态
│   │   │   ├── user.js
│   │   │   └── book.js
│   │   ├── api/                # API封装
│   │   │   └── index.js
│   │   ├── views/              # 页面
│   │   │   ├── LoginView.vue
│   │   │   ├── RegisterView.vue
│   │   │   ├── HomeView.vue
│   │   │   ├── BookDetailView.vue
│   │   │   ├── RecommendView.vue
│   │   │   ├── CompareView.vue
│   │   │   └── ProfileView.vue
│   │   ├── components/         # 组件
│   │   │   ├── BookCard.vue
│   │   │   ├── StarRating.vue
│   │   │   ├── BookGrid.vue
│   │   │   ├── RecommendList.vue
│   │   │   ├── CompareChart.vue
│   │   │   └── AppSidebar.vue
│   │   └── assets/             # 静态资源
│   └── public/
│
└── README.md
```

---

## 八、实现计划

1. **环境搭建**：创建前后端项目结构，安装依赖
2. **数据库配置**：创建MySQL数据库和表结构
3. **数据准备**：下载Book-Crossing数据集，导入MySQL
4. **后端开发**：Flask API + 数据库模型 + 推荐算法实现
5. **前端开发**：Vue 3页面 + 组件 + API对接
6. **算法对比**：实现CF和SVD，计算评估指标
7. **联调测试**：前后端联调，端侧部署验证
8. **报告撰写**：按课程要求撰写完整报告

---

## 九、报告内容规划

| 报告章节 | 内容规划 |
|----------|----------|
| 标题 | 基于协同过滤与矩阵分解的校园二手书智能推荐系统实践报告 |
| 摘要 | 简述二手书交易痛点、协同过滤+SVD算法、实现步骤、对比结果 |
| 关键词 | 协同过滤；矩阵分解；推荐系统；Vue 3；Flask |
| 背景与目标 | 校园二手书信息过载、推荐系统解决匹配效率问题 |
| 技术与工具 | Python、Flask、Vue 3、MySQL、Surprise、NumPy |
| 算法设计与实现 | 协同过滤原理+公式、SVD分解原理、核心代码片段 |
| 测试结果 | RMSE/MAE对比、准确率/召回率图表、训练时间 |
| 问题与改进 | 冷启动问题、稀疏矩阵、未来可用深度学习改进 |
| 总结 | 从数据到推荐系统的完整流程收获 |
| 参考文献 | 至少5篇，包含推荐系统经典论文和框架文档 |
