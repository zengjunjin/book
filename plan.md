# 校园二手书智能推荐系统 - 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 构建基于协同过滤与SVD矩阵分解的校园二手书智能推荐系统，包含Vue 3前端、Flask后端、MySQL数据库，实现算法对比实验。

**Architecture:** 前后端分离架构。前端Vue 3 + Vite提供用户界面，后端Flask提供RESTful API，MySQL存储数据。推荐算法在Python中实现，包含User-Based CF、Item-Based CF和SVD三种方法。

**Tech Stack:** Vue 3, Vite, Pinia, Axios, Element Plus, ECharts, Flask, SQLAlchemy, MySQL, NumPy, Scikit-learn, Surprise

---

## 文件结构

```
campus-book-recommend/
├── backend/
│   ├── app.py
│   ├── config.py
│   ├── models/
│   │   ├── __init__.py
│   │   ├── user.py
│   │   ├── book.py
│   │   └── rating.py
│   ├── routes/
│   │   ├── __init__.py
│   │   ├── auth.py
│   │   ├── books.py
│   │   ├── ratings.py
│   │   └── recommend.py
│   ├── services/
│   │   ├── __init__.py
│   │   ├── cf_algorithm.py
│   │   ├── svd_algorithm.py
│   │   └── evaluator.py
│   ├── utils/
│   │   └── data_loader.py
│   ├── data/
│   │   ├── BX-Books.csv
│   │   ├── BX-Book-Ratings.csv
│   │   └── BX-Users.csv
│   └── requirements.txt
├── frontend/
│   ├── index.html
│   ├── vite.config.js
│   ├── package.json
│   ├── src/
│   │   ├── main.js
│   │   ├── App.vue
│   │   ├── router/
│   │   │   └── index.js
│   │   ├── stores/
│   │   │   ├── user.js
│   │   │   └── book.js
│   │   ├── api/
│   │   │   └── index.js
│   │   ├── views/
│   │   │   ├── LoginView.vue
│   │   │   ├── RegisterView.vue
│   │   │   ├── HomeView.vue
│   │   │   ├── BookDetailView.vue
│   │   │   ├── RecommendView.vue
│   │   │   ├── CompareView.vue
│   │   │   └── ProfileView.vue
│   │   ├── components/
│   │   │   ├── BookCard.vue
│   │   │   ├── StarRating.vue
│   │   │   ├── BookGrid.vue
│   │   │   ├── RecommendList.vue
│   │   │   ├── CompareChart.vue
│   │   │   └── AppSidebar.vue
│   │   └── assets/
│   └── public/
└── README.md
```

---

## Task 1: 后端环境搭建与项目初始化

**Files:**
- Create: `backend/requirements.txt`
- Create: `backend/config.py`
- Create: `backend/app.py`

- [ ] **Step 1: 创建requirements.txt**

```txt
flask==3.0.0
flask-sqlalchemy==3.1.1
flask-cors==4.0.0
pymysql==1.1.0
cryptography==41.0.7
numpy==1.26.2
pandas==2.1.4
scikit-learn==1.3.2
scikit-surprise==1.1.3
werkzeug==3.0.1
```

- [ ] **Step 2: 创建config.py**

```python
import os

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key-change-in-production'
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or 'mysql+pymysql://root:password@localhost:3306/book_recommend?charset=utf8mb4'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    CORS_ORIGINS = ['http://localhost:5173', 'http://127.0.0.1:5173']
```

- [ ] **Step 3: 创建app.py主应用**

```python
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS
from config import Config

db = SQLAlchemy()

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)
    
    db.init_app(app)
    CORS(app, origins=Config.CORS_ORIGINS)
    
    from routes.auth import auth_bp
    from routes.books import books_bp
    from routes.ratings import ratings_bp
    from routes.recommend import recommend_bp
    
    app.register_blueprint(auth_bp, url_prefix='/api/auth')
    app.register_blueprint(books_bp, url_prefix='/api/books')
    app.register_blueprint(ratings_bp, url_prefix='/api/ratings')
    app.register_blueprint(recommend_bp, url_prefix='/api/recommend')
    
    @app.route('/api/health')
    def health_check():
        return {'status': 'ok'}
    
    return app

if __name__ == '__main__':
    app = create_app()
    with app.app_context():
        db.create_all()
    app.run(debug=True, port=5000)
```

- [ ] **Step 4: 安装依赖**

Run: `cd backend && pip install -r requirements.txt`
Expected: 所有依赖安装成功

- [ ] **Step 5: 创建MySQL数据库**

Run: `mysql -u root -p -e "CREATE DATABASE IF NOT EXISTS book_recommend CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"`
Expected: 数据库创建成功

- [ ] **Step 6: Commit**

```bash
git add backend/
git commit -m "feat: initialize backend project with Flask and MySQL"
```

---

## Task 2: 数据库模型定义

**Files:**
- Create: `backend/models/__init__.py`
- Create: `backend/models/user.py`
- Create: `backend/models/book.py`
- Create: `backend/models/rating.py`

- [ ] **Step 1: 创建models/__init__.py**

```python
from app import db
from .user import User
from .book import Book
from .rating import Rating

__all__ = ['User', 'Book', 'Rating', 'db']
```

- [ ] **Step 2: 创建user.py**

```python
from app import db
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime

class User(db.Model):
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    email = db.Column(db.String(100))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    ratings = db.relationship('Rating', backref='user', lazy=True)
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
    
    def to_dict(self):
        return {
            'id': self.id,
            'username': self.username,
            'email': self.email,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
```

- [ ] **Step 3: 创建book.py**

```python
from app import db

class Book(db.Model):
    __tablename__ = 'books'
    
    id = db.Column(db.Integer, primary_key=True)
    isbn = db.Column(db.String(20), unique=True, nullable=False)
    title = db.Column(db.String(255), nullable=False)
    author = db.Column(db.String(255))
    year = db.Column(db.Integer)
    publisher = db.Column(db.String(255))
    image_url = db.Column(db.String(500))
    category = db.Column(db.String(100))
    
    ratings = db.relationship('Rating', backref='book', lazy=True)
    
    def to_dict(self):
        return {
            'id': self.id,
            'isbn': self.isbn,
            'title': self.title,
            'author': self.author,
            'year': self.year,
            'publisher': self.publisher,
            'image_url': self.image_url,
            'category': self.category
        }
```

- [ ] **Step 4: 创建rating.py**

```python
from app import db
from datetime import datetime

class Rating(db.Model):
    __tablename__ = 'ratings'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    book_id = db.Column(db.Integer, db.ForeignKey('books.id'), nullable=False)
    rating = db.Column(db.Integer, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'book_id': self.book_id,
            'rating': self.rating,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
```

- [ ] **Step 5: 更新app.py导入模型**

Modify: `backend/app.py`

在`db.init_app(app)`之后添加：
```python
    from models import User, Book, Rating
```

- [ ] **Step 6: 测试数据库连接**

Run: `cd backend && python -c "from app import create_app, db; app = create_app(); app.app_context().push(); db.create_all(); print('Database tables created successfully')"`
Expected: 输出"Database tables created successfully"

- [ ] **Step 7: Commit**

```bash
git add backend/
git commit -m "feat: add database models for User, Book, Rating"
```

---

## Task 3: 认证API路由

**Files:**
- Create: `backend/routes/__init__.py`
- Create: `backend/routes/auth.py`

- [ ] **Step 1: 创建routes/__init__.py**

```python
# Routes package
```

- [ ] **Step 2: 创建auth.py**

```python
from flask import Blueprint, request, jsonify
from models import db, User

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/register', methods=['POST'])
def register():
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')
    email = data.get('email')
    
    if not username or not password:
        return jsonify({'error': 'Username and password are required'}), 400
    
    if User.query.filter_by(username=username).first():
        return jsonify({'error': 'Username already exists'}), 409
    
    user = User(username=username, email=email)
    user.set_password(password)
    db.session.add(user)
    db.session.commit()
    
    return jsonify({'message': 'User registered successfully', 'user': user.to_dict()}), 201

@auth_bp.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')
    
    user = User.query.filter_by(username=username).first()
    if not user or not user.check_password(password):
        return jsonify({'error': 'Invalid username or password'}), 401
    
    return jsonify({'message': 'Login successful', 'user': user.to_dict()}), 200

@auth_bp.route('/me', methods=['GET'])
def get_current_user():
    # 简化版，实际应使用JWT token
    user_id = request.args.get('user_id')
    if not user_id:
        return jsonify({'error': 'User ID required'}), 400
    
    user = User.query.get(user_id)
    if not user:
        return jsonify({'error': 'User not found'}), 404
    
    return jsonify({'user': user.to_dict()}), 200
```

- [ ] **Step 3: 测试注册API**

Run: `curl -X POST http://localhost:5000/api/auth/register -H "Content-Type: application/json" -d '{"username":"testuser","password":"testpass","email":"test@example.com"}'`
Expected: 返回注册成功信息和用户数据

- [ ] **Step 4: 测试登录API**

Run: `curl -X POST http://localhost:5000/api/auth/login -H "Content-Type: application/json" -d '{"username":"testuser","password":"testpass"}'`
Expected: 返回登录成功信息和用户数据

- [ ] **Step 5: Commit**

```bash
git add backend/routes/auth.py
git commit -m "feat: add authentication API routes"
```

---

## Task 4: 书籍API路由

**Files:**
- Create: `backend/routes/books.py`

- [ ] **Step 1: 创建books.py**

```python
from flask import Blueprint, request, jsonify
from models import Book

books_bp = Blueprint('books', __name__)

@books_bp.route('/', methods=['GET'])
def get_books():
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    search = request.args.get('search', '')
    category = request.args.get('category', '')
    
    query = Book.query
    
    if search:
        query = query.filter(
            db.or_(
                Book.title.contains(search),
                Book.author.contains(search)
            )
        )
    
    if category:
        query = query.filter(Book.category == category)
    
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    books = [book.to_dict() for book in pagination.items]
    
    return jsonify({
        'books': books,
        'total': pagination.total,
        'pages': pagination.pages,
        'current_page': page
    }), 200

@books_bp.route('/<int:book_id>', methods=['GET'])
def get_book(book_id):
    book = Book.query.get(book_id)
    if not book:
        return jsonify({'error': 'Book not found'}), 404
    return jsonify({'book': book.to_dict()}), 200

@books_bp.route('/<int:book_id>/similar', methods=['GET'])
def get_similar_books(book_id):
    book = Book.query.get(book_id)
    if not book:
        return jsonify({'error': 'Book not found'}), 404
    
    # 简单相似度：同作者或同分类
    similar = Book.query.filter(
        db.and_(
            Book.id != book_id,
            db.or_(
                Book.author == book.author,
                Book.category == book.category
            )
        )
    ).limit(5).all()
    
    return jsonify({'similar_books': [b.to_dict() for b in similar]}), 200
```

- [ ] **Step 2: Commit**

```bash
git add backend/routes/books.py
git commit -m "feat: add book API routes with search and pagination"
```

---

## Task 5: 评分API路由

**Files:**
- Create: `backend/routes/ratings.py`

- [ ] **Step 1: 创建ratings.py**

```python
from flask import Blueprint, request, jsonify
from models import db, Rating, Book

ratings_bp = Blueprint('ratings', __name__)

@ratings_bp.route('/', methods=['POST'])
def create_rating():
    data = request.get_json()
    user_id = data.get('user_id')
    book_id = data.get('book_id')
    rating_value = data.get('rating')
    
    if not all([user_id, book_id, rating_value]):
        return jsonify({'error': 'Missing required fields'}), 400
    
    if not (1 <= rating_value <= 10):
        return jsonify({'error': 'Rating must be between 1 and 10'}), 400
    
    # 检查是否已评分
    existing = Rating.query.filter_by(user_id=user_id, book_id=book_id).first()
    if existing:
        existing.rating = rating_value
        db.session.commit()
        return jsonify({'message': 'Rating updated', 'rating': existing.to_dict()}), 200
    
    rating = Rating(user_id=user_id, book_id=book_id, rating=rating_value)
    db.session.add(rating)
    db.session.commit()
    
    return jsonify({'message': 'Rating created', 'rating': rating.to_dict()}), 201

@ratings_bp.route('/user', methods=['GET'])
def get_user_ratings():
    user_id = request.args.get('user_id', type=int)
    if not user_id:
        return jsonify({'error': 'User ID required'}), 400
    
    ratings = Rating.query.filter_by(user_id=user_id).all()
    result = []
    for r in ratings:
        book = Book.query.get(r.book_id)
        rating_dict = r.to_dict()
        rating_dict['book'] = book.to_dict() if book else None
        result.append(rating_dict)
    
    return jsonify({'ratings': result}), 200
```

- [ ] **Step 2: Commit**

```bash
git add backend/routes/ratings.py
git commit -m "feat: add rating API routes"
```

---

## Task 6: 数据加载与预处理

**Files:**
- Create: `backend/utils/__init__.py`
- Create: `backend/utils/data_loader.py`

- [ ] **Step 1: 创建utils/__init__.py**

```python
# Utils package
```

- [ ] **Step 2: 创建data_loader.py**

```python
import pandas as pd
import numpy as np
from models import db, Book, Rating

def load_book_crossing_data(books_path, ratings_path, users_path=None):
    """加载Book-Crossing数据集并导入数据库"""
    
    # 加载书籍数据
    books_df = pd.read_csv(books_path, sep=';', encoding='latin-1', on_bad_lines='skip')
    books_df.columns = ['isbn', 'title', 'author', 'year', 'publisher', 
                        'image_url_s', 'image_url_m', 'image_url_l']
    
    # 加载评分数据
    ratings_df = pd.read_csv(ratings_path, sep=';', encoding='latin-1')
    ratings_df.columns = ['user_id', 'isbn', 'rating']
    
    # 清洗数据
    ratings_df = ratings_df[ratings_df['rating'] > 0]  # 只保留显性评分
    
    return books_df, ratings_df

def import_books_to_db(books_df):
    """将书籍数据导入数据库"""
    for _, row in books_df.iterrows():
        # 检查是否已存在
        existing = Book.query.filter_by(isbn=row['isbn']).first()
        if existing:
            continue
        
        try:
            year = int(row['year']) if pd.notna(row['year']) and str(row['year']).isdigit() else None
        except:
            year = None
        
        book = Book(
            isbn=row['isbn'],
            title=row['title'],
            author=row['author'],
            year=year,
            publisher=row['publisher'],
            image_url=row['image_url_l'] if pd.notna(row['image_url_l']) else None
        )
        db.session.add(book)
    
    db.session.commit()
    print(f"Imported {Book.query.count()} books")

def import_ratings_to_db(ratings_df):
    """将评分数据导入数据库"""
    # 获取所有有效的ISBN到book_id的映射
    books = Book.query.all()
    isbn_to_id = {b.isbn: b.id for b in books}
    
    # 只导入有对应书籍的评分
    valid_ratings = ratings_df[ratings_df['isbn'].isin(isbn_to_id.keys())]
    
    # 限制数据量以提高性能
    valid_ratings = valid_ratings.head(50000)
    
    for _, row in valid_ratings.iterrows():
        book_id = isbn_to_id.get(row['isbn'])
        if not book_id:
            continue
        
        # 创建系统用户（如果不存在）
        from models import User
        user = User.query.filter_by(id=row['user_id']).first()
        if not user:
            user = User(id=row['user_id'], username=f"user_{row['user_id']}", email=None)
            user.set_password('default_password')
            db.session.add(user)
        
        # 检查是否已存在评分
        existing = Rating.query.filter_by(
            user_id=row['user_id'], 
            book_id=book_id
        ).first()
        if existing:
            continue
        
        rating = Rating(
            user_id=row['user_id'],
            book_id=book_id,
            rating=row['rating']
        )
        db.session.add(rating)
    
    db.session.commit()
    print(f"Imported {Rating.query.count()} ratings")

def prepare_rating_matrix():
    """准备用户-物品评分矩阵"""
    ratings = Rating.query.all()
    
    data = []
    for r in ratings:
        data.append({
            'user_id': r.user_id,
            'book_id': r.book_id,
            'rating': r.rating
        })
    
    df = pd.DataFrame(data)
    
    # 创建用户和书籍的ID映射
    user_ids = df['user_id'].unique()
    book_ids = df['book_id'].unique()
    
    user_id_map = {uid: i for i, uid in enumerate(user_ids)}
    book_id_map = {bid: i for i, bid in enumerate(book_ids)}
    
    # 构建评分矩阵
    n_users = len(user_ids)
    n_books = len(book_ids)
    rating_matrix = np.zeros((n_users, n_books))
    
    for _, row in df.iterrows():
        u_idx = user_id_map[row['user_id']]
        b_idx = book_id_map[row['book_id']]
        rating_matrix[u_idx, b_idx] = row['rating']
    
    return rating_matrix, user_id_map, book_id_map, df
```

- [ ] **Step 3: Commit**

```bash
git add backend/utils/data_loader.py
git commit -m "feat: add data loading and preprocessing utilities"
```

---

## Task 7: 协同过滤算法实现

**Files:**
- Create: `backend/services/__init__.py`
- Create: `backend/services/cf_algorithm.py`

- [ ] **Step 1: 创建services/__init__.py**

```python
# Services package
```

- [ ] **Step 2: 创建cf_algorithm.py**

```python
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity
from utils.data_loader import prepare_rating_matrix

class CollaborativeFiltering:
    def __init__(self):
        self.rating_matrix = None
        self.user_id_map = None
        self.book_id_map = None
        self.reverse_user_map = None
        self.reverse_book_map = None
        self.user_similarity = None
        self.item_similarity = None
        self.df = None
        self._load_data()
    
    def _load_data(self):
        """加载评分数据"""
        self.rating_matrix, self.user_id_map, self.book_id_map, self.df = prepare_rating_matrix()
        self.reverse_user_map = {v: k for k, v in self.user_id_map.items()}
        self.reverse_book_map = {v: k for k, v in self.book_id_map.items()}
        
        # 预计算相似度矩阵
        self.user_similarity = cosine_similarity(self.rating_matrix)
        self.item_similarity = cosine_similarity(self.rating_matrix.T)
    
    def user_based_recommend(self, user_id, n_recommendations=10, k=20):
        """基于用户的协同过滤推荐"""
        if user_id not in self.user_id_map:
            return []
        
        user_idx = self.user_id_map[user_id]
        user_ratings = self.rating_matrix[user_idx]
        
        # 找到Top-K相似用户
        similarities = self.user_similarity[user_idx]
        similar_indices = np.argsort(similarities)[::-1][1:k+1]  # 排除自己
        
        # 预测评分
        predictions = np.zeros(self.rating_matrix.shape[1])
        sim_sums = np.zeros(self.rating_matrix.shape[1])
        
        for sim_idx in similar_indices:
            sim = similarities[sim_idx]
            if sim <= 0:
                continue
            sim_user_ratings = self.rating_matrix[sim_idx]
            predictions += sim * sim_user_ratings
            sim_sums += sim * (sim_user_ratings > 0)
        
        # 避免除零
        with np.errstate(divide='ignore', invalid='ignore'):
            predictions = np.divide(predictions, sim_sums, 
                                   out=np.zeros_like(predictions), where=sim_sums!=0)
        
        # 过滤已评分书籍
        unrated_mask = user_ratings == 0
        predictions = predictions * unrated_mask
        
        # 取Top-N
        top_indices = np.argsort(predictions)[::-1][:n_recommendations]
        
        recommendations = []
        for idx in top_indices:
            if predictions[idx] > 0:
                book_id = self.reverse_book_map[idx]
                recommendations.append({
                    'book_id': book_id,
                    'predicted_rating': float(predictions[idx])
                })
        
        return recommendations
    
    def item_based_recommend(self, user_id, n_recommendations=10, k=20):
        """基于物品的协同过滤推荐"""
        if user_id not in self.user_id_map:
            return []
        
        user_idx = self.user_id_map[user_id]
        user_ratings = self.rating_matrix[user_idx]
        rated_items = np.where(user_ratings > 0)[0]
        
        if len(rated_items) == 0:
            return []
        
        # 预测评分
        predictions = np.zeros(self.rating_matrix.shape[1])
        sim_sums = np.zeros(self.rating_matrix.shape[1])
        
        for item_idx in rated_items:
            item_rating = user_ratings[item_idx]
            similarities = self.item_similarity[item_idx]
            
            # 取Top-K相似物品
            similar_indices = np.argsort(similarities)[::-1][1:k+1]
            
            for sim_idx in similar_indices:
                sim = similarities[sim_idx]
                if sim <= 0:
                    continue
                predictions[sim_idx] += sim * item_rating
                sim_sums[sim_idx] += sim
        
        with np.errstate(divide='ignore', invalid='ignore'):
            predictions = np.divide(predictions, sim_sums,
                                   out=np.zeros_like(predictions), where=sim_sums!=0)
        
        # 过滤已评分
        unrated_mask = user_ratings == 0
        predictions = predictions * unrated_mask
        
        top_indices = np.argsort(predictions)[::-1][:n_recommendations]
        
        recommendations = []
        for idx in top_indices:
            if predictions[idx] > 0:
                book_id = self.reverse_book_map[idx]
                recommendations.append({
                    'book_id': book_id,
                    'predicted_rating': float(predictions[idx])
                })
        
        return recommendations
```

- [ ] **Step 3: Commit**

```bash
git add backend/services/cf_algorithm.py
git commit -m "feat: implement user-based and item-based collaborative filtering"
```

---

## Task 8: SVD矩阵分解算法实现

**Files:**
- Create: `backend/services/svd_algorithm.py`

- [ ] **Step 1: 创建svd_algorithm.py**

```python
from surprise import SVD, Dataset, Reader, accuracy
from surprise.model_selection import train_test_split
import pandas as pd
from utils.data_loader import prepare_rating_matrix

class SVDRecommendation:
    def __init__(self):
        self.model = None
        self.trainset = None
        self.testset = None
        self.df = None
        self.user_id_map = None
        self.book_id_map = None
        self._load_data()
    
    def _load_data(self):
        """加载数据并训练SVD模型"""
        _, self.user_id_map, self.book_id_map, self.df = prepare_rating_matrix()
        
        if self.df.empty:
            return
        
        # 转换为Surprise格式
        reader = Reader(rating_scale=(1, 10))
        data = Dataset.load_from_df(self.df[['user_id', 'book_id', 'rating']], reader)
        
        # 划分训练集和测试集
        self.trainset, self.testset = train_test_split(data, test_size=0.2, random_state=42)
        
        # 训练SVD模型
        self.model = SVD(n_factors=50, n_epochs=20, lr_all=0.005, reg_all=0.02, random_state=42)
        self.model.fit(self.trainset)
    
    def recommend(self, user_id, n_recommendations=10):
        """为指定用户生成推荐"""
        if self.model is None or user_id not in self.user_id_map:
            return []
        
        # 获取用户已评分的书籍
        user_ratings = self.df[self.df['user_id'] == user_id]
        rated_books = set(user_ratings['book_id'].tolist())
        
        # 获取所有书籍
        all_books = set(self.df['book_id'].unique())
        unrated_books = all_books - rated_books
        
        # 预测未评分书籍的评分
        predictions = []
        for book_id in list(unrated_books)[:500]:  # 限制计算量
            pred = self.model.predict(user_id, book_id)
            predictions.append({
                'book_id': book_id,
                'predicted_rating': pred.est
            })
        
        # 按预测评分排序
        predictions.sort(key=lambda x: x['predicted_rating'], reverse=True)
        return predictions[:n_recommendations]
    
    def evaluate(self):
        """评估模型性能"""
        if self.model is None:
            return {}
        
        predictions = self.model.test(self.testset)
        
        return {
            'rmse': accuracy.rmse(predictions, verbose=False),
            'mae': accuracy.mae(predictions, verbose=False)
        }
```

- [ ] **Step 2: Commit**

```bash
git add backend/services/svd_algorithm.py
git commit -m "feat: implement SVD matrix factorization recommendation"
```

---

## Task 9: 评估器与推荐API

**Files:**
- Create: `backend/services/evaluator.py`
- Create: `backend/routes/recommend.py`

- [ ] **Step 1: 创建evaluator.py**

```python
import numpy as np
from sklearn.metrics import mean_squared_error, mean_absolute_error
from services.cf_algorithm import CollaborativeFiltering
from services.svd_algorithm import SVDRecommendation

class Evaluator:
    def __init__(self):
        self.cf = CollaborativeFiltering()
        self.svd = SVDRecommendation()
    
    def evaluate_cf(self, test_size=0.2):
        """评估协同过滤算法"""
        # 简单评估：随机划分测试集
        df = self.cf.df
        if df.empty:
            return {}
        
        # 随机采样部分数据作为测试集
        test_df = df.sample(frac=test_size, random_state=42)
        
        rmse_list = []
        mae_list = []
        
        for _, row in test_df.head(1000).iterrows():  # 限制评估样本数
            user_id = row['user_id']
            book_id = row['book_id']
            actual_rating = row['rating']
            
            # 获取推荐
            recs = self.cf.user_based_recommend(user_id, n_recommendations=50)
            
            # 查找预测评分
            pred_rating = None
            for rec in recs:
                if rec['book_id'] == book_id:
                    pred_rating = rec['predicted_rating']
                    break
            
            if pred_rating is not None:
                rmse_list.append((actual_rating - pred_rating) ** 2)
                mae_list.append(abs(actual_rating - pred_rating))
        
        if not rmse_list:
            return {'rmse': None, 'mae': None}
        
        return {
            'rmse': np.sqrt(np.mean(rmse_list)),
            'mae': np.mean(mae_list)
        }
    
    def compare_algorithms(self):
        """对比所有算法"""
        cf_results = self.evaluate_cf()
        svd_results = self.svd.evaluate()
        
        return {
            'collaborative_filtering': cf_results,
            'svd': svd_results,
            'comparison': {
                'rmse': {
                    'cf': cf_results.get('rmse'),
                    'svd': svd_results.get('rmse')
                },
                'mae': {
                    'cf': cf_results.get('mae'),
                    'svd': svd_results.get('mae')
                }
            }
        }
```

- [ ] **Step 2: 创建recommend.py**

```python
from flask import Blueprint, request, jsonify
from models import Book
from services.cf_algorithm import CollaborativeFiltering
from services.svd_algorithm import SVDRecommendation
from services.evaluator import Evaluator

recommend_bp = Blueprint('recommend', __name__)
cf_engine = CollaborativeFiltering()
svd_engine = SVDRecommendation()
evaluator = Evaluator()

@recommend_bp.route('/cf', methods=['GET'])
def cf_recommend():
    user_id = request.args.get('user_id', type=int)
    n = request.args.get('n', 10, type=int)
    
    if not user_id:
        return jsonify({'error': 'User ID required'}), 400
    
    recommendations = cf_engine.user_based_recommend(user_id, n_recommendations=n)
    
    # 获取书籍详情
    result = []
    for rec in recommendations:
        book = Book.query.get(rec['book_id'])
        if book:
            book_dict = book.to_dict()
            book_dict['predicted_rating'] = rec['predicted_rating']
            result.append(book_dict)
    
    return jsonify({'recommendations': result, 'algorithm': 'User-Based CF'}), 200

@recommend_bp.route('/svd', methods=['GET'])
def svd_recommend():
    user_id = request.args.get('user_id', type=int)
    n = request.args.get('n', 10, type=int)
    
    if not user_id:
        return jsonify({'error': 'User ID required'}), 400
    
    recommendations = svd_engine.recommend(user_id, n_recommendations=n)
    
    result = []
    for rec in recommendations:
        book = Book.query.get(rec['book_id'])
        if book:
            book_dict = book.to_dict()
            book_dict['predicted_rating'] = rec['predicted_rating']
            result.append(book_dict)
    
    return jsonify({'recommendations': result, 'algorithm': 'SVD'}), 200

@recommend_bp.route('/compare', methods=['GET'])
def compare_algorithms():
    results = evaluator.compare_algorithms()
    return jsonify(results), 200
```

- [ ] **Step 3: Commit**

```bash
git add backend/services/evaluator.py backend/routes/recommend.py
git commit -m "feat: add recommendation API and algorithm evaluation"
```

---

## Task 10: 数据导入脚本

**Files:**
- Create: `backend/import_data.py`

- [ ] **Step 1: 创建import_data.py**

```python
import os
import urllib.request
import zipfile
from app import create_app, db
from utils.data_loader import load_book_crossing_data, import_books_to_db, import_ratings_to_db

def download_dataset():
    """下载Book-Crossing数据集"""
    data_dir = 'data'
    os.makedirs(data_dir, exist_ok=True)
    
    # 数据集文件路径
    books_path = os.path.join(data_dir, 'BX-Books.csv')
    ratings_path = os.path.join(data_dir, 'BX-Book-Ratings.csv')
    users_path = os.path.join(data_dir, 'BX-Users.csv')
    
    # 如果文件已存在，直接返回
    if os.path.exists(books_path) and os.path.exists(ratings_path):
        print("Dataset already exists")
        return books_path, ratings_path, users_path
    
    # 下载数据集
    url = "http://www2.informatik.uni-freiburg.de/~cziegler/BX/BX-CSV-Dump.zip"
    zip_path = os.path.join(data_dir, 'BX-CSV-Dump.zip')
    
    print("Downloading Book-Crossing dataset...")
    try:
        urllib.request.urlretrieve(url, zip_path)
        
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(data_dir)
        
        os.remove(zip_path)
        print("Dataset downloaded and extracted")
    except Exception as e:
        print(f"Error downloading dataset: {e}")
        print("Please download manually from: http://www2.informatik.uni-freiburg.de/~cziegler/BX/")
    
    return books_path, ratings_path, users_path

def main():
    app = create_app()
    
    with app.app_context():
        # 创建表
        db.create_all()
        print("Database tables created")
        
        # 下载数据集
        books_path, ratings_path, users_path = download_dataset()
        
        # 检查文件是否存在
        if not os.path.exists(books_path) or not os.path.exists(ratings_path):
            print("Dataset files not found. Please check the data directory.")
            return
        
        # 加载数据
        print("Loading dataset...")
        books_df, ratings_df = load_book_crossing_data(books_path, ratings_path, users_path)
        
        # 导入数据库
        print("Importing books...")
        import_books_to_db(books_df)
        
        print("Importing ratings...")
        import_ratings_to_db(ratings_df)
        
        print("Data import completed!")

if __name__ == '__main__':
    main()
```

- [ ] **Step 2: Commit**

```bash
git add backend/import_data.py
git commit -m "feat: add data import script for Book-Crossing dataset"
```

---

## Task 11: 前端项目初始化

**Files:**
- Create: `frontend/package.json`
- Create: `frontend/vite.config.js`
- Create: `frontend/index.html`
- Create: `frontend/src/main.js`

- [ ] **Step 1: 创建package.json**

```json
{
  "name": "book-recommend-frontend",
  "private": true,
  "version": "0.0.0",
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "vite build",
    "preview": "vite preview"
  },
  "dependencies": {
    "vue": "^3.4.0",
    "vue-router": "^4.2.5",
    "pinia": "^2.1.7",
    "axios": "^1.6.2",
    "element-plus": "^2.5.0",
    "echarts": "^5.4.3",
    "vue-echarts": "^6.6.8"
  },
  "devDependencies": {
    "@vitejs/plugin-vue": "^5.0.0",
    "vite": "^5.0.0"
  }
}
```

- [ ] **Step 2: 创建vite.config.js**

```javascript
import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://localhost:5000',
        changeOrigin: true
      }
    }
  }
})
```

- [ ] **Step 3: 创建index.html**

```html
<!DOCTYPE html>
<html lang="zh-CN">
  <head>
    <meta charset="UTF-8" />
    <link rel="icon" type="image/svg+xml" href="/vite.svg" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>校园二手书智能推荐系统</title>
  </head>
  <body>
    <div id="app"></div>
    <script type="module" src="/src/main.js"></script>
  </body>
</html>
```

- [ ] **Step 4: 创建src/main.js**

```javascript
import { createApp } from 'vue'
import { createPinia } from 'pinia'
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'
import App from './App.vue'
import router from './router'

const app = createApp(App)

app.use(createPinia())
app.use(router)
app.use(ElementPlus)

app.mount('#app')
```

- [ ] **Step 5: 安装前端依赖**

Run: `cd frontend && npm install`
Expected: 所有依赖安装成功

- [ ] **Step 6: Commit**

```bash
git add frontend/
git commit -m "feat: initialize Vue 3 frontend project"
```

---

## Task 12: 前端路由与状态管理

**Files:**
- Create: `frontend/src/router/index.js`
- Create: `frontend/src/stores/user.js`
- Create: `frontend/src/stores/book.js`

- [ ] **Step 1: 创建router/index.js**

```javascript
import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  {
    path: '/login',
    name: 'Login',
    component: () => import('../views/LoginView.vue')
  },
  {
    path: '/register',
    name: 'Register',
    component: () => import('../views/RegisterView.vue')
  },
  {
    path: '/',
    name: 'Home',
    component: () => import('../views/HomeView.vue')
  },
  {
    path: '/book/:id',
    name: 'BookDetail',
    component: () => import('../views/BookDetailView.vue')
  },
  {
    path: '/recommend',
    name: 'Recommend',
    component: () => import('../views/RecommendView.vue')
  },
  {
    path: '/compare',
    name: 'Compare',
    component: () => import('../views/CompareView.vue')
  },
  {
    path: '/profile',
    name: 'Profile',
    component: () => import('../views/ProfileView.vue')
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

export default router
```

- [ ] **Step 2: 创建stores/user.js**

```javascript
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

export const useUserStore = defineStore('user', () => {
  const user = ref(null)
  const isLoggedIn = computed(() => !!user.value)

  const setUser = (userData) => {
    user.value = userData
    localStorage.setItem('user', JSON.stringify(userData))
  }

  const logout = () => {
    user.value = null
    localStorage.removeItem('user')
  }

  const initUser = () => {
    const stored = localStorage.getItem('user')
    if (stored) {
      user.value = JSON.parse(stored)
    }
  }

  return { user, isLoggedIn, setUser, logout, initUser }
})
```

- [ ] **Step 3: 创建stores/book.js**

```javascript
import { defineStore } from 'pinia'
import { ref } from 'vue'

export const useBookStore = defineStore('book', () => {
  const books = ref([])
  const currentBook = ref(null)
  const recommendations = ref([])
  const loading = ref(false)

  const setBooks = (bookList) => {
    books.value = bookList
  }

  const setCurrentBook = (book) => {
    currentBook.value = book
  }

  const setRecommendations = (recs) => {
    recommendations.value = recs
  }

  return { books, currentBook, recommendations, loading, setBooks, setCurrentBook, setRecommendations }
})
```

- [ ] **Step 4: Commit**

```bash
git add frontend/src/router frontend/src/stores
git commit -m "feat: add Vue Router and Pinia stores"
```

---

## Task 13: API封装

**Files:**
- Create: `frontend/src/api/index.js`

- [ ] **Step 1: 创建api/index.js**

```javascript
import axios from 'axios'

const api = axios.create({
  baseURL: '/api',
  timeout: 10000,
  headers: {
    'Content-Type': 'application/json'
  }
})

// 请求拦截器
api.interceptors.request.use(
  (config) => {
    const user = JSON.parse(localStorage.getItem('user') || '{}')
    if (user.id) {
      config.params = { ...config.params, user_id: user.id }
    }
    return config
  },
  (error) => {
    return Promise.reject(error)
  }
)

// 响应拦截器
api.interceptors.response.use(
  (response) => response.data,
  (error) => {
    console.error('API Error:', error)
    return Promise.reject(error)
  }
)

// 认证相关
export const authAPI = {
  register: (data) => api.post('/auth/register', data),
  login: (data) => api.post('/auth/login', data),
  getMe: (userId) => api.get('/auth/me', { params: { user_id: userId } })
}

// 书籍相关
export const bookAPI = {
  getBooks: (params) => api.get('/books', { params }),
  getBook: (id) => api.get(`/books/${id}`),
  getSimilar: (id) => api.get(`/books/${id}/similar`)
}

// 评分相关
export const ratingAPI = {
  createRating: (data) => api.post('/ratings', data),
  getUserRatings: (userId) => api.get('/ratings/user', { params: { user_id: userId } })
}

// 推荐相关
export const recommendAPI = {
  getCFRecommendations: (userId, n = 10) => 
    api.get('/recommend/cf', { params: { user_id: userId, n } }),
  getSVDRecommendations: (userId, n = 10) => 
    api.get('/recommend/svd', { params: { user_id: userId, n } }),
  compareAlgorithms: () => api.get('/recommend/compare')
}

export default api
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/api/index.js
git commit -m "feat: add API client with axios"
```

---

## Task 14: 基础组件

**Files:**
- Create: `frontend/src/components/AppSidebar.vue`
- Create: `frontend/src/components/BookCard.vue`
- Create: `frontend/src/components/StarRating.vue`

- [ ] **Step 1: 创建AppSidebar.vue**

```vue
<template>
  <el-aside width="200px" class="sidebar">
    <div class="logo">
      <h2>二手书推荐</h2>
    </div>
    <el-menu
      :default-active="$route.path"
      router
      class="el-menu-vertical"
      background-color="#1a1a2e"
      text-color="#fff"
      active-text-color="#F97316"
    >
      <el-menu-item index="/">
        <el-icon><HomeFilled /></el-icon>
        <span>书籍广场</span>
      </el-menu-item>
      <el-menu-item index="/recommend">
        <el-icon><StarFilled /></el-icon>
        <span>为你推荐</span>
      </el-menu-item>
      <el-menu-item index="/compare">
        <el-icon><TrendCharts /></el-icon>
        <span>算法对比</span>
      </el-menu-item>
      <el-menu-item index="/profile">
        <el-icon><UserFilled /></el-icon>
        <span>个人中心</span>
      </el-menu-item>
    </el-menu>
  </el-aside>
</template>

<script setup>
import { HomeFilled, StarFilled, TrendCharts, UserFilled } from '@element-plus/icons-vue'
</script>

<style scoped>
.sidebar {
  background-color: #1a1a2e;
  min-height: 100vh;
}
.logo {
  padding: 20px;
  text-align: center;
  color: #F97316;
}
.logo h2 {
  margin: 0;
  font-size: 18px;
}
</style>
```

- [ ] **Step 2: 创建BookCard.vue**

```vue
<template>
  <el-card class="book-card" shadow="hover" @click="goToDetail">
    <div class="book-cover">
      <img v-if="book.image_url" :src="book.image_url" :alt="book.title" />
      <div v-else class="no-image">暂无封面</div>
    </div>
    <div class="book-info">
      <h3 class="title">{{ book.title }}</h3>
      <p class="author">{{ book.author || '未知作者' }}</p>
      <p class="publisher">{{ book.publisher || '未知出版社' }}</p>
      <el-tag v-if="book.category" size="small">{{ book.category }}</el-tag>
    </div>
  </el-card>
</template>

<script setup>
import { useRouter } from 'vue-router'

const props = defineProps({
  book: {
    type: Object,
    required: true
  }
})

const router = useRouter()

const goToDetail = () => {
  router.push(`/book/${props.book.id}`)
}
</script>

<style scoped>
.book-card {
  cursor: pointer;
  transition: transform 0.3s, box-shadow 0.3s;
  margin-bottom: 20px;
}
.book-card:hover {
  transform: translateY(-5px);
  box-shadow: 0 8px 16px rgba(0,0,0,0.2);
}
.book-cover {
  height: 200px;
  display: flex;
  align-items: center;
  justify-content: center;
  background-color: #f5f5f5;
  margin-bottom: 10px;
}
.book-cover img {
  max-height: 100%;
  max-width: 100%;
  object-fit: contain;
}
.no-image {
  color: #999;
}
.book-info .title {
  font-size: 16px;
  font-weight: bold;
  margin: 0 0 8px 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.book-info .author,
.book-info .publisher {
  font-size: 13px;
  color: #666;
  margin: 4px 0;
}
</style>
```

- [ ] **Step 3: 创建StarRating.vue**

```vue
<template>
  <div class="star-rating">
    <el-rate
      v-model="rating"
      :max="10"
      show-score
      text-color="#ff9900"
      @change="handleChange"
    />
  </div>
</template>

<script setup>
import { ref } from 'vue'

const props = defineProps({
  initialRating: {
    type: Number,
    default: 0
  }
})

const emit = defineEmits(['rate'])

const rating = ref(props.initialRating)

const handleChange = (value) => {
  emit('rate', value)
}
</script>

<style scoped>
.star-rating {
  display: inline-block;
}
</style>
```

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/
git commit -m "feat: add base UI components"
```

---

## Task 15: App.vue与页面视图

**Files:**
- Create: `frontend/src/App.vue`
- Create: `frontend/src/views/LoginView.vue`
- Create: `frontend/src/views/RegisterView.vue`

- [ ] **Step 1: 创建App.vue**

```vue
<template>
  <div class="app">
    <template v-if="!isAuthPage">
      <el-container>
        <AppSidebar />
        <el-main>
          <router-view />
        </el-main>
      </el-container>
    </template>
    <template v-else>
      <router-view />
    </template>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import AppSidebar from './components/AppSidebar.vue'

const route = useRoute()
const isAuthPage = computed(() => {
  return route.path === '/login' || route.path === '/register'
})
</script>

<style>
* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}
body {
  font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
  background-color: #f5f5f5;
}
.el-main {
  padding: 20px;
  background-color: #f5f5f5;
  min-height: 100vh;
}
</style>
```

- [ ] **Step 2: 创建LoginView.vue**

```vue
<template>
  <div class="auth-page">
    <el-card class="auth-card">
      <h2>登录</h2>
      <el-form :model="form" @submit.prevent="handleLogin">
        <el-form-item>
          <el-input v-model="form.username" placeholder="用户名" />
        </el-form-item>
        <el-form-item>
          <el-input v-model="form.password" type="password" placeholder="密码" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="handleLogin" :loading="loading" style="width: 100%">
            登录
          </el-button>
        </el-form-item>
      </el-form>
      <p class="auth-link">
        还没有账号？<router-link to="/register">立即注册</router-link>
      </p>
    </el-card>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { authAPI } from '../api'
import { useUserStore } from '../stores/user'

const router = useRouter()
const userStore = useUserStore()

const form = ref({
  username: '',
  password: ''
})
const loading = ref(false)

const handleLogin = async () => {
  if (!form.value.username || !form.value.password) {
    ElMessage.warning('请填写用户名和密码')
    return
  }
  
  loading.value = true
  try {
    const res = await authAPI.login(form.value)
    if (res.user) {
      userStore.setUser(res.user)
      ElMessage.success('登录成功')
      router.push('/')
    }
  } catch (error) {
    ElMessage.error(error.response?.data?.error || '登录失败')
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.auth-page {
  display: flex;
  justify-content: center;
  align-items: center;
  min-height: 100vh;
  background-color: #1a1a2e;
}
.auth-card {
  width: 400px;
  padding: 20px;
}
.auth-card h2 {
  text-align: center;
  margin-bottom: 20px;
  color: #1a1a2e;
}
.auth-link {
  text-align: center;
  margin-top: 15px;
}
</style>
```

- [ ] **Step 3: 创建RegisterView.vue**

```vue
<template>
  <div class="auth-page">
    <el-card class="auth-card">
      <h2>注册</h2>
      <el-form :model="form" @submit.prevent="handleRegister">
        <el-form-item>
          <el-input v-model="form.username" placeholder="用户名" />
        </el-form-item>
        <el-form-item>
          <el-input v-model="form.email" placeholder="邮箱（可选）" />
        </el-form-item>
        <el-form-item>
          <el-input v-model="form.password" type="password" placeholder="密码" />
        </el-form-item>
        <el-form-item>
          <el-input v-model="form.confirmPassword" type="password" placeholder="确认密码" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="handleRegister" :loading="loading" style="width: 100%">
            注册
          </el-button>
        </el-form-item>
      </el-form>
      <p class="auth-link">
        已有账号？<router-link to="/login">立即登录</router-link>
      </p>
    </el-card>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { authAPI } from '../api'

const router = useRouter()

const form = ref({
  username: '',
  email: '',
  password: '',
  confirmPassword: ''
})
const loading = ref(false)

const handleRegister = async () => {
  if (!form.value.username || !form.value.password) {
    ElMessage.warning('请填写用户名和密码')
    return
  }
  
  if (form.value.password !== form.value.confirmPassword) {
    ElMessage.warning('两次密码不一致')
    return
  }
  
  loading.value = true
  try {
    await authAPI.register({
      username: form.value.username,
      password: form.value.password,
      email: form.value.email
    })
    ElMessage.success('注册成功，请登录')
    router.push('/login')
  } catch (error) {
    ElMessage.error(error.response?.data?.error || '注册失败')
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.auth-page {
  display: flex;
  justify-content: center;
  align-items: center;
  min-height: 100vh;
  background-color: #1a1a2e;
}
.auth-card {
  width: 400px;
  padding: 20px;
}
.auth-card h2 {
  text-align: center;
  margin-bottom: 20px;
  color: #1a1a2e;
}
.auth-link {
  text-align: center;
  margin-top: 15px;
}
</style>
```

- [ ] **Step 4: Commit**

```bash
git add frontend/src/App.vue frontend/src/views/LoginView.vue frontend/src/views/RegisterView.vue
git commit -m "feat: add App layout and auth views"
```

---

## Task 16: 首页与书籍详情页

**Files:**
- Create: `frontend/src/views/HomeView.vue`
- Create: `frontend/src/views/BookDetailView.vue`

- [ ] **Step 1: 创建HomeView.vue**

```vue
<template>
  <div class="home-view">
    <div class="header">
      <h1>书籍广场</h1>
      <el-input
        v-model="searchQuery"
        placeholder="搜索书名或作者"
        class="search-input"
        clearable
        @input="handleSearch"
      >
        <template #prefix>
          <el-icon><Search /></el-icon>
        </template>
      </el-input>
    </div>
    
    <div class="book-grid">
      <BookCard
        v-for="book in books"
        :key="book.id"
        :book="book"
      />
    </div>
    
    <div class="pagination">
      <el-pagination
        v-model:current-page="currentPage"
        :page-size="20"
        :total="total"
        layout="prev, pager, next"
        @current-change="handlePageChange"
      />
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { Search } from '@element-plus/icons-vue'
import { bookAPI } from '../api'
import BookCard from '../components/BookCard.vue'

const books = ref([])
const searchQuery = ref('')
const currentPage = ref(1)
const total = ref(0)
const loading = ref(false)

const fetchBooks = async () => {
  loading.value = true
  try {
    const res = await bookAPI.getBooks({
      page: currentPage.value,
      per_page: 20,
      search: searchQuery.value
    })
    books.value = res.books
    total.value = res.total
  } catch (error) {
    console.error('Failed to fetch books:', error)
  } finally {
    loading.value = false
  }
}

const handleSearch = () => {
  currentPage.value = 1
  fetchBooks()
}

const handlePageChange = (page) => {
  currentPage.value = page
  fetchBooks()
}

onMounted(() => {
  fetchBooks()
})
</script>

<style scoped>
.home-view {
  padding: 20px;
}
.header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 30px;
}
.header h1 {
  color: #1a1a2e;
  margin: 0;
}
.search-input {
  width: 300px;
}
.book-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
  gap: 20px;
}
.pagination {
  margin-top: 30px;
  text-align: center;
}
</style>
```

- [ ] **Step 2: 创建BookDetailView.vue**

```vue
<template>
  <div class="book-detail" v-if="book">
    <el-row :gutter="30">
      <el-col :span="8">
        <div class="book-cover-large">
          <img v-if="book.image_url" :src="book.image_url" :alt="book.title" />
          <div v-else class="no-image">暂无封面</div>
        </div>
      </el-col>
      <el-col :span="16">
        <div class="book-info">
          <h1>{{ book.title }}</h1>
          <p class="info-item"><strong>作者：</strong>{{ book.author || '未知' }}</p>
          <p class="info-item"><strong>出版社：</strong>{{ book.publisher || '未知' }}</p>
          <p class="info-item"><strong>出版年份：</strong>{{ book.year || '未知' }}</p>
          <p class="info-item"><strong>ISBN：</strong>{{ book.isbn }}</p>
          
          <div class="rating-section">
            <h3>给这本书评分</h3>
            <StarRating :initial-rating="userRating" @rate="handleRate" />
          </div>
        </div>
      </el-col>
    </el-row>
    
    <div class="similar-books" v-if="similarBooks.length > 0">
      <h2>相似书籍</h2>
      <div class="book-grid">
        <BookCard
          v-for="b in similarBooks"
          :key="b.id"
          :book="b"
        />
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import { bookAPI, ratingAPI } from '../api'
import { useUserStore } from '../stores/user'
import BookCard from '../components/BookCard.vue'
import StarRating from '../components/StarRating.vue'

const route = useRoute()
const userStore = useUserStore()

const book = ref(null)
const similarBooks = ref([])
const userRating = ref(0)

const fetchBookDetail = async () => {
  try {
    const res = await bookAPI.getBook(route.params.id)
    book.value = res.book
    
    const similarRes = await bookAPI.getSimilar(route.params.id)
    similarBooks.value = similarRes.similar_books
  } catch (error) {
    console.error('Failed to fetch book detail:', error)
  }
}

const handleRate = async (rating) => {
  if (!userStore.isLoggedIn) {
    ElMessage.warning('请先登录')
    return
  }
  
  try {
    await ratingAPI.createRating({
      user_id: userStore.user.id,
      book_id: book.value.id,
      rating: rating
    })
    ElMessage.success('评分成功')
    userRating.value = rating
  } catch (error) {
    ElMessage.error('评分失败')
  }
}

onMounted(() => {
  fetchBookDetail()
})
</script>

<style scoped>
.book-detail {
  padding: 20px;
}
.book-cover-large {
  width: 100%;
  height: 400px;
  display: flex;
  align-items: center;
  justify-content: center;
  background-color: #f5f5f5;
  border-radius: 8px;
}
.book-cover-large img {
  max-height: 100%;
  max-width: 100%;
  object-fit: contain;
}
.no-image {
  color: #999;
  font-size: 18px;
}
.book-info h1 {
  color: #1a1a2e;
  margin-bottom: 20px;
}
.info-item {
  font-size: 16px;
  margin: 10px 0;
  color: #333;
}
.rating-section {
  margin-top: 30px;
  padding: 20px;
  background-color: #fff;
  border-radius: 8px;
}
.similar-books {
  margin-top: 40px;
}
.similar-books h2 {
  color: #1a1a2e;
  margin-bottom: 20px;
}
.book-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
  gap: 15px;
}
</style>
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/views/HomeView.vue frontend/src/views/BookDetailView.vue
git commit -m "feat: add home and book detail views"
```

---

## Task 17: 推荐页与算法对比页

**Files:**
- Create: `frontend/src/views/RecommendView.vue`
- Create: `frontend/src/views/CompareView.vue`
- Create: `frontend/src/components/CompareChart.vue`

- [ ] **Step 1: 创建RecommendView.vue**

```vue
<template>
  <div class="recommend-view">
    <h1>为你推荐</h1>
    
    <el-tabs v-model="activeTab">
      <el-tab-pane label="协同过滤" name="cf">
        <div class="recommend-list">
          <BookCard
            v-for="book in cfRecommendations"
            :key="book.id"
            :book="book"
          />
        </div>
      </el-tab-pane>
      
      <el-tab-pane label="SVD矩阵分解" name="svd">
        <div class="recommend-list">
          <BookCard
            v-for="book in svdRecommendations"
            :key="book.id"
            :book="book"
          />
        </div>
      </el-tab-pane>
    </el-tabs>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { recommendAPI } from '../api'
import { useUserStore } from '../stores/user'
import BookCard from '../components/BookCard.vue'

const userStore = useUserStore()
const activeTab = ref('cf')
const cfRecommendations = ref([])
const svdRecommendations = ref([])
const loading = ref(false)

const fetchRecommendations = async () => {
  if (!userStore.isLoggedIn) {
    ElMessage.warning('请先登录')
    return
  }
  
  loading.value = true
  try {
    const [cfRes, svdRes] = await Promise.all([
      recommendAPI.getCFRecommendations(userStore.user.id, 10),
      recommendAPI.getSVDRecommendations(userStore.user.id, 10)
    ])
    
    cfRecommendations.value = cfRes.recommendations
    svdRecommendations.value = svdRes.recommendations
  } catch (error) {
    console.error('Failed to fetch recommendations:', error)
    ElMessage.error('获取推荐失败')
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  fetchRecommendations()
})
</script>

<style scoped>
.recommend-view {
  padding: 20px;
}
.recommend-view h1 {
  color: #1a1a2e;
  margin-bottom: 20px;
}
.recommend-list {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
  gap: 20px;
  margin-top: 20px;
}
</style>
```

- [ ] **Step 2: 创建CompareView.vue**

```vue
<template>
  <div class="compare-view">
    <h1>算法对比分析</h1>
    
    <el-card class="metric-card">
      <template #header>
        <span>评估指标对比</span>
      </template>
      <CompareChart :data="compareData" />
    </el-card>
    
    <el-card class="detail-card">
      <template #header>
        <span>详细数据</span>
      </template>
      <el-table :data="tableData" style="width: 100%">
        <el-table-column prop="algorithm" label="算法" />
        <el-table-column prop="rmse" label="RMSE" />
        <el-table-column prop="mae" label="MAE" />
      </el-table>
    </el-card>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { recommendAPI } from '../api'
import CompareChart from '../components/CompareChart.vue'

const compareData = ref({})
const tableData = ref([])

const fetchCompareData = async () => {
  try {
    const res = await recommendAPI.compareAlgorithms()
    compareData.value = res.comparison || {}
    
    tableData.value = [
      {
        algorithm: '协同过滤 (CF)',
        rmse: res.collaborative_filtering?.rmse?.toFixed(4) || 'N/A',
        mae: res.collaborative_filtering?.mae?.toFixed(4) || 'N/A'
      },
      {
        algorithm: 'SVD矩阵分解',
        rmse: res.svd?.rmse?.toFixed(4) || 'N/A',
        mae: res.svd?.mae?.toFixed(4) || 'N/A'
      }
    ]
  } catch (error) {
    console.error('Failed to fetch compare data:', error)
  }
}

onMounted(() => {
  fetchCompareData()
})
</script>

<style scoped>
.compare-view {
  padding: 20px;
}
.compare-view h1 {
  color: #1a1a2e;
  margin-bottom: 20px;
}
.metric-card,
.detail-card {
  margin-bottom: 20px;
}
</style>
```

- [ ] **Step 3: 创建CompareChart.vue**

```vue
<template>
  <div ref="chartRef" class="chart-container"></div>
</template>

<script setup>
import { ref, onMounted, watch } from 'vue'
import * as echarts from 'echarts'

const props = defineProps({
  data: {
    type: Object,
    default: () => ({})
  }
})

const chartRef = ref(null)
let chart = null

const initChart = () => {
  if (!chartRef.value) return
  
  chart = echarts.init(chartRef.value)
  updateChart()
}

const updateChart = () => {
  if (!chart) return
  
  const rmseData = props.data.rmse || {}
  const maeData = props.data.mae || {}
  
  const option = {
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'shadow' }
    },
    legend: {
      data: ['RMSE', 'MAE']
    },
    xAxis: {
      type: 'category',
      data: ['协同过滤', 'SVD矩阵分解']
    },
    yAxis: {
      type: 'value',
      name: '误差值'
    },
    series: [
      {
        name: 'RMSE',
        type: 'bar',
        data: [rmseData.cf || 0, rmseData.svd || 0],
        itemStyle: { color: '#F97316' }
      },
      {
        name: 'MAE',
        type: 'bar',
        data: [maeData.cf || 0, maeData.svd || 0],
        itemStyle: { color: '#3B82F6' }
      }
    ]
  }
  
  chart.setOption(option)
}

watch(() => props.data, updateChart, { deep: true })

onMounted(() => {
  initChart()
  window.addEventListener('resize', () => chart?.resize())
})
</script>

<style scoped>
.chart-container {
  width: 100%;
  height: 400px;
}
</style>
```

- [ ] **Step 4: Commit**

```bash
git add frontend/src/views/RecommendView.vue frontend/src/views/CompareView.vue frontend/src/components/CompareChart.vue
git commit -m "feat: add recommendation and algorithm comparison views"
```

---

## Task 18: 个人中心页

**Files:**
- Create: `frontend/src/views/ProfileView.vue`

- [ ] **Step 1: 创建ProfileView.vue**

```vue
<template>
  <div class="profile-view">
    <h1>个人中心</h1>
    
    <el-card class="user-info">
      <template #header>
        <span>用户信息</span>
      </template>
      <p><strong>用户名：</strong>{{ userStore.user?.username }}</p>
      <p><strong>邮箱：</strong>{{ userStore.user?.email || '未设置' }}</p>
    </el-card>
    
    <el-card class="rating-history">
      <template #header>
        <span>评分历史</span>
      </template>
      <el-table :data="ratings" style="width: 100%">
        <el-table-column prop="book.title" label="书名" />
        <el-table-column prop="book.author" label="作者" />
        <el-table-column prop="rating" label="评分" width="100">
          <template #default="scope">
            <el-rate v-model="scope.row.rating" disabled show-score />
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="评分时间" />
      </el-table>
    </el-card>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ratingAPI } from '../api'
import { useUserStore } from '../stores/user'

const userStore = useUserStore()
const ratings = ref([])

const fetchRatings = async () => {
  if (!userStore.isLoggedIn) return
  
  try {
    const res = await ratingAPI.getUserRatings(userStore.user.id)
    ratings.value = res.ratings
  } catch (error) {
    console.error('Failed to fetch ratings:', error)
  }
}

onMounted(() => {
  fetchRatings()
})
</script>

<style scoped>
.profile-view {
  padding: 20px;
}
.profile-view h1 {
  color: #1a1a2e;
  margin-bottom: 20px;
}
.user-info,
.rating-history {
  margin-bottom: 20px;
}
</style>
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/views/ProfileView.vue
git commit -m "feat: add user profile view"
```

---

## Task 19: 前端启动与联调

**Files:**
- Modify: `frontend/src/main.js`

- [ ] **Step 1: 更新main.js初始化用户**

Modify: `frontend/src/main.js`

```javascript
import { createApp } from 'vue'
import { createPinia } from 'pinia'
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'
import App from './App.vue'
import router from './router'
import { useUserStore } from './stores/user'

const app = createApp(App)

app.use(createPinia())

// 初始化用户状态
const userStore = useUserStore()
userStore.initUser()

app.use(router)
app.use(ElementPlus)

app.mount('#app')
```

- [ ] **Step 2: 启动后端服务**

Run: `cd backend && python app.py`
Expected: Flask服务在5000端口启动

- [ ] **Step 3: 启动前端服务**

Run: `cd frontend && npm run dev`
Expected: Vite服务在5173端口启动

- [ ] **Step 4: 测试完整流程**

1. 访问 http://localhost:5173
2. 注册新用户
3. 浏览书籍
4. 给书籍评分
5. 查看推荐结果
6. 查看算法对比

- [ ] **Step 5: Commit**

```bash
git add frontend/src/main.js
git commit -m "feat: initialize user state on app startup"
```

---

## Task 20: README与项目文档

**Files:**
- Create: `README.md`

- [ ] **Step 1: 创建README.md**

```markdown
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
git clone <repository-url>
cd campus-book-recommend
```

### 2. 配置MySQL数据库

```bash
mysql -u root -p -e "CREATE DATABASE book_recommend CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"
```

### 3. 启动后端

```bash
cd backend
pip install -r requirements.txt
python import_data.py  # 导入数据集
python app.py
```

### 4. 启动前端

```bash
cd frontend
npm install
npm run dev
```

### 5. 访问应用

打开浏览器访问 http://localhost:5173

## 项目结构

```
campus-book-recommend/
├── backend/          # Flask后端
├── frontend/         # Vue 3前端
└── README.md
```

## 算法对比

系统实现了两种推荐算法：

1. **协同过滤（Collaborative Filtering）**
   - 基于用户的协同过滤
   - 基于物品的协同过滤
   - 使用余弦相似度计算

2. **SVD矩阵分解**
   - 使用Surprise库实现
   - 将评分矩阵分解为隐因子矩阵

评估指标：RMSE、MAE

## 功能特性

- 用户注册/登录
- 书籍浏览与搜索
- 用户评分
- 个性化推荐（两种算法）
- 算法对比可视化
- 评分历史查看

## 许可证

MIT License
```

- [ ] **Step 2: Commit**

```bash
git add README.md
git commit -m "docs: add project README"
```

---

## 实现计划总结

| 阶段 | 任务 | 说明 |
|------|------|------|
| 环境搭建 | Task 1-2 | 后端项目初始化、数据库模型 |
| API开发 | Task 3-5 | 认证、书籍、评分API |
| 算法实现 | Task 6-9 | 数据加载、CF、SVD、评估器、推荐API |
| 数据导入 | Task 10 | Book-Crossing数据集导入 |
| 前端搭建 | Task 11-13 | Vue 3项目、路由、状态管理、API封装 |
| 前端组件 | Task 14-18 | 基础组件、页面视图 |
| 联调测试 | Task 19 | 前后端联调 |
| 文档 | Task 20 | README编写 |

---

## Spec覆盖检查

| 设计文档章节 | 对应任务 |
|-------------|---------|
| 系统架构 | Task 1-2 |
| 数据库设计 | Task 2 |
| 推荐算法 | Task 7-8 |
| 评估指标 | Task 9 |
| 前端页面 | Task 14-18 |
| API接口 | Task 3-5, 9 |
| 数据导入 | Task 6, 10 |

所有设计文档中的功能点均已覆盖。
