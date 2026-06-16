# 校园二手书智能推荐系统

基于协同过滤与SVD矩阵分解的图书推荐系统，包含Vue 3前端、Flask后端和MySQL数据库。

## 技术栈

- **前端**：Vue 3 + Vite + Pinia + Element Plus + ECharts
- **后端**：Flask + SQLAlchemy + MySQL
- **算法**：协同过滤（User-Based / Item-Based）+ SVD矩阵分解（Surprise库）
- **数据集**：Book-Crossing公开数据集

## 快速开始

### 1. 克隆项目

```bash
cd book
```

### 2. 配置MySQL数据库

启动MySQL服务后，创建数据库：

```bash
mysql -u root -p -e "CREATE DATABASE IF NOT EXISTS book_recommend CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"
```

修改 `backend/config.py` 中的数据库连接信息（用户名、密码）。

### 3. 启动后端

```bash
cd backend
pip install -r requirements.txt
python import_data.py  # 导入数据集（首次运行需要，会自动下载数据）
python app.py
```

后端服务将在 http://localhost:5000 启动

### 4. 启动前端

```bash
cd frontend
npm install
npm run dev
```

前端开发服务器将在 http://localhost:5173 启动

### 5. 访问应用

打开浏览器访问 http://localhost:5173

1. 注册一个新账号
2. 浏览书籍列表
3. 对感兴趣的书籍进行评分
4. 查看「为你推荐」页面获取个性化推荐
5. 查看「算法对比」页面了解两种算法的性能对比

## 项目结构

```
book/
├── backend/              # Flask后端
│   ├── app.py           # 应用入口
│   ├── config.py        # 配置文件
│   ├── import_data.py   # 数据导入脚本
│   ├── models/          # 数据模型
│   ├── routes/          # API路由
│   ├── services/        # 业务逻辑与算法
│   ├── utils/           # 工具函数
│   └── data/            # 数据集文件
├── frontend/            # Vue 3前端
│   ├── src/
│   │   ├── components/  # 组件
│   │   ├── views/       # 页面视图
│   │   ├── api/         # API封装
│   │   ├── stores/      # Pinia状态
│   │   └── router/      # 路由
│   └── package.json
├── design.md            # 设计文档
├── plan.md              # 计划文档
└── README.md
```

## 算法对比

系统实现了两种推荐算法：

1. **协同过滤（Collaborative Filtering）**
   - 基于用户的协同过滤（User-Based）
   - 基于物品的协同过滤（Item-Based）
   - 使用余弦相似度计算

2. **SVD矩阵分解**
   - 使用Surprise库实现
   - 将高维稀疏评分矩阵分解为低维隐因子矩阵

评估指标：RMSE（均方根误差）、MAE（平均绝对误差）

## 功能特性

- 用户注册/登录
- 书籍浏览与搜索
- 用户评分功能
- 两种算法的个性化推荐
- 算法性能对比可视化
- 评分历史记录与个人中心

## 许可证

MIT License
