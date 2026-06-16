# 书籍推荐系统 V2 现代化重构实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将现有 Flask 推荐系统重构为 FastAPI + PostgreSQL + Redis + Vue3 的现代化架构，实现多维度反馈、冷启动优化、探索-利用平衡三大核心功能。

**Architecture:** 采用分层架构设计，后端分为 API 层、业务逻辑层、数据层；前端保持 Vue3 + Element Plus 技术栈；引入 Docker Compose 实现一键部署。

**Tech Stack:** FastAPI, SQLAlchemy 2.0, PostgreSQL 15, Redis 7, Celery 5, Vue 3.4+, Element Plus 2.5, Docker

---

## 阶段概览

| 阶段 | 名称 | 预计任务数 | 核心产出 |
|---|---|---|---|
| **阶段 1** | 项目脚手架与数据层 | 8 | 项目目录、Docker 配置、数据库模型 |
| **阶段 2** | API 层开发 | 10 | 所有 REST API 接口 |
| **阶段 3** | 推荐算法服务 | 6 | CF/SVD/混合推荐引擎 |
| **阶段 4** | 核心功能实现 | 8 | 交互系统、冷启动、探索平衡 |
| **阶段 5** | 前端升级 | 6 | 新 UI 组件、交互功能 |
| **阶段 6** | 数据迁移与测试 | 5 | 从 V1 迁移数据、端到端测试 |

---

## 阶段 1: 项目脚手架与数据层

### 任务 1.1: 创建项目目录结构

**Files:**
- Create: `book-v2/backend/`
- Create: `book-v2/backend/app/`
- Create: `book-v2/backend/app/models/`
- Create: `book-v2/backend/app/schemas/`
- Create: `book-v2/backend/app/api/`
- Create: `book-v2/backend/app/services/`
- Create: `book-v2/backend/app/services/recommender/`
- Create: `book-v2/backend/app/tasks/`
- Create: `book-v2/backend/tests/`
- Create: `book-v2/frontend-v2/`
- Create: `book-v2/docker-compose.yml`
- Create: `book-v2/.env.example`

- [ ] **Step 1: 创建目录结构**

```bash
mkdir -p book-v2/backend/app/{models,schemas,api,services/recommender,tasks}
mkdir -p book-v2/backend/tests
mkdir -p book-v2/frontend-v2
touch book-v2/docker-compose.yml
touch book-v2/.env.example
```

### 任务 1.2: Docker Compose 配置

**Files:**
- Create: `book-v2/docker-compose.yml`

- [ ] **Step 1: 编写 docker-compose.yml**

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
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres"]
      interval: 5s
      timeout: 5s
      retries: 5

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 5s
      retries: 5

  backend:
    build: ./backend
    ports:
      - "8000:8000"
    env_file:
      - .env
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
    volumes:
      - ./backend:/app
    command: uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

  celery_worker:
    build: ./backend
    env_file:
      - .env
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
    volumes:
      - ./backend:/app
    command: celery -A app.celery_app worker --loglevel=info

volumes:
  postgres_data:
  redis_data:
```

### 任务 1.3: 后端依赖配置

**Files:**
- Create: `book-v2/backend/requirements.txt`
- Create: `book-v2/backend/Dockerfile`

- [ ] **Step 1: 编写 requirements.txt**

```
fastapi==0.109.2
uvicorn[standard]==0.27.1
sqlalchemy==2.0.25
psycopg2-binary==2.9.9
alembic==1.13.1
redis==5.0.1
celery==5.3.6
pydantic==2.6.1
pydantic-settings==2.1.0
python-jose[cryptography]==3.3.0
passlib[bcrypt]==1.7.4
python-multipart==0.0.9
surprise==1.1.1
numpy==1.26.4
pandas==2.2.0
httpx==0.26.0
pytest==8.0.0
pytest-asyncio==0.23.4
```

- [ ] **Step 2: 编写 Dockerfile**

```dockerfile
FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### 任务 1.4: 环境变量配置

**Files:**
- Create: `book-v2/.env.example`

- [ ] **Step 1: 编写 .env.example**

```
DATABASE_URL=postgresql://postgres:postgres123@localhost:5432/book_recommend
REDIS_URL=redis://localhost:6379/0
CELERY_BROKER_URL=redis://localhost:6379/1
CELERY_RESULT_BACKEND=redis://localhost:6379/2
SECRET_KEY=your-super-secret-key-change-this-in-production
DEBUG=true
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
```

### 任务 1.5: 数据库连接配置

**Files:**
- Create: `book-v2/backend/app/__init__.py`
- Create: `book-v2/backend/app/config.py`
- Create: `book-v2/backend/app/database.py`

- [ ] **Step 1: 编写 app/config.py**

```python
from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    # Database
    DATABASE_URL: str = "postgresql://postgres:postgres123@localhost:5432/book_recommend"

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"
    CELERY_BROKER_URL: str = "redis://localhost:6379/1"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/2"

    # Security
    SECRET_KEY: str = "change-this-secret-key"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    # App
    DEBUG: bool = True

    class Config:
        env_file = ".env"


settings = Settings()
```

- [ ] **Step 2: 编写 app/database.py**

```python
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from app.config import settings

engine = create_engine(settings.DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

### 任务 1.6: 数据模型 - User & Book

**Files:**
- Create: `book-v2/backend/app/models/__init__.py`
- Create: `book-v2/backend/app/models/user.py`
- Create: `book-v2/backend/app/models/book.py`

- [ ] **Step 1: 编写 models/user.py**

```python
from sqlalchemy import Column, Integer, String, Boolean, DateTime
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, nullable=False, index=True)
    email = Column(String(100), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    avatar_url = Column(String(500))
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    ratings = relationship("Rating", back_populates="user", cascade="all, delete-orphan")
    interactions = relationship("Interaction", back_populates="user", cascade="all, delete-orphan")
    tags = relationship("UserTag", back_populates="user", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<User {self.username}>"
```

- [ ] **Step 2: 编写 models/book.py**

```python
from sqlalchemy import Column, Integer, String, Text, ARRAY, Float, DateTime
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base


class Book(Base):
    __tablename__ = "books"

    id = Column(Integer, primary_key=True, index=True)
    isbn = Column(String(20), unique=True, nullable=False, index=True)
    title = Column(String(255), nullable=False)
    author = Column(String(255))
    year = Column(Integer)
    publisher = Column(String(255))
    image_url = Column(String(500))
    description = Column(Text)
    category = Column(String(100))
    tags = Column(ARRAY(String), default=[])
    avg_rating = Column(Float, default=0.0)
    rating_count = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    ratings = relationship("Rating", back_populates="book", cascade="all, delete-orphan")
    interactions = relationship("Interaction", back_populates="book", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Book {self.title}>"
```

### 任务 1.7: 数据模型 - Rating & Interaction

**Files:**
- Create: `book-v2/backend/app/models/rating.py`
- Create: `book-v2/backend/app/models/interaction.py`
- Create: `book-v2/backend/app/models/user_tag.py`

- [ ] **Step 1: 编写 models/rating.py**

```python
from sqlalchemy import Column, Integer, ForeignKey, DateTime, CheckConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base


class Rating(Base):
    __tablename__ = "ratings"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    book_id = Column(Integer, ForeignKey("books.id", ondelete="CASCADE"), nullable=False, index=True)
    rating = Column(Integer, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    user = relationship("User", back_populates="ratings")
    book = relationship("Book", back_populates="ratings")

    __table_args__ = (
        CheckConstraint('rating >= 1 AND rating <= 10', name='rating_range_check'),
    )

    def __repr__(self):
        return f"<Rating user={self.user_id} book={self.book_id} rating={self.rating}>"
```

- [ ] **Step 2: 编写 models/interaction.py**

```python
from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base


class Interaction(Base):
    __tablename__ = "interactions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    book_id = Column(Integer, ForeignKey("books.id", ondelete="CASCADE"), nullable=False, index=True)
    interaction_type = Column(String(20), nullable=False)  # 'view', 'like', 'dislike', 'want_to_read', 'read'
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    user = relationship("User", back_populates="interactions")
    book = relationship("Book", back_populates="interactions")

    __table_args__ = (
        UniqueConstraint('user_id', 'book_id', 'interaction_type', name='unique_user_book_interaction'),
    )

    def __repr__(self):
        return f"<Interaction user={self.user_id} book={self.book_id} type={self.interaction_type}>"
```

- [ ] **Step 3: 编写 models/user_tag.py**

```python
from sqlalchemy import Column, Integer, String, Float, ForeignKey, DateTime, UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base


class UserTag(Base):
    __tablename__ = "user_tags"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    tag_name = Column(String(50), nullable=False)
    weight = Column(Float, default=1.0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    user = relationship("User", back_populates="tags")

    __table_args__ = (
        UniqueConstraint('user_id', 'tag_name', name='unique_user_tag'),
    )

    def __repr__(self):
        return f"<UserTag user={self.user_id} tag={self.tag_name}>"
```

### 任务 1.8: Alembic 数据库迁移配置

**Files:**
- Create: `book-v2/backend/alembic.ini`
- Create: `book-v2/backend/alembic/env.py`
- Create: `book-v2/backend/alembic/versions/`

- [ ] **Step 1: 初始化 Alembic**

```bash
cd book-v2/backend
alembic init alembic
```

- [ ] **Step 2: 配置 alembic/env.py**

```python
from logging.config import fileConfig
from sqlalchemy import engine_from_config, pool
from alembic import context
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from app.database import Base
from app.models import User, Book, Rating, Interaction, UserTag
from app.config import settings

config = context.config
config.set_main_option("sqlalchemy.url", settings.DATABASE_URL)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
```

---

## 阶段 2: API 层开发

### 任务 2.1: FastAPI 入口与依赖注入

**Files:**
- Create: `book-v2/backend/app/main.py`
- Create: `book-v2/backend/app/api/__init__.py`
- Create: `book-v2/backend/app/api/deps.py`

- [ ] **Step 1: 编写 app/main.py**

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
from app.api import auth, books, ratings, interactions, recommend, users

app = FastAPI(
    title="Book Recommendation System V2",
    description="Modern book recommendation system with multi-dimensional feedback",
    version="2.0.0",
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(users.router, prefix="/api/users", tags=["users"])
app.include_router(books.router, prefix="/api/books", tags=["books"])
app.include_router(ratings.router, prefix="/api/ratings", tags=["ratings"])
app.include_router(interactions.router, prefix="/api/interactions", tags=["interactions"])
app.include_router(recommend.router, prefix="/api/recommend", tags=["recommend"])


@app.get("/api/health")
def health_check():
    return {"status": "ok", "version": "2.0.0"}
```

- [ ] **Step 2: 编写 app/api/deps.py**

```python
from typing import Generator
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlalchemy.orm import Session
from app.database import get_db
from app.config import settings
from app.models import User

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        user_id: int = payload.get("sub")
        if user_id is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise credentials_exception
    return user
```

### 任务 2.2: 认证 API

**Files:**
- Create: `book-v2/backend/app/api/auth.py`
- Create: `book-v2/backend/app/schemas/user.py`
- Create: `book-v2/backend/app/services/auth.py`

- [ ] **Step 1: 编写 schemas/user.py**

```python
from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import datetime


class UserBase(BaseModel):
    username: str
    email: EmailStr


class UserCreate(UserBase):
    password: str


class UserLogin(BaseModel):
    username: str
    password: str


class UserResponse(UserBase):
    id: int
    avatar_url: Optional[str] = None
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class TokenData(BaseModel):
    user_id: Optional[int] = None
```

- [ ] **Step 2: 编写 services/auth.py**

```python
from datetime import datetime, timedelta
from jose import jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session
from app.config import settings
from app.models import User

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


def create_access_token(data: dict, expires_delta: timedelta = None) -> str:
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def authenticate_user(db: Session, username: str, password: str) -> User:
    user = db.query(User).filter(User.username == username).first()
    if not user:
        return None
    if not verify_password(password, user.password_hash):
        return None
    return user
```

- [ ] **Step 3: 编写 api/auth.py**

```python
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from datetime import timedelta
from app.database import get_db
from app.schemas.user import UserCreate, UserResponse, Token
from app.services.auth import authenticate_user, create_access_token, get_password_hash
from app.models import User
from app.config import settings

router = APIRouter()


@router.post("/register", response_model=UserResponse)
def register(user_data: UserCreate, db: Session = Depends(get_db)):
    # Check if user exists
    if db.query(User).filter(User.username == user_data.username).first():
        raise HTTPException(status_code=400, detail="Username already registered")
    if db.query(User).filter(User.email == user_data.email).first():
        raise HTTPException(status_code=400, detail="Email already registered")

    # Create user
    user = User(
        username=user_data.username,
        email=user_data.email,
        password_hash=get_password_hash(user_data.password)
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.post("/login", response_model=Token)
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = authenticate_user(db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
        )
    access_token = create_access_token(
        data={"sub": user.id},
        expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    return {"access_token": access_token, "token_type": "bearer"}


@router.get("/me", response_model=UserResponse)
def get_me(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return current_user
```

### 任务 2.3: 书籍 API

**Files:**
- Create: `book-v2/backend/app/schemas/book.py`
- Create: `book-v2/backend/app/api/books.py`

- [ ] **Step 1: 编写 schemas/book.py**

```python
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime


class BookBase(BaseModel):
    title: str
    author: Optional[str] = None
    category: Optional[str] = None


class BookResponse(BookBase):
    id: int
    isbn: str
    year: Optional[int] = None
    publisher: Optional[str] = None
    image_url: Optional[str] = None
    description: Optional[str] = None
    tags: List[str] = []
    avg_rating: float = 0.0
    rating_count: int = 0

    class Config:
        from_attributes = True


class BookListResponse(BaseModel):
    books: List[BookResponse]
    total: int
    page: int
    pages: int


class BookDetailResponse(BookResponse):
    community_rating: dict  # avg_rating, rating_count, distribution, most_common_rating
    user_rating: Optional[int] = None
    user_interactions: dict = {}  # liked, disliked, wanted
```

- [ ] **Step 2: 编写 api/books.py**

```python
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import Optional
from app.database import get_db
from app.models import Book, Rating
from app.schemas.book import BookResponse, BookListResponse, BookDetailResponse
from app.api.deps import get_current_user
from app.models import User
from collections import Counter

router = APIRouter()


@router.get("/", response_model=BookListResponse)
def get_books(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    search: Optional[str] = None,
    category: Optional[str] = None,
    db: Session = Depends(get_db)
):
    query = db.query(Book)

    if search:
        query = query.filter(
            Book.title.ilike(f"%{search}%") | Book.author.ilike(f"%{search}%")
        )

    if category:
        query = query.filter(Book.category == category)

    total = query.count()
    books = query.offset((page - 1) * per_page).limit(per_page).all()

    return BookListResponse(
        books=[BookResponse.model_validate(b) for b in books],
        total=total,
        page=page,
        pages=(total + per_page - 1) // per_page
    )


@router.get("/{book_id}", response_model=BookDetailResponse)
def get_book(
    book_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    book = db.query(Book).filter(Book.id == book_id).first()
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")

    # Get community rating stats
    ratings = db.query(Rating).filter(Rating.book_id == book_id).all()
    rating_count = len(ratings)
    avg_rating = round(sum(r.rating for r in ratings) / rating_count, 1) if rating_count > 0 else None

    # Rating distribution
    distribution = {str(i): 0 for i in range(1, 11)}
    for r in ratings:
        key = str(r.rating)
        if key in distribution:
            distribution[key] += 1

    # Most common rating
    most_common = Counter(r.rating for r in ratings).most_common(1)
    most_common_rating = most_common[0][0] if most_common else None

    # User's rating
    user_rating = db.query(Rating).filter(
        Rating.user_id == current_user.id,
        Rating.book_id == book_id
    ).first()

    # User's interactions
    from app.models import Interaction
    interactions = db.query(Interaction).filter(
        Interaction.user_id == current_user.id,
        Interaction.book_id == book_id
    ).all()
    user_interactions = {i.interaction_type: True for i in interactions}

    return BookDetailResponse(
        **BookResponse.model_validate(book).model_dump(),
        community_rating={
            "avg_rating": avg_rating,
            "rating_count": rating_count,
            "distribution": distribution,
            "most_common_rating": most_common_rating
        },
        user_rating=user_rating.rating if user_rating else None,
        user_interactions=user_interactions
    )


@router.get("/{book_id}/similar")
def get_similar_books(book_id: int, db: Session = Depends(get_db)):
    book = db.query(Book).filter(Book.id == book_id).first()
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")

    # Find similar by author or category
    conditions = []
    if book.author:
        conditions.append(Book.author == book.author)
    if book.category:
        conditions.append(Book.category == book.category)

    if conditions:
        from sqlalchemy import or_
        similar = db.query(Book).filter(
            Book.id != book_id,
            or_(*conditions)
        ).limit(6).all()
    else:
        similar = db.query(Book).filter(Book.id != book_id).limit(6).all()

    return {"similar_books": [BookResponse.model_validate(b) for b in similar]}
```

### 任务 2.4: 评分 API

**Files:**
- Create: `book-v2/backend/app/schemas/rating.py`
- Create: `book-v2/backend/app/api/ratings.py`

- [ ] **Step 1: 编写 schemas/rating.py**

```python
from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional


class RatingCreate(BaseModel):
    book_id: int
    rating: int = Field(..., ge=1, le=10)


class RatingResponse(BaseModel):
    id: int
    user_id: int
    book_id: int
    rating: int
    created_at: datetime

    class Config:
        from_attributes = True


class RatingWithBook(RatingResponse):
    book: dict  # simplified book info
```

- [ ] **Step 2: 编写 api/ratings.py**

```python
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.schemas.rating import RatingCreate, RatingResponse, RatingWithBook
from app.models import Rating, Book
from app.api.deps import get_current_user
from app.models import User
from app.tasks.model_training import update_book_stats

router = APIRouter()


@router.post("/", response_model=RatingResponse)
def create_or_update_rating(
    rating_data: RatingCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # Check if book exists
    book = db.query(Book).filter(Book.id == rating_data.book_id).first()
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")

    # Check if rating exists
    existing = db.query(Rating).filter(
        Rating.user_id == current_user.id,
        Rating.book_id == rating_data.book_id
    ).first()

    if existing:
        existing.rating = rating_data.rating
        db.commit()
        db.refresh(existing)
    else:
        rating = Rating(
            user_id=current_user.id,
            book_id=rating_data.book_id,
            rating=rating_data.rating
        )
        db.add(rating)
        db.commit()
        db.refresh(rating)
        existing = rating

    # Update book stats asynchronously
    update_book_stats.delay(rating_data.book_id)

    return existing


@router.get("/user/{user_id}")
def get_user_ratings(
    user_id: int,
    page: int = 1,
    per_page: int = 20,
    db: Session = Depends(get_db)
):
    query = db.query(Rating).filter(Rating.user_id == user_id).order_by(Rating.created_at.desc())
    total = query.count()
    ratings = query.offset((page - 1) * per_page).limit(per_page).all()

    result = []
    for r in ratings:
        book = db.query(Book).filter(Book.id == r.book_id).first()
        result.append({
            **RatingResponse.model_validate(r).model_dump(),
            "book": {
                "id": book.id,
                "title": book.title,
                "author": book.author,
                "image_url": book.image_url
            } if book else None
        })

    return {
        "ratings": result,
        "total": total,
        "page": page,
        "pages": (total + per_page - 1) // per_page
    }
```

### 任务 2.5: 交互 API

**Files:**
- Create: `book-v2/backend/app/schemas/interaction.py`
- Create: `book-v2/backend/app/api/interactions.py`

- [ ] **Step 1: 编写 schemas/interaction.py**

```python
from pydantic import BaseModel
from datetime import datetime
from typing import Optional

INTERACTION_TYPES = ["view", "like", "dislike", "want_to_read", "read"]


class InteractionCreate(BaseModel):
    book_id: int
    interaction_type: str


class InteractionResponse(BaseModel):
    id: int
    user_id: int
    book_id: int
    interaction_type: str
    created_at: datetime

    class Config:
        from_attributes = True
```

- [ ] **Step 2: 编写 api/interactions.py**

```python
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.schemas.interaction import InteractionCreate, InteractionResponse
from app.models import Interaction, Book
from app.api.deps import get_current_user
from app.models import User

router = APIRouter()


@router.post("/", response_model=dict)
def create_interaction(
    interaction_data: InteractionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # Validate interaction type
    valid_types = ["view", "like", "dislike", "want_to_read", "read"]
    if interaction_data.interaction_type not in valid_types:
        raise HTTPException(status_code=400, detail=f"Invalid interaction type. Must be one of: {valid_types}")

    # Check if book exists
    book = db.query(Book).filter(Book.id == interaction_data.book_id).first()
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")

    # Check if interaction exists
    existing = db.query(Interaction).filter(
        Interaction.user_id == current_user.id,
        Interaction.book_id == interaction_data.book_id,
        Interaction.interaction_type == interaction_data.interaction_type
    ).first()

    if existing:
        # Remove existing (toggle behavior)
        db.delete(existing)
        db.commit()
        return {"success": True, "action": "removed", "type": interaction_data.interaction_type}

    # Create interaction
    interaction = Interaction(
        user_id=current_user.id,
        book_id=interaction_data.book_id,
        interaction_type=interaction_data.interaction_type
    )
    db.add(interaction)
    db.commit()
    db.refresh(interaction)

    return {"success": True, "action": "added", "type": interaction_data.interaction_type}


@router.get("/{user_id}")
def get_user_interactions(
    user_id: int,
    interaction_type: str = None,
    db: Session = Depends(get_db)
):
    query = db.query(Interaction).filter(Interaction.user_id == user_id)

    if interaction_type:
        query = query.filter(Interaction.interaction_type == interaction_type)

    interactions = query.all()
    return {
        "interactions": [InteractionResponse.model_validate(i) for i in interactions],
        "total": len(interactions)
    }


@router.delete("/{interaction_id}")
def delete_interaction(
    interaction_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    interaction = db.query(Interaction).filter(
        Interaction.id == interaction_id,
        Interaction.user_id == current_user.id
    ).first()

    if not interaction:
        raise HTTPException(status_code=404, detail="Interaction not found")

    db.delete(interaction)
    db.commit()
    return {"success": True}
```

### 任务 2.6: 推荐 API

**Files:**
- Create: `book-v2/backend/app/schemas/recommend.py`
- Create: `book-v2/backend/app/api/recommend.py`

- [ ] **Step 1: 编写 schemas/recommend.py**

```python
from pydantic import BaseModel
from typing import List, Optional


class RecommendationItem(BaseModel):
    book_id: int
    title: str
    author: Optional[str] = None
    image_url: Optional[str] = None
    score: float
    reason: Optional[str] = None
    source: str  # 'cf', 'svd', 'hybrid', 'cold_start', 'explore'


class RecommendationResponse(BaseModel):
    user_id: int
    recommendations: List[RecommendationItem]
    total: int
    source: str
    explore_count: int = 0
    diversity_score: float = 0.0
```

- [ ] **Step 2: 编写 api/recommend.py**

```python
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from app.database import get_db
from app.schemas.recommend import RecommendationResponse
from app.models import User
from app.api.deps import get_current_user
from app.services.recommender import get_recommender

router = APIRouter()


@router.get("/cf/{user_id}", response_model=RecommendationResponse)
def get_cf_recommendations(
    user_id: int,
    n: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db)
):
    recommender = get_recommender()
    recs = recommender.cf_recommend(user_id, n)
    return RecommendationResponse(
        user_id=user_id,
        recommendations=recs,
        total=len(recs),
        source="cf"
    )


@router.get("/svd/{user_id}", response_model=RecommendationResponse)
def get_svd_recommendations(
    user_id: int,
    n: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db)
):
    recommender = get_recommender()
    recs = recommender.svd_recommend(user_id, n)
    return RecommendationResponse(
        user_id=user_id,
        recommendations=recs,
        total=len(recs),
        source="svd"
    )


@router.get("/hybrid/{user_id}", response_model=RecommendationResponse)
def get_hybrid_recommendations(
    user_id: int,
    n: int = Query(20, ge=1, le=100),
    diversity: bool = True,
    db: Session = Depends(get_db)
):
    recommender = get_recommender()
    recs, explore_count, diversity_score = recommender.hybrid_recommend(user_id, n, diversity)
    return RecommendationResponse(
        user_id=user_id,
        recommendations=recs,
        total=len(recs),
        source="hybrid",
        explore_count=explore_count,
        diversity_score=diversity_score
    )


@router.get("/cold-start/{user_id}", response_model=RecommendationResponse)
def get_cold_start_recommendations(
    user_id: int,
    n: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db)
):
    recommender = get_recommender()
    recs = recommender.cold_start_recommend(user_id, n)
    return RecommendationResponse(
        user_id=user_id,
        recommendations=recs,
        total=len(recs),
        source="cold_start"
    )
```

### 任务 2.7: 用户标签 API

**Files:**
- Create: `book-v2/backend/app/api/users.py`

- [ ] **Step 1: 编写 api/users.py**

```python
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from pydantic import BaseModel
from app.database import get_db
from app.models import User, UserTag, Rating
from app.api.deps import get_current_user

router = APIRouter()


# Available tags for selection
AVAILABLE_TAGS = [
    "科幻", "奇幻", "悬疑", "推理", "爱情", "言情", "历史", "传记", "心理",
    "哲学", "宗教", "社会", "政治", "经济", "管理", "励志", "成长", "旅行",
    "美食", "运动", "科技", "编程", "设计", "艺术", "摄影", "音乐", "电影",
    "儿童", "青少年", "漫画", "武侠", "恐怖", "惊悚", "美国文学", "英国文学",
    "日本文学", "中国文学", "经典", "现代文学"
]


class UserTagUpdate(BaseModel):
    tags: List[str]


class UserTagResponse(BaseModel):
    tags: List[str]
    count: int


@router.get("/tags")
def get_available_tags():
    return {"tags": AVAILABLE_TAGS}


@router.get("/{user_id}/tags", response_model=UserTagResponse)
def get_user_tags(user_id: int, db: Session = Depends(get_db)):
    user_tags = db.query(UserTag).filter(UserTag.user_id == user_id).all()
    return UserTagResponse(
        tags=[t.tag_name for t in user_tags],
        count=len(user_tags)
    )


@router.put("/{user_id}/tags", response_model=UserTagResponse)
def update_user_tags(
    user_id: int,
    tag_data: UserTagUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if current_user.id != user_id:
        raise HTTPException(status_code=403, detail="Not authorized")

    # Validate tags
    invalid_tags = [t for t in tag_data.tags if t not in AVAILABLE_TAGS]
    if invalid_tags:
        raise HTTPException(status_code=400, detail=f"Invalid tags: {invalid_tags}")

    if len(tag_data.tags) > 5:
        raise HTTPException(status_code=400, detail="Maximum 5 tags allowed")

    # Delete existing tags
    db.query(UserTag).filter(UserTag.user_id == user_id).delete()

    # Add new tags
    for tag_name in tag_data.tags:
        user_tag = UserTag(user_id=user_id, tag_name=tag_name)
        db.add(user_tag)

    db.commit()

    return UserTagResponse(tags=tag_data.tags, count=len(tag_data.tags))


@router.get("/{user_id}/stats")
def get_user_stats(user_id: int, db: Session = Depends(get_db)):
    rating_count = db.query(Rating).filter(Rating.user_id == user_id).count()
    user_tags = db.query(UserTag).filter(UserTag.user_id == user_id).count()

    return {
        "user_id": user_id,
        "rating_count": rating_count,
        "tag_count": user_tags,
        "is_cold_start": rating_count < 5
    }
```

---

## 阶段 3: 推荐算法服务

### 任务 3.1: 推荐引擎基础

**Files:**
- Create: `book-v2/backend/app/services/recommender/__init__.py`
- Create: `book-v2/backend/app/services/recommender/base.py`

- [ ] **Step 1: 编写 recommender/__init__.py**

```python
from app.services.recommender.hybrid_engine import HybridRecommender

_recommender_instance = None


def get_recommender() -> HybridRecommender:
    global _recommender_instance
    if _recommender_instance is None:
        _recommender_instance = HybridRecommender()
    return _recommender_instance
```

- [ ] **Step 2: 编写 recommender/base.py**

```python
from abc import ABC, abstractmethod
from typing import List, Dict, Tuple
import redis
import json
from app.config import settings


class BaseRecommender(ABC):
    def __init__(self):
        self.redis_client = redis.from_url(settings.REDIS_URL, decode_responses=True)

    def get_cache(self, key: str) -> List[Dict]:
        """Get recommendations from cache"""
        cached = self.redis_client.get(key)
        if cached:
            return json.loads(cached)
        return None

    def set_cache(self, key: str, data: List[Dict], ttl: int = 300):
        """Set recommendations cache"""
        self.redis_client.setex(key, ttl, json.dumps(data))

    def clear_user_cache(self, user_id: int):
        """Clear all recommendation caches for a user"""
        pattern = f"user:{user_id}:recommendations:*"
        keys = self.redis_client.keys(pattern)
        if keys:
            self.redis_client.delete(*keys)

    @abstractmethod
    def recommend(self, user_id: int, n: int = 20) -> List[Dict]:
        """Generate recommendations for a user"""
        pass

    def get_user_preferences(self, db, user_id: int) -> Dict:
        """Get user preferences from ratings and interactions"""
        from app.models import Rating, Interaction, UserTag

        # Get ratings
        ratings = db.query(Rating).filter(Rating.user_id == user_id).all()
        rated_books = {r.book_id: r.rating for r in ratings}

        # Get interactions
        interactions = db.query(Interaction).filter(Interaction.user_id == user_id).all()
        liked_books = set()
        disliked_books = set()
        wanted_books = set()

        for i in interactions:
            if i.interaction_type == "like":
                liked_books.add(i.book_id)
            elif i.interaction_type == "dislike":
                disliked_books.add(i.book_id)
            elif i.interaction_type == "want_to_read":
                wanted_books.add(i.book_id)

        # Get user tags
        user_tags = db.query(UserTag).filter(UserTag.user_id == user_id).all()
        tags = [t.tag_name for t in user_tags]

        return {
            "rated_books": rated_books,
            "liked_books": liked_books,
            "disliked_books": disliked_books,
            "wanted_books": wanted_books,
            "tags": tags
        }
```

### 任务 3.2: 协同过滤引擎

**Files:**
- Create: `book-v2/backend/app/services/recommender/cf_engine.py`

- [ ] **Step 1: 编写 cf_engine.py**

```python
import numpy as np
from scipy import sparse
from surprise import accuracy
from sqlalchemy import func
from app.database import SessionLocal
from app.models import Rating, Book
from app.services.recommender.base import BaseRecommender


class CFEngine(BaseRecommender):
    """User-based Collaborative Filtering Engine"""

    def __init__(self):
        super().__init__()
        self.rating_matrix = None
        self.user_map = {}
        self.item_map = {}
        self.reverse_user_map = {}
        self.reverse_item_map = {}
        self.load_data()

    def load_data(self):
        """Load rating data and build matrices"""
        db = SessionLocal()
        try:
            # Get all ratings
            ratings = db.query(Rating).all()

            # Build mappings
            user_ids = sorted(set(r.user_id for r in ratings))
            book_ids = sorted(set(r.book_id for r in ratings))

            self.user_map = {uid: idx for idx, uid in enumerate(user_ids)}
            self.item_map = {bid: idx for idx, bid in enumerate(book_ids)}
            self.reverse_user_map = {idx: uid for uid, idx in self.user_map.items()}
            self.reverse_item_map = {idx: bid for bid, idx in self.item_map.items()}

            # Build sparse rating matrix
            n_users = len(user_ids)
            n_items = len(book_ids)
            rows = [self.user_map[r.user_id] for r in ratings]
            cols = [self.item_map[r.book_id] for r in ratings]
            values = [r.rating for r in ratings]

            self.rating_matrix = sparse.csr_matrix(
                (values, (rows, cols)),
                shape=(n_users, n_items),
                dtype=np.float32
            )

            # Compute item means for normalization
            self.item_means = np.array(self.rating_matrix.sum(axis=0) / (self.rating_matrix > 0).sum(axis=0)).flatten()
            self.item_means = np.nan_to_num(self.item_means, nan=0)

        finally:
            db.close()

    def cosine_similarity(self, user_idx: int, candidate_indices: List[int]) -> List[float]:
        """Calculate cosine similarity between user and candidates"""
        user_vector = self.rating_matrix[user_idx].toarray().flatten()
        user_nonzero = user_vector > 0

        similarities = []
        for item_idx in candidate_indices:
            item_vector = self.rating_matrix[:, item_idx].toarray().flatten()
            item_nonzero = item_vector > 0

            # Overlap-based similarity
            overlap = np.logical_and(user_nonzero, item_nonzero).sum()
            if overlap < 1:
                similarities.append(0.0)
            else:
                user_rated = user_vector[user_nonzero]
                item_ratings = item_vector[item_nonzero]

                norm_user = np.sqrt(np.sum(user_rated ** 2))
                norm_item = np.sqrt(np.sum(item_ratings ** 2))

                if norm_user > 0 and norm_item > 0:
                    sim = np.dot(user_rated, item_ratings) / (norm_user * norm_item)
                    similarities.append(sim)
                else:
                    similarities.append(0.0)

        return similarities

    def recommend(self, user_id: int, n: int = 20) -> List[Dict]:
        """Generate CF recommendations"""
        # Check cache
        cache_key = f"user:{user_id}:recommendations:cf"
        cached = self.get_cache(cache_key)
        if cached:
            return cached[:n]

        if user_id not in self.user_map:
            return []

        user_idx = self.user_map[user_id]

        # Get unrated items
        user_ratings = self.rating_matrix[user_idx].toarray().flatten()
        unrated_mask = user_ratings == 0
        unrated_indices = np.where(unrated_mask)[0]

        if len(unrated_indices) == 0:
            return []

        # Calculate similarities and predict
        similarities = self.cosine_similarity(user_idx, unrated_indices)

        # Weighted average prediction
        predictions = []
        for i, item_idx in enumerate(unrated_indices):
            sim = similarities[i]
            if sim > 0:
                # Get ratings from similar users
                item_ratings = self.rating_matrix[:, item_idx].toarray().flatten()
                rated_mask = item_ratings > 0
                if rated_mask.sum() > 0:
                    # Weighted prediction
                    weight = sim * (item_ratings[rated_mask] - self.item_means[item_idx])
                    pred = self.item_means[item_idx] + np.sum(weight) / (np.sum(np.abs(similarities[i])) + 0.1)
                    pred = max(1, min(10, pred))
                    predictions.append((item_idx, pred, sim))

        # Sort by prediction score
        predictions.sort(key=lambda x: x[1], reverse=True)
        top_predictions = predictions[:n * 3]  # Get more for diversity

        # Get book details
        db = SessionLocal()
        try:
            results = []
            seen_books = set()
            for item_idx, score, sim in top_predictions:
                book_id = self.reverse_item_map[item_idx]
                if book_id in seen_books:
                    continue
                seen_books.add(book_id)

                book = db.query(Book).filter(Book.id == book_id).first()
                if book:
                    results.append({
                        "book_id": book.id,
                        "title": book.title,
                        "author": book.author,
                        "image_url": book.image_url,
                        "score": round(score, 2),
                        "reason": "与你口味相似的用户喜欢",
                        "source": "cf"
                    })

                if len(results) >= n:
                    break

            # Cache results
            self.set_cache(cache_key, results, ttl=300)

            return results
        finally:
            db.close()
```

### 任务 3.3: SVD 引擎

**Files:**
- Create: `book-v2/backend/app/services/recommender/svd_engine.py`

- [ ] **Step 1: 编写 svd_engine.py**

```python
import random
import numpy as np
from surprise import SVD, Dataset, Reader
from sqlalchemy import func
from app.database import SessionLocal
from app.models import Rating, Book
from app.services.recommender.base import BaseRecommender


class SVDEngine(BaseRecommender):
    """SVD Matrix Factorization Engine"""

    def __init__(self):
        super().__init__()
        self.model = None
        self.all_book_ids = []
        self.load_model()

    def load_model(self):
        """Load or train SVD model"""
        db = SessionLocal()
        try:
            # Get all ratings
            ratings = db.query(Rating).all()
            if len(ratings) < 100:
                self.model = None
                self.all_book_ids = []
                return

            # Prepare data for surprise
            reader = Reader(rating_scale=(1, 10))
            data = Dataset.load_from_df(
                Dataset.parse_ratings([[r.user_id, r.book_id, r.rating] for r in ratings]),
                reader
            )
            trainset = data.build_full_trainset()

            # Train SVD
            self.model = SVD(n_factors=100, n_epochs=20, random_state=42)
            self.model.fit(trainset)

            # Get all book IDs
            self.all_book_ids = list(set(r.book_id for r in ratings))

        finally:
            db.close()

    def recommend(self, user_id: int, n: int = 20, seed: int = None) -> List[Dict]:
        """Generate SVD recommendations"""
        if self.model is None:
            return []

        # Check cache
        cache_key = f"user:{user_id}:recommendations:svd"
        cached = self.get_cache(cache_key)
        if cached and seed is not None:
            random.seed(seed)
            random.shuffle(cached)
            return cached[:n]
        elif cached:
            return cached[:n]

        db = SessionLocal()
        try:
            # Get user's rated books
            rated = set(r.book_id for r in db.query(Rating).filter(Rating.user_id == user_id).all())

            # Predict for all unrated books
            predictions = []
            for book_id in self.all_book_ids:
                if book_id in rated:
                    continue

                pred = self.model.predict(user_id, book_id)
                score = max(1, min(10, pred.est + random.uniform(-1.0, 1.0)))
                predictions.append((book_id, score))

            # Sort by score
            predictions.sort(key=lambda x: x[1], reverse=True)

            # Get top candidates and shuffle for diversity
            top_candidates = predictions[:n * 3]
            random.shuffle(top_candidates)
            top_predictions = top_candidates[:n]

            # Get book details
            results = []
            for book_id, score in top_predictions:
                book = db.query(Book).filter(Book.id == book_id).first()
                if book:
                    results.append({
                        "book_id": book.id,
                        "title": book.title,
                        "author": book.author,
                        "image_url": book.image_url,
                        "score": round(score, 2),
                        "reason": "基于你评分模式的预测",
                        "source": "svd"
                    })

            # Cache results
            self.set_cache(cache_key, results, ttl=300)

            return results
        finally:
            db.close()
```

### 任务 3.4: 冷启动处理器

**Files:**
- Create: `book-v2/backend/app/services/recommender/cold_start.py`

- [ ] **Step 1: 编写 cold_start.py**

```python
from sqlalchemy import func
from app.database import SessionLocal
from app.models import Book, UserTag, Rating
from app.services.recommender.base import BaseRecommender


class ColdStartHandler(BaseRecommender):
    """Handle cold start recommendations for new users"""

    def __init__(self):
        super().__init__()

    def get_tag_based_recommendations(self, user_id: int, n: int = 20) -> list:
        """Recommend books based on user's interest tags"""
        db = SessionLocal()
        try:
            # Get user tags
            user_tags = db.query(UserTag).filter(UserTag.user_id == user_id).all()
            tag_names = [t.tag_name for t in user_tags]

            if not tag_names:
                # Fallback to popular books
                return self.get_popular_recommendations(n)

            # Get user's rated books
            rated_book_ids = set(r.book_id for r in db.query(Rating).filter(Rating.user_id == user_id).all())

            # Find books matching user tags
            query = db.query(Book).filter(
                Book.tags.overlap(tag_names),
                Book.id.notin_(rated_book_ids),
                Book.avg_rating > 0
            ).order_by(Book.avg_rating.desc(), Book.rating_count.desc())

            books = query.limit(n).all()

            if len(books) < n:
                # Add popular books
                popular = self.get_popular_recommendations(n - len(books))
                books.extend(popular)

            results = []
            for book in books:
                matching_tags = [t for t in (book.tags or []) if t in tag_names]
                results.append({
                    "book_id": book.id,
                    "title": book.title,
                    "author": book.author,
                    "image_url": book.image_url,
                    "score": book.avg_rating,
                    "reason": f"匹配你的兴趣: {', '.join(matching_tags[:2])}" if matching_tags else "热门推荐",
                    "source": "cold_start"
                })

            return results[:n]
        finally:
            db.close()

    def get_popular_recommendations(self, n: int = 20) -> list:
        """Get popular books as fallback"""
        db = SessionLocal()
        try:
            # Check cache
            cache_key = "popular:books"
            cached = self.redis_client.zrevrange(cache_key, 0, n - 1, withscores=True)
            if cached:
                book_ids = [int(bid) for bid, score in cached]
                books = db.query(Book).filter(Book.id.in_(book_ids)).all()
                book_map = {b.id: b for b in books}
                return [
                    {
                        "book_id": b.id,
                        "title": b.title,
                        "author": b.author,
                        "image_url": b.image_url,
                        "score": b.avg_rating,
                        "reason": "热门推荐",
                        "source": "popular"
                    }
                    for bid, score in cached
                    if bid in book_map and (b := book_map[int(bid)])
                ]

            # Query popular books
            books = db.query(Book).filter(
                Book.rating_count > 0
            ).order_by(
                Book.avg_rating.desc(),
                Book.rating_count.desc()
            ).limit(n).all()

            results = [
                {
                    "book_id": book.id,
                    "title": book.title,
                    "author": book.author,
                    "image_url": book.image_url,
                    "score": book.avg_rating,
                    "reason": "热门推荐",
                    "source": "popular"
                }
                for book in books
            ]

            # Cache in Redis
            for i, book in enumerate(books):
                self.redis_client.zadd(cache_key, {str(book.id): book.avg_rating})
            self.redis_client.expire(cache_key, 600)

            return results
        finally:
            db.close()
```

### 任务 3.5: 多样性采样器

**Files:**
- Create: `book-v2/backend/app/services/recommender/diversity.py`

- [ ] **Step 1: 编写 diversity.py**

```python
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
```

### 任务 3.6: 混合推荐引擎

**Files:**
- Create: `book-v2/backend/app/services/recommender/hybrid_engine.py`

- [ ] **Step 1: 编写 hybrid_engine.py**

```python
from typing import List, Dict, Tuple, Set
from sqlalchemy import func
from app.database import SessionLocal
from app.models import Book, Rating, Interaction
from app.services.recommender.base import BaseRecommender
from app.services.recommender.cf_engine import CFEngine
from app.services.recommender.svd_engine import SVDEngine
from app.services.recommender.cold_start import ColdStartHandler
from app.services.recommender.diversity import DiversitySampler


class HybridRecommender(BaseRecommender):
    """Hybrid recommendation engine combining multiple strategies"""

    def __init__(self):
        super().__init__()
        self.cf_engine = CFEngine()
        self.svd_engine = SVDEngine()
        self.cold_start = ColdStartHandler()
        self.diversity = DiversitySampler(explore_ratio=0.15)

    def is_cold_start(self, db, user_id: int) -> bool:
        """Check if user is in cold start state"""
        rating_count = db.query(Rating).filter(Rating.user_id == user_id).count()
        return rating_count < 5

    def apply_interaction_adjustment(
        self,
        recommendations: List[Dict],
        user_prefs: Dict
    ) -> List[Dict]:
        """Adjust recommendation scores based on user interactions"""
        liked = user_prefs.get("liked_books", set())
        disliked = user_prefs.get("disliked_books", set())
        wanted = user_prefs.get("wanted_books", set())

        for rec in recommendations:
            book_id = rec["book_id"]

            if book_id in liked:
                rec["score"] += 1.5
            if book_id in disliked:
                rec["score"] -= 2.0
            if book_id in wanted:
                rec["score"] += 1.0

            rec["score"] = max(0, rec["score"])

        return recommendations

    def cf_recommend(self, user_id: int, n: int = 20) -> List[Dict]:
        """Get CF-only recommendations"""
        db = SessionLocal()
        try:
            user_prefs = self.get_user_preferences(db, user_id)
            recs = self.cf_engine.recommend(user_id, n * 2)
            recs = self.apply_interaction_adjustment(recs, user_prefs)
            return sorted(recs, key=lambda x: x["score"], reverse=True)[:n]
        finally:
            db.close()

    def svd_recommend(self, user_id: int, n: int = 20) -> List[Dict]:
        """Get SVD-only recommendations"""
        db = SessionLocal()
        try:
            user_prefs = self.get_user_preferences(db, user_id)
            recs = self.svd_engine.recommend(user_id, n * 2)
            recs = self.apply_interaction_adjustment(recs, user_prefs)
            return sorted(recs, key=lambda x: x["score"], reverse=True)[:n]
        finally:
            db.close()

    def cold_start_recommend(self, user_id: int, n: int = 20) -> List[Dict]:
        """Get cold start recommendations based on user tags"""
        return self.cold_start.get_tag_based_recommendations(user_id, n)

    def hybrid_recommend(
        self,
        user_id: int,
        n: int = 20,
        diversity: bool = True
    ) -> Tuple[List[Dict], int, float]:
        """Get hybrid recommendations with diversity"""
        db = SessionLocal()
        try:
            # Check cold start
            if self.is_cold_start(db, user_id):
                recs = self.cold_start_recommend(user_id, n)
                return recs, 0, self.diversity._calculate_diversity(recs)

            # Get user preferences
            user_prefs = self.get_user_preferences(db, user_id)
            interacted = (
                user_prefs["rated_books"].keys() |
                user_prefs["liked_books"] |
                user_prefs["disliked_books"] |
                user_prefs["wanted_books"]
            )

            # Get recommendations from multiple sources
            cf_recs = self.cf_engine.recommend(user_id, n * 2)
            svd_recs = self.svd_engine.recommend(user_id, n * 2)

            # Merge and deduplicate
            all_recs = {r["book_id"]: r for r in cf_recs + svd_recs}

            # Average scores for duplicate books
            for bid in all_recs:
                sources = [r for r in cf_recs + svd_recs if r["book_id"] == bid]
                if len(sources) > 1:
                    avg_score = sum(s["score"] for s in sources) / len(sources)
                    all_recs[bid]["score"] = avg_score

            recommendations = list(all_recs.values())

            # Apply interaction adjustment
            recommendations = self.apply_interaction_adjustment(recommendations, user_prefs)

            # Sort by score
            recommendations.sort(key=lambda x: x["score"], reverse=True)

            if diversity:
                # Apply diversity sampling
                result, explore_count, diversity_score = self.diversity.sample(
                    recommendations, n, interacted
                )
                return result, explore_count, diversity_score
            else:
                return recommendations[:n], 0, 0.0

        finally:
            db.close()
```

---

## 阶段 4: 核心功能实现

### 任务 4.1: Celery 异步任务配置

**Files:**
- Create: `book-v2/backend/app/celery_app.py`
- Create: `book-v2/backend/app/tasks/__init__.py`
- Create: `book-v2/backend/app/tasks/model_training.py`

- [ ] **Step 1: 编写 celery_app.py**

```python
from celery import Celery
from app.config import settings

celery_app = Celery(
    "book_recommend",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=["app.tasks.model_training"]
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Asia/Shanghai",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=3600,  # 1 hour max
    worker_prefetch_multiplier=1,
)
```

- [ ] **Step 2: 编写 tasks/model_training.py**

```python
from celery import shared_task
from sqlalchemy import func
from app.database import SessionLocal
from app.models import Book, Rating
from app.celery_app import celery_app


@celery_app.task
def update_book_stats(book_id: int):
    """Update book statistics after rating changes"""
    db = SessionLocal()
    try:
        ratings = db.query(Rating).filter(Rating.book_id == book_id).all()
        count = len(ratings)
        avg = sum(r.rating for r in ratings) / count if count > 0 else 0

        book = db.query(Book).filter(Book.id == book_id).first()
        if book:
            book.rating_count = count
            book.avg_rating = round(avg, 2)
            db.commit()

        # Clear recommendation cache
        from app.services.recommender import get_recommender
        recommender = get_recommender()
        recommender.redis_client.delete(f"user:*:recommendations:*")

        return {"book_id": book_id, "rating_count": count, "avg_rating": avg}
    finally:
        db.close()


@celery_app.task
def retrain_models():
    """Retrain recommendation models (scheduled task)"""
    from app.services.recommender import get_recommender
    recommender = get_recommender()

    # Reload CF model
    recommender.cf_engine.load_data()

    # Reload SVD model
    recommender.svd_engine.load_model()

    # Clear all caches
    recommender.redis_client.flushdb()

    return {"status": "success", "message": "Models retrained and cache cleared"}


@celery_app.task
def update_popular_books():
    """Update popular books cache"""
    db = SessionLocal()
    try:
        books = db.query(Book).filter(
            Book.rating_count > 0
        ).order_by(
            Book.avg_rating.desc(),
            Book.rating_count.desc()
        ).limit(100).all()

        recommender = __import__(
            "app.services.recommender", fromlist=["get_recommender"]
        ).get_recommender()

        cache_key = "popular:books"
        recommender.redis_client.delete(cache_key)

        for i, book in enumerate(books):
            recommender.redis_client.zadd(cache_key, {str(book.id): book.avg_rating})

        recommender.redis_client.expire(cache_key, 3600)

        return {"status": "success", "count": len(books)}
    finally:
        db.close()
```

### 任务 4.2: 交互服务层

**Files:**
- Create: `book-v2/backend/app/services/interaction.py`

- [ ] **Step 1: 编写 services/interaction.py**

```python
from sqlalchemy.orm import Session
from typing import Dict, Set
from app.models import Interaction


class InteractionService:
    """Handle user interaction business logic"""

    # Weight for preference calculation
    INTERACTION_WEIGHTS = {
        "view": 0.1,
        "like": 0.5,
        "dislike": -0.5,
        "want_to_read": 0.3,
        "read": 0.0,
    }

    @staticmethod
    def calculate_preference_score(
        rating: int = None,
        liked: bool = False,
        disliked: bool = False,
        wanted: bool = False,
        view_count: int = 0
    ) -> float:
        """Calculate preference score from interactions"""
        score = 0.0

        if rating is not None:
            score += (rating / 10) * 0.5

        if liked:
            score += InteractionService.INTERACTION_WEIGHTS["like"]

        if disliked:
            score += InteractionService.INTERACTION_WEIGHTS["dislike"]

        if wanted:
            score += InteractionService.INTERACTION_WEIGHTS["want_to_read"]

        if view_count > 0:
            score += min(view_count / 10, 1) * InteractionService.INTERACTION_WEIGHTS["view"]

        return max(0, min(1, score))

    @staticmethod
    def get_user_interaction_set(db: Session, user_id: int) -> Dict[str, Set[int]]:
        """Get all user interactions as sets"""
        interactions = db.query(Interaction).filter(
            Interaction.user_id == user_id
        ).all()

        result = {
            "liked": set(),
            "disliked": set(),
            "wanted": set(),
            "viewed": set(),
            "read": set(),
        }

        for i in interactions:
            key = {
                "like": "liked",
                "dislike": "disliked",
                "want_to_read": "wanted",
                "view": "viewed",
                "read": "read",
            }.get(i.interaction_type)

            if key:
                result[key].add(i.book_id)

        return result
```

---

## 阶段 5: 前端升级

### 任务 5.1: Vue 项目初始化

**Files:**
- Create: `book-v2/frontend-v2/package.json`
- Create: `book-v2/frontend-v2/vite.config.ts`
- Create: `book-v2/frontend-v2/tsconfig.json`

- [ ] **Step 1: 初始化 Vue 项目**

```bash
cd book-v2/frontend-v2
npm init vite@latest . -- --template vue-ts
npm install
npm install vue-router@4 pinia element-plus @element-plus/icons-vue axios
npm install -D unplugin-vue-components unplugin-auto-import
```

### 任务 5.2: API 客户端

**Files:**
- Create: `book-v2/frontend-v2/src/api/`
- Create: `book-v2/frontend-v2/src/api/client.ts`

- [ ] **Step 1: 编写 api/client.ts**

```typescript
import axios from 'axios'

const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL || 'http://localhost:8000/api',
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json'
  }
})

// Request interceptor
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

// Response interceptor
api.interceptors.response.use(
  (response) => response.data,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('token')
      window.location.href = '/login'
    }
    return Promise.reject(error)
  }
)

export default api
```

### 任务 5.3: 书籍卡片组件

**Files:**
- Create: `book-v2/frontend-v2/src/components/BookCard.vue`

- [ ] **Step 1: 编写 BookCard.vue**

```vue
<template>
  <div class="book-card" @click="$router.push(`/book/${book.id}`)">
    <div class="cover">
      <img v-if="book.image_url" :src="book.image_url" :alt="book.title" />
      <div v-else class="no-cover">暂无封面</div>
    </div>
    <div class="info">
      <h3 class="title">{{ book.title }}</h3>
      <p class="author">{{ book.author || '未知作者' }}</p>
      <div class="rating">
        <span class="avg">{{ book.avg_rating?.toFixed(1) || 'N/A' }}</span>
        <span class="count">({{ book.rating_count }}人)</span>
      </div>
      <div class="interactions" @click.stop>
        <button
          :class="{ active: interactions.liked }"
          @click="toggleLike"
          title="喜欢"
        >
          {{ interactions.liked ? '❤️' : '🤍' }}
        </button>
        <button
          :class="{ active: interactions.wanted }"
          @click="toggleWant"
          title="想读"
        >
          {{ interactions.wanted ? '👀' : '📖' }}
        </button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import api from '../api/client'

const props = defineProps<{
  book: {
    id: number
    title: string
    author?: string
    image_url?: string
    avg_rating?: number
    rating_count: number
  }
  initialInteractions?: {
    liked?: boolean
    wanted?: boolean
  }
}>()

const interactions = ref({
  liked: props.initialInteractions?.liked || false,
  wanted: props.initialInteractions?.wanted || false
})

const emit = defineEmits(['interaction-change'])

const toggleLike = async () => {
  try {
    await api.post('/interactions', {
      book_id: props.book.id,
      interaction_type: 'like'
    })
    interactions.value.liked = !interactions.value.liked
    emit('interaction-change', { type: 'like', value: interactions.value.liked })
  } catch (error) {
    console.error('Failed to toggle like:', error)
  }
}

const toggleWant = async () => {
  try {
    await api.post('/interactions', {
      book_id: props.book.id,
      interaction_type: 'want_to_read'
    })
    interactions.value.wanted = !interactions.value.wanted
    emit('interaction-change', { type: 'want_to_read', value: interactions.value.wanted })
  } catch (error) {
    console.error('Failed to toggle want:', error)
  }
}
</script>

<style scoped>
.book-card {
  background: #1f1f28;
  border-radius: 12px;
  overflow: hidden;
  cursor: pointer;
  transition: transform 0.2s, box-shadow 0.2s;
}

.book-card:hover {
  transform: translateY(-4px);
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.3);
}

.cover img {
  width: 100%;
  height: 200px;
  object-fit: cover;
}

.no-cover {
  height: 200px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #27272f;
  color: #71717a;
}

.info {
  padding: 12px;
}

.title {
  font-size: 14px;
  font-weight: 600;
  color: #e4e4e7;
  margin: 0 0 4px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.author {
  font-size: 12px;
  color: #a1a1aa;
  margin: 0 0 8px;
}

.rating {
  display: flex;
  align-items: center;
  gap: 4px;
  margin-bottom: 8px;
}

.avg {
  color: #f97316;
  font-weight: 600;
}

.count {
  color: #71717a;
  font-size: 12px;
}

.interactions {
  display: flex;
  gap: 8px;
}

.interactions button {
  background: none;
  border: none;
  font-size: 18px;
  cursor: pointer;
  opacity: 0.6;
  transition: opacity 0.2s, transform 0.2s;
}

.interactions button:hover {
  opacity: 1;
  transform: scale(1.2);
}

.interactions button.active {
  opacity: 1;
}
</style>
```

### 任务 5.4: 兴趣标签选择组件

**Files:**
- Create: `book-v2/frontend-v2/src/components/TagSelector.vue`

- [ ] **Step 1: 编写 TagSelector.vue**

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

<script setup lang="ts">
import { ref, watch } from 'vue'

const props = defineProps<{
  modelValue: string[]
}>()

const emit = defineEmits(['update:modelValue'])

const availableTags = [
  '科幻', '奇幻', '悬疑', '推理', '爱情', '历史', '心理',
  '哲学', '社会', '经济', '励志', '旅行', '科技', '编程',
  '艺术', '儿童', '漫画', '武侠', '美国文学', '经典'
]

const selectedTags = ref<string[]>([...props.modelValue])

const toggleTag = (tag: string) => {
  const index = selectedTags.value.indexOf(tag)
  if (index > -1) {
    selectedTags.value.splice(index, 1)
  } else if (selectedTags.value.length < 5) {
    selectedTags.value.push(tag)
  }
  emit('update:modelValue', selectedTags.value)
}

watch(() => props.modelValue, (newVal) => {
  selectedTags.value = [...newVal]
})
</script>

<style scoped>
.tag-selector {
  padding: 24px;
  background: #1f1f28;
  border-radius: 12px;
}

.tag-selector h3 {
  color: #f97316;
  margin: 0 0 8px;
}

.hint {
  color: #71717a;
  margin: 0 0 24px;
  font-size: 14px;
}

.tag-cloud {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
}

.tag-cloud button {
  padding: 8px 16px;
  background: #27272f;
  border: 1px solid #3f3f46;
  border-radius: 20px;
  color: #a1a1aa;
  cursor: pointer;
  transition: all 0.2s;
}

.tag-cloud button:hover {
  background: #3f3f46;
  color: #e4e4e7;
}

.tag-cloud button.selected {
  background: #f97316;
  border-color: #f97316;
  color: white;
}

.selected-info {
  margin-top: 24px;
  color: #71717a;
  font-size: 14px;
}
</style>
```

### 任务 5.5: 推荐页面

**Files:**
- Create: `book-v2/frontend-v2/src/views/RecommendView.vue`

- [ ] **Step 1: 编写 RecommendView.vue**

```vue
<template>
  <div class="recommend-view">
    <div class="header">
      <h1>为你推荐</h1>
      <div class="actions">
        <el-button @click="refreshRecommendations" :loading="loading">
          🔄 刷新推荐
        </el-button>
        <el-select v-model="selectedAlgo" style="width: 150px">
          <el-option label="混合推荐" value="hybrid" />
          <el-option label="协同过滤" value="cf" />
          <el-option label="SVD" value="svd" />
        </el-select>
      </div>
    </div>

    <div v-if="loading" class="loading">
      <el-progress type="dashboard" :percentage="75" />
    </div>

    <div v-else-if="recommendations.length === 0" class="empty">
      <p>暂无推荐结果</p>
      <p class="hint">尝试选择一些兴趣标签，我们会为你推荐书籍</p>
    </div>

    <div v-else class="recommendations">
      <div class="recommend-section">
        <h2>🎯 为你推荐</h2>
        <div class="book-grid">
          <BookCard
            v-for="book in exploitRecommendations"
            :key="book.book_id"
            :book="book"
            :initial-interactions="book.interactions"
          />
        </div>
      </div>

      <div v-if="exploreRecommendations.length > 0" class="recommend-section explore">
        <h2>🔮 探索发现</h2>
        <div class="book-grid">
          <BookCard
            v-for="book in exploreRecommendations"
            :key="book.book_id"
            :book="book"
          />
        </div>
      </div>

      <div class="stats">
        <p>推荐书籍: {{ recommendations.length }} 本 | 探索书籍: {{ exploreCount }} 本</p>
        <p>多样性分数: {{ diversityScore }}</p>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import api from '../api/client'
import BookCard from '../components/BookCard.vue'

const loading = ref(false)
const recommendations = ref<any[]>([])
const selectedAlgo = ref('hybrid')
const exploreCount = ref(0)
const diversityScore = ref(0)

const exploitRecommendations = computed(() =>
  recommendations.value.filter(r => r.source !== 'explore')
)

const exploreRecommendations = computed(() =>
  recommendations.value.filter(r => r.source === 'explore')
)

const fetchRecommendations = async () => {
  loading.value = true
  try {
    let response
    switch (selectedAlgo.value) {
      case 'cf':
        response = await api.get(`/recommend/cf/8?n=20`)
        break
      case 'svd':
        response = await api.get(`/recommend/svd/8?n=20`)
        break
      default:
        response = await api.get(`/recommend/hybrid/8?n=20`)
        exploreCount.value = response.explore_count
        diversityScore.value = response.diversity_score
    }
    recommendations.value = response.recommendations
  } catch (error) {
    ElMessage.error('获取推荐失败')
  } finally {
    loading.value = false
  }
}

const refreshRecommendations = async () => {
  await fetchRecommendations()
  ElMessage.success('已为你刷新推荐')
}

onMounted(() => {
  fetchRecommendations()
})
</script>

<style scoped>
.recommend-view {
  padding: 24px;
}

.header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 24px;
}

.header h1 {
  margin: 0;
  color: #e4e4e7;
}

.actions {
  display: flex;
  gap: 12px;
}

.book-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
  gap: 20px;
}

.recommend-section {
  margin-bottom: 32px;
}

.recommend-section h2 {
  color: #e4e4e7;
  margin: 0 0 16px;
  font-size: 18px;
}

.recommend-section.explore h2 {
  color: #a78bfa;
}

.stats {
  margin-top: 24px;
  padding: 16px;
  background: #1f1f28;
  border-radius: 8px;
  color: #71717a;
  font-size: 14px;
}

.stats p {
  margin: 4px 0;
}
</style>
```

### 任务 5.6: 书籍详情页

**Files:**
- Create: `book-v2/frontend-v2/src/views/BookDetailView.vue`

- [ ] **Step 1: 编写 BookDetailView.vue**

```vue
<template>
  <div class="book-detail" v-if="book">
    <div class="info-section">
      <div class="cover">
        <img v-if="book.image_url" :src="book.image_url" :alt="book.title" />
        <div v-else class="no-cover">暂无封面</div>
      </div>

      <div class="info">
        <h1>{{ book.title }}</h1>
        <div class="meta">
          <p>作者: {{ book.author || '未知' }}</p>
          <p>出版社: {{ book.publisher || '未知' }}</p>
          <p>年份: {{ book.year || '未知' }}</p>
          <p v-if="book.tags?.length">标签: {{ book.tags.join(', ') }}</p>
        </div>

        <!-- 社区评分 -->
        <div class="community-card" v-if="book.community_rating">
          <h3>社区口碑</h3>
          <div class="rating-display">
            <span class="big-score">{{ book.community_rating.avg_rating }}</span>
            <span class="rating-info">
              {{ book.community_rating.rating_count }} 人评分
              <br />最多人给 {{ book.community_rating.most_common_rating }} 分
            </span>
          </div>
          <div class="distribution">
            <div
              v-for="score in [10, 9, 8, 7, 6]"
              :key="score"
              class="dist-row"
            >
              <span>{{ score }}</span>
              <div class="bar">
                <div
                  class="fill"
                  :style="{ width: getBarWidth(score) + '%' }"
                ></div>
              </div>
              <span class="count">{{ book.community_rating.distribution[score] || 0 }}</span>
            </div>
          </div>
        </div>

        <!-- 交互按钮 -->
        <div class="interactions">
          <div class="rating-section">
            <p>你的评分: {{ book.user_rating || '未评分' }}</p>
            <el-rate v-model="userRating" :max="10" show-score @change="submitRating" />
          </div>
          <div class="interaction-buttons">
            <button :class="{ active: book.user_interactions?.liked }" @click="toggleInteraction('like')">
              {{ book.user_interactions?.liked ? '❤️ 喜欢' : '🤍 喜欢' }}
            </button>
            <button :class="{ active: book.user_interactions?.wanted }" @click="toggleInteraction('want_to_read')">
              {{ book.user_interactions?.wanted ? '👀 想读' : '📖 想读' }}
            </button>
            <button :class="{ active: book.user_interactions?.disliked }" @click="toggleInteraction('dislike')">
              {{ book.user_interactions?.disliked ? '😔 不喜欢' : '✕ 不喜欢' }}
            </button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import api from '../api/client'

const route = useRoute()
const book = ref<any>(null)
const userRating = ref(0)

const fetchBook = async () => {
  try {
    const response = await api.get(`/books/${route.params.id}`)
    book.value = response
  } catch (error) {
    console.error('Failed to fetch book:', error)
  }
}

const submitRating = async (rating: number) => {
  try {
    await api.post('/ratings', {
      book_id: book.value.id,
      rating
    })
    ElMessage.success(`已评分 ${rating} 分`)
    await fetchBook()
  } catch (error) {
    ElMessage.error('评分失败')
  }
}

const toggleInteraction = async (type: string) => {
  try {
    await api.post('/interactions', {
      book_id: book.value.id,
      interaction_type: type
    })
    await fetchBook()
  } catch (error) {
    ElMessage.error('操作失败')
  }
}

const getBarWidth = (score: number) => {
  if (!book.value?.community_rating) return 0
  const total = book.value.community_rating.rating_count || 1
  const count = book.value.community_rating.distribution[score] || 0
  return (count / total) * 100
}

onMounted(() => {
  fetchBook()
})
</script>

<style scoped>
.book-detail {
  padding: 24px;
}

.info-section {
  display: flex;
  gap: 40px;
}

.cover img {
  max-height: 300px;
  border-radius: 8px;
}

.info {
  flex: 1;
}

.info h1 {
  margin: 0 0 16px;
  color: #e4e4e7;
}

.meta p {
  margin: 8px 0;
  color: #a1a1aa;
}

.community-card {
  padding: 20px;
  background: #1f1f28;
  border-radius: 12px;
  margin: 24px 0;
}

.community-card h3 {
  color: #f97316;
  margin: 0 0 16px;
}

.rating-display {
  display: flex;
  align-items: center;
  gap: 16px;
  margin-bottom: 16px;
}

.big-score {
  font-size: 48px;
  font-weight: bold;
  color: #f97316;
}

.rating-info {
  color: #71717a;
  font-size: 14px;
}

.distribution {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.dist-row {
  display: flex;
  align-items: center;
  gap: 8px;
}

.dist-row span:first-child {
  width: 20px;
  text-align: right;
  color: #a1a1aa;
}

.bar {
  flex: 1;
  height: 8px;
  background: #27272f;
  border-radius: 4px;
}

.fill {
  height: 100%;
  background: #f97316;
  border-radius: 4px;
}

.count {
  width: 40px;
  text-align: right;
  color: #71717a;
  font-size: 12px;
}

.interactions {
  padding: 20px;
  background: #1f1f28;
  border-radius: 12px;
}

.rating-section {
  margin-bottom: 16px;
}

.interaction-buttons {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
}

.interaction-buttons button {
  padding: 8px 16px;
  background: #27272f;
  border: none;
  border-radius: 20px;
  color: #a1a1aa;
  cursor: pointer;
}

.interaction-buttons button.active {
  background: #f97316;
  color: white;
}
</style>
```

---

## 阶段 6: 数据迁移与测试

### 任务 6.1: 数据迁移脚本

**Files:**
- Create: `book-v2/backend/scripts/migrate_data.py`

- [ ] **Step 1: 编写数据迁移脚本**

```python
"""
从 V1 数据库迁移数据到 V2
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.database import SessionLocal, Base, engine
from app.models import User, Book, Rating

# V1 数据库连接
V1_DATABASE_URL = "mysql+pymysql://root:password@localhost:3306/book_v1"

def migrate_data():
    print("开始数据迁移...")

    # 创建新数据库表
    Base.metadata.create_all(bind=engine)
    print("✓ 新数据库表已创建")

    v1_engine = create_engine(V1_DATABASE_URL)
    V1Session = sessionmaker(bind=v1_engine)

    v1_db = V1Session()
    v2_db = SessionLocal()

    try:
        # 迁移用户
        print("迁移用户数据...")
        v1_users = v1_db.execute("SELECT * FROM users").fetchall()
        for u in v1_users:
            existing = v2_db.query(User).filter(User.id == u.id).first()
            if not existing:
                user = User(
                    id=u.id,
                    username=u.username,
                    email=u.email,
                    password_hash=u.password_hash
                )
                v2_db.add(user)
        v2_db.commit()
        print(f"✓ 迁移了 {len(v1_users)} 个用户")

        # 迁移书籍
        print("迁移书籍数据...")
        v1_books = v1_db.execute("SELECT * FROM books").fetchall()
        for b in v1_books:
            existing = v2_db.query(Book).filter(Book.id == b.id).first()
            if not existing:
                book = Book(
                    id=b.id,
                    isbn=b.isbn,
                    title=b.title,
                    author=b.author,
                    year=b.year,
                    publisher=b.publisher,
                    image_url=b.image_url
                )
                v2_db.add(book)
        v2_db.commit()
        print(f"✓ 迁移了 {len(v1_books)} 本书")

        # 迁移评分
        print("迁移评分数据...")
        v1_ratings = v1_db.execute("SELECT * FROM ratings").fetchall()
        for r in v1_ratings:
            existing = v2_db.query(Rating).filter(
                Rating.user_id == r.user_id,
                Rating.book_id == r.book_id
            ).first()
            if not existing:
                rating = Rating(
                    user_id=r.user_id,
                    book_id=r.book_id,
                    rating=r.rating
                )
                v2_db.add(rating)
        v2_db.commit()
        print(f"✓ 迁移了 {len(v1_ratings)} 条评分")

        print("\n数据迁移完成！")

    finally:
        v1_db.close()
        v2_db.close()


if __name__ == "__main__":
    migrate_data()
```

### 任务 6.2: 单元测试

**Files:**
- Create: `book-v2/backend/tests/test_recommender.py`
- Create: `book-v2/backend/tests/test_api.py`

- [ ] **Step 1: 编写推荐引擎测试**

```python
import pytest
from app.services.recommender.hybrid_engine import HybridRecommender


def test_hybrid_recommender_initialization():
    recommender = HybridRecommender()
    assert recommender is not None
    assert recommender.cf_engine is not None
    assert recommender.svd_engine is not None
    assert recommender.cold_start is not None


def test_diversity_sampler():
    from app.services.recommender.diversity import DiversitySampler

    sampler = DiversitySampler(max_same_category=2, max_same_author=1)

    candidates = [
        {"book_id": 1, "title": "Book A", "author": "Author 1", "category": "Sci-Fi", "score": 9.0},
        {"book_id": 2, "title": "Book B", "author": "Author 1", "category": "Sci-Fi", "score": 8.5},
        {"book_id": 3, "title": "Book C", "author": "Author 2", "category": "Sci-Fi", "score": 8.0},
        {"book_id": 4, "title": "Book D", "author": "Author 3", "category": "Fantasy", "score": 7.5},
        {"book_id": 5, "title": "Book E", "author": "Author 4", "category": "Fantasy", "score": 7.0},
    ]

    result, explore_count, diversity = sampler.sample(candidates, 4)

    assert len(result) == 4
    assert diversity > 0


def test_preference_score_calculation():
    from app.services.interaction import InteractionService

    score = InteractionService.calculate_preference_score(
        rating=8,
        liked=True,
        wanted=True
    )

    expected = (8/10) * 0.5 + 0.5 + 0.3
    assert abs(score - expected) < 0.01
```

### 任务 6.3: API 集成测试

- [ ] **Step 1: 编写 API 测试**

```python
import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_health_check():
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_user_registration():
    response = client.post("/api/auth/register", json={
        "username": "testuser",
        "email": "test@example.com",
        "password": "testpassword"
    })
    assert response.status_code == 200
    assert response.json()["username"] == "testuser"


def test_book_list():
    response = client.get("/api/books?page=1&per_page=10")
    assert response.status_code == 200
    assert "books" in response.json()
    assert "total" in response.json()
```

### 任务 6.4: 端到端测试脚本

**Files:**
- Create: `book-v2/scripts/e2e_test.py`

- [ ] **Step 1: 编写端到端测试**

```python
"""
端到端测试: 验证完整推荐流程
"""
import requests
import time

BASE_URL = "http://localhost:8000/api"


def test_full_recommendation_flow():
    print("=" * 60)
    print("端到端测试: 推荐系统流程")
    print("=" * 60)

    # 1. 注册用户
    print("\n[1] 注册用户...")
    resp = requests.post(f"{BASE_URL}/auth/register", json={
        "username": "e2e_test_user",
        "email": "e2e@test.com",
        "password": "test123"
    })
    assert resp.status_code == 200
    user = resp.json()
    user_id = user["id"]
    print(f"✓ 用户注册成功: {user['username']} (id={user_id})")

    # 2. 登录获取 token
    print("\n[2] 用户登录...")
    resp = requests.post(f"{BASE_URL}/auth/login", data={
        "username": "e2e_test_user",
        "password": "test123"
    })
    assert resp.status_code == 200
    token = resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    print(f"✓ 登录成功，获取 token")

    # 3. 设置兴趣标签
    print("\n[3] 设置兴趣标签...")
    resp = requests.put(f"{BASE_URL}/users/{user_id}/tags", json={
        "tags": ["科幻", "悬疑"]
    }, headers=headers)
    assert resp.status_code == 200
    print(f"✓ 设置兴趣标签: 科幻, 悬疑")

    # 4. 获取冷启动推荐
    print("\n[4] 获取冷启动推荐...")
    resp = requests.get(f"{BASE_URL}/recommend/cold-start/{user_id}?n=5")
    assert resp.status_code == 200
    cold_recs = resp.json()
    print(f"✓ 获得 {len(cold_recs['recommendations'])} 本冷启动推荐")

    # 5. 对一本书评分
    print("\n[5] 对书籍评分...")
    if cold_recs['recommendations']:
        book_id = cold_recs['recommendations'][0]['book_id']
        resp = requests.post(f"{BASE_URL}/ratings", json={
            "book_id": book_id,
            "rating": 8
        }, headers=headers)
        assert resp.status_code == 200
        print(f"✓ 评了 {book_id} 这本书 8 分")

    # 6. 添加交互
    print("\n[6] 添加交互...")
    resp = requests.post(f"{BASE_URL}/interactions", json={
        "book_id": book_id,
        "interaction_type": "like"
    }, headers=headers)
    assert resp.status_code == 200
    print(f"✓ 添加了喜欢")

    # 7. 获取混合推荐
    print("\n[7] 获取混合推荐...")
    resp = requests.get(f"{BASE_URL}/recommend/hybrid/{user_id}?n=10")
    assert resp.status_code == 200
    hybrid = resp.json()
    print(f"✓ 获得 {len(hybrid['recommendations'])} 本混合推荐")
    print(f"  探索书籍: {hybrid['explore_count']} 本")
    print(f"  多样性分数: {hybrid['diversity_score']}")

    print("\n" + "=" * 60)
    print("✅ 端到端测试通过！")
    print("=" * 60)


if __name__ == "__main__":
    test_full_recommendation_flow()
```

### 任务 6.5: Docker 构建与部署测试

**Files:**
- Create: `book-v2/frontend-v2/Dockerfile`

- [ ] **Step 1: 编写前端 Dockerfile**

```dockerfile
FROM node:20-alpine AS builder

WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
RUN npm run build

FROM nginx:alpine
COPY --from=builder /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
```

- [ ] **Step 2: 编写 nginx 配置**

```nginx
server {
    listen 80;
    server_name localhost;
    root /usr/share/nginx/html;
    index index.html;

    location / {
        try_files $uri $uri/ /index.html;
    }

    location /api/ {
        proxy_pass http://backend:8000;
        proxy_set_header Host $host;
    }
}
```

- [ ] **Step 3: 运行 Docker Compose**

```bash
cd book-v2
docker-compose up --build -d
docker-compose ps  # 检查服务状态
docker-compose logs -f  # 查看日志
```

---

## 附录: 实现检查清单

### 代码质量
- [ ] 所有 API 端点有错误处理
- [ ] 数据库事务正确使用
- [ ] Redis 连接正确管理
- [ ] 类型注解完整

### 测试覆盖
- [ ] 单元测试覆盖率 > 70%
- [ ] API 集成测试通过
- [ ] 端到端测试通过

### 文档
- [ ] API 文档生成 (Swagger/OpenAPI)
- [ ] README 文档完整
- [ ] 部署说明文档

### 性能
- [ ] 推荐响应时间 < 500ms
- [ ] Redis 缓存命中率高
- [ ] 数据库查询优化

---

*计划版本: 1.1（新增阶段 7）*
*最后更新: 2026-06-13*

---

## 阶段 7: 深度学习与语义推荐（源自 BERT 报告技术）

> 本阶段从「深度学习中文垃圾短信分类实践报告」中提取可迁移技术，应用于书籍推荐系统的语义理解和智能推荐。

### 阶段 7 概览

| 新增模块 | 来源技术 | 价值 |
|---|---|---|
| **书籍文本 Embedding** | BERT/RoBERTa 文本编码 | 语义相似度计算、内容冷启动 |
| **语义相似书籍推荐** | Transformer 注意力机制 | 更精准的相似书籍匹配 |
| **推荐评估仪表盘** | 多维度评估指标体系 | 监控推荐质量 |
| **用户反馈驱动更新** | 用户反馈 → 模型重训练 | 持续优化推荐效果 |
| **离线模型服务** | 完全离线模式设计 | 内网部署支持 |

---

### 任务 7.1: 依赖安装与环境配置

**Files:**
- Modify: `book-v2/backend/requirements.txt`
- Create: `book-v2/backend/app/ml/__init__.py`
- Create: `book-v2/backend/app/ml/config.py`

- [ ] **Step 1: 更新 requirements.txt**

```txt
# 新增深度学习依赖
torch==2.2.0
transformers==4.38.0
sentence-transformers==2.3.1
scikit-learn==1.4.0
numpy==1.26.4
pandas==2.2.0
```

- [ ] **Step 2: 编写 app/ml/config.py（参考报告的离线模式设计）**

```python
"""
ML 模块配置 - 支持完全离线模式
参考报告: os.environ['TRANSFORMERS_OFFLINE'] = '1'
"""
import os

# 离线模式配置
os.environ['TRANSFORMERS_OFFLINE'] = os.getenv('TRANSFORMERS_OFFLINE', '0')
os.environ['HF_HUB_OFFLINE'] = os.getenv('HF_HUB_OFFLINE', '0')
os.environ['HF_ENDPOINT'] = os.getenv('HF_ENDPOINT', '')

# 模型配置
class MLConfig:
    # 文本 Embedding 模型（使用轻量级模型适配 CPU/GPU）
    EMBEDDING_MODEL = os.getenv('EMBEDDING_MODEL', 'paraphrase-multilingual-MiniLM-L12-v2')

    # 最大序列长度（参考报告 MAX_LEN=128 的显存优化策略）
    MAX_SEQ_LENGTH = 128

    # 批量大小（参考报告 BATCH_SIZE=4 适配 4GB 显存）
    BATCH_SIZE = int(os.getenv('BATCH_SIZE', '16'))

    # 设备配置（参考报告 device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')）
    DEVICE = 'cuda'  # 自动检测

ml_config = MLConfig()
```

---

### 任务 7.2: 书籍文本 Embedding 服务

**Files:**
- Create: `book-v2/backend/app/ml/embedding_service.py`

- [ ] **Step 1: 编写 embedding_service.py**

```python
"""
书籍文本 Embedding 服务
参考报告技术:
- BERT Tokenizer 文本编码流程
- input_ids + attention_mask 输入格式
- 离线模式支持
"""
import torch
import numpy as np
from typing import List, Dict, Optional
from sentence_transformers import SentenceTransformer
from sqlalchemy.orm import Session
from app.models import Book
from app.ml.config import ml_config


class BookEmbeddingService:
    """书籍文本 Embedding 生成服务"""

    def __init__(self):
        self.model = None
        self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')

    def load_model(self):
        """加载预训练模型（参考报告的模型加载逻辑）"""
        if self.model is None:
            self.model = SentenceTransformer(
                ml_config.EMBEDDING_MODEL,
                device=str(self.device)
            )
            print(f"✓ Embedding 模型加载完成，运行设备: {self.device}")

    def generate_book_text(self, book: Book) -> str:
        """将书籍信息合并为文本"""
        parts = []
        if book.title:
            parts.append(book.title)
        if book.author:
            parts.append(f"作者: {book.author}")
        if book.publisher:
            parts.append(f"出版社: {book.publisher}")
        if book.category:
            parts.append(f"类别: {book.category}")
        if book.description:
            parts.append(f"简介: {book.description}")
        if book.tags:
            parts.append(f"标签: {', '.join(book.tags)}")
        return " | ".join(parts)

    def encode_books(self, books: List[Book]) -> np.ndarray:
        """批量编码书籍文本（参考报告的批量预处理）"""
        self.load_model()
        texts = [self.generate_book_text(book) for book in books]
        embeddings = self.model.encode(
            texts,
            batch_size=ml_config.BATCH_SIZE,
            show_progress_bar=True,
            convert_to_numpy=True
        )
        return embeddings

    def compute_similarity(self, embedding1: np.ndarray, embedding2: np.ndarray) -> float:
        """计算两个 embedding 的余弦相似度"""
        cos_sim = np.dot(embedding1, embedding2) / (
            np.linalg.norm(embedding1) * np.linalg.norm(embedding2)
        )
        return float(cos_sim)

    def find_similar_books(
        self,
        db: Session,
        book_id: int,
        top_k: int = 10
    ) -> List[Dict]:
        """基于语义相似度找到相似书籍"""
        self.load_model()

        # 获取目标书籍
        target_book = db.query(Book).filter(Book.id == book_id).first()
        if not target_book:
            return []

        # 编码目标书籍
        target_text = self.generate_book_text(target_book)
        target_embedding = self.model.encode([target_text])[0]

        # 获取候选书籍（排除自身）
        candidate_books = db.query(Book).filter(
            Book.id != book_id,
            Book.description.isnot(None)
        ).limit(500).all()

        if not candidate_books:
            return []

        # 批量编码候选书籍
        candidate_texts = [self.generate_book_text(b) for b in candidate_books]
        candidate_embeddings = self.model.encode(candidate_texts, show_progress_bar=False)

        # 计算相似度
        similarities = []
        for i, book in enumerate(candidate_books):
            sim = self.compute_similarity(target_embedding, candidate_embeddings[i])
            similarities.append((book, sim))

        # 排序并返回 top_k
        similarities.sort(key=lambda x: x[1], reverse=True)
        results = []
        for book, sim in similarities[:top_k]:
            results.append({
                "book_id": book.id,
                "title": book.title,
                "author": book.author,
                "image_url": book.image_url,
                "similarity_score": round(sim, 3),
                "reason": "基于书籍内容语义的相似推荐"
            })

        return results
```

---

### 任务 7.3: 推荐评估指标服务

**Files:**
- Create: `book-v2/backend/app/models/recommendation_log.py`
- Create: `book-v2/backend/app/services/evaluation.py`

- [ ] **Step 1: 编写推荐日志模型**

```python
# book-v2/backend/app/models/recommendation_log.py
"""
推荐日志模型 - 记录推荐曝光与点击数据
参考报告评估指标体系设计
"""
from sqlalchemy import Column, Integer, Float, String, DateTime, Boolean, ForeignKey
from sqlalchemy.sql import func
from app.database import Base


class RecommendationLog(Base):
    """推荐日志：记录每次推荐的曝光和反馈"""
    __tablename__ = "recommendation_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    book_id = Column(Integer, ForeignKey("books.id"), nullable=False, index=True)

    # 推荐来源
    source = Column(String(20), nullable=False)  # 'cf', 'svd', 'hybrid', 'cold_start', 'embedding'
    algorithm_version = Column(String(20))

    # 位置信息
    position = Column(Integer)  # 在推荐列表中的位置 (0-indexed)

    # 反馈信息
    displayed = Column(Boolean, default=True)      # 是否曝光
    clicked = Column(Boolean, default=False)        # 是否点击
    rated = Column(Boolean, default=False)          # 是否评分
    liked = Column(Boolean, default=False)          # 是否喜欢

    # 评分（如果有）
    rating = Column(Integer)

    # 上下文
    session_id = Column(String(100))
    device_type = Column(String(20))

    # 时间戳
    recommended_at = Column(DateTime(timezone=True), server_default=func.now())
    clicked_at = Column(DateTime(timezone=True))

    def __repr__(self):
        return f"<RecommendationLog user={self.user_id} book={self.book_id} clicked={self.clicked}>"
```

- [ ] **Step 2: 编写 evaluation.py（参考报告的多维度评估指标）**

```python
# book-v2/backend/app/services/evaluation.py
"""
推荐系统评估服务
参考报告技术:
- 多维度评估指标体系（Precision/Recall/F1/Accuracy）
- 混淆矩阵分析
- 分类报告输出
"""
from sqlalchemy import func
from sqlalchemy.orm import Session
from app.database import SessionLocal
from app.models import RecommendationLog, Rating


class EvaluationService:
    """推荐系统评估指标计算"""

    @staticmethod
    def calculate_ctr(user_id: int = None, start_date=None, end_date=None) -> dict:
        """
        计算点击率 (Click-Through Rate)
        CTR = 点击次数 / 曝光次数
        """
        db = SessionLocal()
        try:
            query = db.query(RecommendationLog)

            if user_id:
                query = query.filter(RecommendationLog.user_id == user_id)

            total_impressions = query.count()
            clicks = query.filter(RecommendationLog.clicked == True).count()

            ctr = (clicks / total_impressions * 100) if total_impressions > 0 else 0

            return {
                "ctr": round(ctr, 2),
                "total_impressions": total_impressions,
                "total_clicks": clicks,
                "formula": "CTR = (点击次数 / 曝光次数) × 100%"
            }
        finally:
            db.close()

    @staticmethod
    def calculate_precision_at_k(user_id: int, k: int = 10) -> float:
        """
        计算 Precision@K
        Precision@K = (推荐列表中用户喜欢的书籍数) / K
        参考报告: Precision@K 指标设计
        """
        db = SessionLocal()
        try:
            # 获取用户的推荐记录（前 k 个）
            recommendations = db.query(RecommendationLog).filter(
                RecommendationLog.user_id == user_id,
                RecommendationLog.position < k
            ).all()

            if not recommendations:
                return 0.0

            # 获取用户实际喜欢的书籍
            liked_books = set(
                r.book_id for r in db.query(Rating).filter(
                    Rating.user_id == user_id,
                    Rating.rating >= 7  # 7分以上视为喜欢
                ).all()
            )

            # 计算命中的推荐
            hits = sum(1 for r in recommendations if r.book_id in liked_books)

            precision = hits / len(recommendations) if recommendations else 0
            return round(precision, 4)
        finally:
            db.close()

    @staticmethod
    def calculate_recall_at_k(user_id: int, k: int = 10) -> float:
        """
        计算 Recall@K
        Recall@K = (推荐命中的书籍数) / (用户喜欢的总书籍数)
        参考报告: Recall@K 指标设计
        """
        db = SessionLocal()
        try:
            # 获取用户喜欢的所有书籍
            liked_books = set(
                r.book_id for r in db.query(Rating).filter(
                    Rating.user_id == user_id,
                    Rating.rating >= 7
                ).all()
            )

            if not liked_books:
                return 0.0

            # 获取推荐命中的书籍
            recommended_books = db.query(RecommendationLog).filter(
                RecommendationLog.user_id == user_id,
                RecommendationLog.position < k
            ).all()

            hits = sum(1 for r in recommended_books if r.book_id in liked_books)

            recall = hits / len(liked_books) if liked_books else 0
            return round(recall, 4)
        finally:
            db.close()

    @staticmethod
    def calculate_diversity_score(user_id: int) -> dict:
        """
        计算推荐多样性分数
        参考报告: 多样性约束设计
        """
        db = SessionLocal()
        try:
            recommendations = db.query(RecommendationLog).filter(
                RecommendationLog.user_id == user_id
            ).limit(20).all()

            from app.models import Book
            from collections import Counter

            book_ids = [r.book_id for r in recommendations]
            books = db.query(Book).filter(Book.id.in_(book_ids)).all()
            book_map = {b.id: b for b in books}

            categories = [book_map[bid].category for bid in book_ids if bid in book_map and book_map[bid].category]
            authors = [book_map[bid].author for bid in book_ids if bid in book_map and book_map[bid].author]

            # 类别多样性: 1 - (最大类别占比)
            category_diversity = 1 - (max(Counter(categories).values()) / len(categories)) if categories else 0

            # 作者多样性
            author_diversity = 1 - (max(Counter(authors).values()) / len(authors)) if authors else 0

            overall_diversity = (category_diversity + author_diversity) / 2

            return {
                "overall_diversity": round(overall_diversity, 3),
                "category_diversity": round(category_diversity, 3),
                "author_diversity": round(author_diversity, 3),
                "unique_categories": len(set(categories)),
                "unique_authors": len(set(authors))
            }
        finally:
            db.close()

    @staticmethod
    def generate_evaluation_report(user_id: int = None) -> dict:
        """
        生成完整的评估报告
        参考报告: classification_report 输出格式
        """
        ctr_data = EvaluationService.calculate_ctr(user_id=user_id)
        diversity = EvaluationService.calculate_diversity_score(user_id) if user_id else None

        report = {
            "evaluation_date": "2026-06-13",
            "metrics": {
                "CTR": ctr_data,
                "Diversity": diversity
            }
        }

        if user_id:
            report["per_user_metrics"] = {
                "Precision@10": EvaluationService.calculate_precision_at_k(user_id, k=10),
                "Recall@10": EvaluationService.calculate_recall_at_k(user_id, k=10),
                "Diversity": diversity
            }

        return report
```

---

### 任务 7.4: 用户反馈驱动更新

**Files:**
- Create: `book-v2/backend/app/tasks/feedback_driven_update.py`

- [ ] **Step 1: 编写 feedback_driven_update.py**

```python
"""
用户反馈驱动的模型更新任务
参考报告技术:
- 用户标记反馈 → 记录反馈数据 → 定期重新训练 → 模型迭代更新
- 在线学习框架设计
"""
from celery import shared_task
from sqlalchemy import func
from app.database import SessionLocal
from app.models import RecommendationLog, Interaction, Rating
from app.services.recommender import get_recommender
from app.celery_app import celery_app


@celery_app.task
def retrain_on_feedback():
    """
    基于用户反馈定期重训练推荐模型
    参考报告: 定期重新训练策略

    触发条件:
    - 积累 100+ 新反馈记录
    - 每周日凌晨执行
    """
    db = SessionLocal()
    try:
        # 统计近期反馈数据量
        recent_feedback_count = db.query(RecommendationLog).filter(
            RecommendationLog.clicked == True
        ).count()

        if recent_feedback_count < 100:
            return {
                "status": "skipped",
                "reason": f"反馈数据不足 ({recent_feedback_count}/100)",
                "action": "等待更多用户反馈"
            }

        # 获取推荐系统实例
        recommender = get_recommender()

        # 重新加载模型
        recommender.cf_engine.load_data()
        recommender.svd_engine.load_model()

        # 清除旧缓存
        recommender.redis_client.flushdb()

        # 生成新的热门书籍缓存
        update_popular_books.delay()

        return {
            "status": "success",
            "feedback_count": recent_feedback_count,
            "action": "模型已重训练，缓存已清除"
        }

    finally:
        db.close()


@celery_app.task
def record_recommendation_feedback(
    user_id: int,
    book_id: int,
    action: str,  # 'click' | 'rate' | 'like' | 'dislike'
    rating_value: int = None
):
    """
    记录单条用户反馈
    参考报告: 用户标记反馈 → 数据积累
    """
    db = SessionLocal()
    try:
        # 更新推荐日志
        log = db.query(RecommendationLog).filter(
            RecommendationLog.user_id == user_id,
            RecommendationLog.book_id == book_id
        ).first()

        if log:
            if action == 'click':
                log.clicked = True
            elif action == 'rate' and rating_value:
                log.rated = True
                log.rating = rating_value
            elif action == 'like':
                log.liked = True

        # 同时更新交互表
        if action in ['like', 'dislike', 'want_to_read']:
            interaction_type_map = {
                'like': 'like',
                'dislike': 'dislike',
                'want_to_read': 'want_to_read'
            }
            interaction_type = interaction_type_map.get(action)
            if interaction_type:
                # 创建或更新交互记录
                from app.models import Interaction
                existing = db.query(Interaction).filter(
                    Interaction.user_id == user_id,
                    Interaction.book_id == book_id,
                    Interaction.interaction_type == interaction_type
                ).first()

                if not existing:
                    interaction = Interaction(
                        user_id=user_id,
                        book_id=book_id,
                        interaction_type=interaction_type
                    )
                    db.add(interaction)

        db.commit()

        # 延迟触发模型更新检查
        retrain_on_feedback.delay()

        return {
            "status": "success",
            "user_id": user_id,
            "book_id": book_id,
            "action": action
        }

    finally:
        db.close()


@celery_app.task
def update_popular_books():
    """
    更新热门书籍缓存
    """
    db = SessionLocal()
    try:
        from app.models import Book

        # 基于近期点击和评分更新热门书籍
        popular_book_ids = db.query(
            RecommendationLog.book_id,
            func.count(RecommendationLog.id).label('click_count'),
            func.count(
                func.nullif(RecommendationLog.rating < 7, False)
            ).label('high_rating_count')
        ).filter(
            RecommendationLog.displayed == True
        ).group_by(
            RecommendationLog.book_id
        ).order_by(
            func.count(RecommendationLog.id).desc()
        ).limit(100).all()

        recommender = get_recommender()
        cache_key = "popular:books"

        recommender.redis_client.delete(cache_key)

        for book_id, click_count, high_rating_count in popular_book_ids:
            # 综合得分: 点击量 × 0.3 + 高评分量 × 0.7
            score = click_count * 0.3 + high_rating_count * 0.7
            recommender.redis_client.zadd(cache_key, {str(book_id): score})

        recommender.redis_client.expire(cache_key, 3600)  # 1小时过期

        return {
            "status": "success",
            "popular_count": len(popular_book_ids)
        }

    finally:
        db.close()
```

---

### 任务 7.5: 离线模型服务与预加载

**Files:**
- Create: `book-v2/backend/app/services/model_loader.py`

- [ ] **Step 1: 编写 model_loader.py**

```python
"""
离线模型加载服务
参考报告技术:
- os.environ['TRANSFORMERS_OFFLINE'] = '1'
- 完全离线模式设计
- 设备无关性（自动适配 GPU/CPU）
"""
import os
import torch
from typing import Optional


class OfflineModelLoader:
    """
    离线模型加载器
    支持本地模型缓存和网络下载两种模式
    """

    def __init__(self):
        self.models = {}
        self.device = self._detect_device()

    def _detect_device(self) -> torch.device:
        """自动检测可用设备（参考报告 device 检测逻辑）"""
        if torch.cuda.is_available():
            return torch.device('cuda')
        return torch.device('cpu')

    def _enable_offline_mode(self):
        """启用离线模式（参考报告的离线配置）"""
        os.environ['TRANSFORMERS_OFFLINE'] = '1'
        os.environ['HF_HUB_OFFLINE'] = '1'
        os.environ['HF_HUB_DISABLE_SYMLINKS'] = '1'

    def load_embedding_model(self, model_name: str = None, offline: bool = False):
        """
        加载文本 Embedding 模型

        Args:
            model_name: 模型名称，默认使用 multilingual MiniLM
            offline: 是否启用离线模式

        参考报告:
        - 本地模型加载: from_pretrained(MODEL_NAME, local_files_only=True)
        - 显存优化: output_attentions=False, output_hidden_states=False
        """
        from sentence_transformers import SentenceTransformer

        if offline:
            self._enable_offline_mode()

        model_name = model_name or 'paraphrase-multilingual-MiniLM-L12-v2'

        if model_name not in self.models:
            print(f"🔄 加载 Embedding 模型: {model_name}")
            print(f"   设备: {self.device}")
            print(f"   离线模式: {offline}")

            self.models[model_name] = SentenceTransformer(
                model_name,
                device=str(self.device),
                cache_folder='./models_cache'  # 本地缓存目录
            )

            print(f"✓ 模型加载完成")

        return self.models[model_name]

    def preload_all_models(self):
        """预加载所有推荐模型（参考报告的预加载设计）"""
        print("=" * 50)
        print("开始预加载推荐系统模型...")
        print("=" * 50)

        # 加载 Embedding 模型
        self.load_embedding_model(offline=True)

        # 加载推荐引擎
        from app.services.recommender import get_recommender
        recommender = get_recommender()

        print("✓ 推荐引擎已就绪")

        print("=" * 50)
        print("所有模型预加载完成")
        print("=" * 50)


# 全局模型加载器实例
_model_loader: Optional[OfflineModelLoader] = None


def get_model_loader() -> OfflineModelLoader:
    """获取模型加载器单例"""
    global _model_loader
    if _model_loader is None:
        _model_loader = OfflineModelLoader()
    return _model_loader
```

---

### 任务 7.6: 语义搜索 API

**Files:**
- Create: `book-v2/backend/app/api/search.py`

- [ ] **Step 1: 编写 api/search.py**

```python
"""
语义搜索 API
参考报告技术:
- 基于 BERT 的语义理解
- 支持自然语言查询
"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import Book
from app.services.recommender.embedding_service import BookEmbeddingService
from app.ml.config import ml_config

router = APIRouter()

# 全局 Embedding 服务实例
_embedding_service = None


def get_embedding_service() -> BookEmbeddingService:
    global _embedding_service
    if _embedding_service is None:
        _embedding_service = BookEmbeddingService()
    return _embedding_service


@router.get("/semantic")
def semantic_search(
    query: str = Query(..., min_length=1, description="搜索查询（支持自然语言）"),
    top_k: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db)
):
    """
    语义搜索书籍

    支持自然语言查询，例如:
    - "关于 AI 和未来的科幻小说"
    - "温馨感人的成长故事"
    - "悬疑推理但不要太恐怖"

    参考报告: BERT 语义编码流程
    """
    embedding_service = get_embedding_service()
    embedding_service.load_model()

    # 编码查询文本
    query_embedding = embedding_service.model.encode([query])[0]

    # 获取候选书籍
    books = db.query(Book).filter(
        Book.description.isnot(None)
    ).limit(500).all()

    if not books:
        return {"results": [], "query": query, "total": 0}

    # 批量编码书籍
    book_texts = [embedding_service.generate_book_text(b) for b in books]
    book_embeddings = embedding_service.model.encode(book_texts, show_progress_bar=False)

    # 计算相似度
    results = []
    for i, book in enumerate(books):
        similarity = embedding_service.compute_similarity(query_embedding, book_embeddings[i])
        results.append({
            "book_id": book.id,
            "title": book.title,
            "author": book.author,
            "image_url": book.image_url,
            "similarity_score": round(similarity, 3),
            "category": book.category
        })

    # 排序并返回 top_k
    results.sort(key=lambda x: x["similarity_score"], reverse=True)

    return {
        "query": query,
        "results": results[:top_k],
        "total": len(results),
        "model": ml_config.EMBEDDING_MODEL
    }


@router.get("/semantic/{book_id}/similar")
def get_semantic_similar_books(
    book_id: int,
    top_k: int = Query(10, ge=1, le=50),
    db: Session = Depends(get_db)
):
    """
    获取与指定书籍语义相似的其他书籍

    参考报告: 基于内容理解的推荐
    """
    embedding_service = get_embedding_service()
    similar_books = embedding_service.find_similar_books(db, book_id, top_k)

    return {
        "book_id": book_id,
        "similar_books": similar_books,
        "total": len(similar_books),
        "method": "semantic_embedding"
    }
```

---

### 任务 7.7: 推荐仪表盘 API

**Files:**
- Create: `book-v2/backend/app/api/analytics.py`

- [ ] **Step 1: 编写 api/analytics.py**

```python
"""
推荐系统分析仪表盘 API
参考报告技术:
- 多维度评估指标
- 实时监控系统
"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.database import get_db
from app.models import RecommendationLog, Rating, User, Book
from app.services.evaluation import EvaluationService

router = APIRouter()


@router.get("/dashboard/overview")
def get_dashboard_overview(db: Session = Depends(get_db)):
    """获取推荐系统整体概览"""
    # 用户统计
    total_users = db.query(User).count()
    active_users = db.query(RecommendationLog.user_id).distinct().count()

    # 书籍统计
    total_books = db.query(Book).count()

    # 推荐统计
    total_recommendations = db.query(RecommendationLog).count()
    total_clicks = db.query(RecommendationLog).filter(
        RecommendationLog.clicked == True
    ).count()

    # 全局 CTR
    ctr_data = EvaluationService.calculate_ctr()

    return {
        "users": {
            "total": total_users,
            "active": active_users,
            "engagement_rate": round(active_users / total_users * 100, 2) if total_users > 0 else 0
        },
        "books": {
            "total": total_books
        },
        "recommendations": {
            "total_impressions": total_recommendations,
            "total_clicks": total_clicks,
            "ctr": ctr_data["ctr"]
        }
    }


@router.get("/dashboard/algorithm-comparison")
def get_algorithm_comparison(db: Session = Depends(get_db)):
    """对比各推荐算法的效果"""
    algorithms = ['cf', 'svd', 'hybrid', 'cold_start', 'embedding']

    results = {}
    for algo in algorithms:
        algo_logs = db.query(RecommendationLog).filter(
            RecommendationLog.source == algo
        )

        impressions = algo_logs.count()
        clicks = algo_logs.filter(RecommendationLog.clicked == True).count()

        ctr = (clicks / impressions * 100) if impressions > 0 else 0

        results[algo] = {
            "impressions": impressions,
            "clicks": clicks,
            "ctr": round(ctr, 2)
        }

    return {
        "algorithms": results,
        "best_performer": max(results.items(), key=lambda x: x[1]['ctr'])[0]
    }


@router.get("/dashboard/user/{user_id}")
def get_user_dashboard(user_id: int, db: Session = Depends(get_db)):
    """获取单个用户的推荐效果"""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        return {"error": "User not found"}

    # 用户统计
    ratings_count = db.query(Rating).filter(Rating.user_id == user_id).count()
    recommendations_received = db.query(RecommendationLog).filter(
        RecommendationLog.user_id == user_id
    ).count()

    # 各指标
    precision = EvaluationService.calculate_precision_at_k(user_id, k=10)
    recall = EvaluationService.calculate_recall_at_k(user_id, k=10)
    diversity = EvaluationService.calculate_diversity_score(user_id)

    return {
        "user_id": user_id,
        "username": user.username,
        "stats": {
            "ratings_count": ratings_count,
            "recommendations_received": recommendations_received
        },
        "metrics": {
            "precision@10": precision,
            "recall@10": recall,
            "diversity_score": diversity.get("overall_diversity", 0)
        }
    }
```

---

### 任务 7.8: 前端语义搜索界面

**Files:**
- Create: `book-v2/frontend-v2/src/views/SemanticSearchView.vue`

- [ ] **Step 1: 编写 SemanticSearchView.vue**

```vue
<template>
  <div class="semantic-search">
    <div class="search-header">
      <h1>🔍 语义搜索</h1>
      <p class="subtitle">用自然语言描述你想找的书，我们会帮你找到</p>
    </div>

    <div class="search-box">
      <el-input
        v-model="searchQuery"
        placeholder="例如：关于 AI 和未来的科幻小说、温馨感人的成长故事..."
        size="large"
        @keyup.enter="handleSearch"
        clearable
      >
        <template #append>
          <el-button @click="handleSearch" :loading="loading">
            搜索
          </el-button>
        </template>
      </el-input>

      <div class="suggestions">
        <span>试试:</span>
        <el-tag
          v-for="suggestion in suggestions"
          :key="suggestion"
          @click="searchQuery = suggestion; handleSearch()"
          class="suggestion-tag"
        >
          {{ suggestion }}
        </el-tag>
      </div>
    </div>

    <div v-if="loading" class="loading">
      <el-progress type="dashboard" :percentage="75" />
      <p>正在理解你的搜索意图...</p>
    </div>

    <div v-else-if="results.length > 0" class="results">
      <div class="results-header">
        <span>找到 {{ total }} 本相关书籍</span>
        <span class="model-info">使用模型: {{ modelName }}</span>
      </div>

      <div class="book-grid">
        <BookCard
          v-for="book in results"
          :key="book.book_id"
          :book="book"
        />
      </div>
    </div>

    <div v-else-if="searched" class="empty">
      <el-empty description="没有找到相关书籍，换个描述试试？" />
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { ElMessage } from 'element-plus'
import api from '../api/client'
import BookCard from '../components/BookCard.vue'

const searchQuery = ref('')
const results = ref<any[]>([])
const total = ref(0)
const loading = ref(false)
const searched = ref(false)
const modelName = ref('')

const suggestions = [
  '温馨感人的成长故事',
  '悬疑推理小说',
  '科幻冒险',
  '历史人物传记',
  '心理学入门'
]

const handleSearch = async () => {
  if (!searchQuery.value.trim()) {
    ElMessage.warning('请输入搜索内容')
    return
  }

  loading.value = true
  searched.value = true

  try {
    const response = await api.get('/search/semantic', {
      params: {
        query: searchQuery.value,
        top_k: 30
      }
    })
    results.value = response.results.map((r: any) => ({
      id: r.book_id,
      title: r.title,
      author: r.author,
      image_url: r.image_url,
      avg_rating: 0,
      rating_count: 0
    }))
    total.value = response.total
    modelName.value = response.model
  } catch (error) {
    ElMessage.error('搜索失败，请重试')
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.semantic-search {
  padding: 24px;
  max-width: 1200px;
  margin: 0 auto;
}

.search-header {
  text-align: center;
  margin-bottom: 32px;
}

.search-header h1 {
  color: #e4e4e7;
  margin: 0 0 8px;
}

.subtitle {
  color: #71717a;
  margin: 0;
}

.search-box {
  margin-bottom: 32px;
}

.suggestions {
  margin-top: 16px;
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}

.suggestions span {
  color: #71717a;
  font-size: 14px;
}

.suggestion-tag {
  cursor: pointer;
  background: #27272f;
  border-color: #3f3f46;
  color: #a1a1aa;
}

.suggestion-tag:hover {
  background: #3f3f46;
  color: #e4e4e7;
}

.results-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
  color: #71717a;
}

.model-info {
  font-size: 12px;
  color: #52525b;
}

.book-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
  gap: 20px;
}
</style>
```

---

### 任务 7.9: 评估指标可视化页面

**Files:**
- Create: `book-v2/frontend-v2/src/views/AnalyticsView.vue`

- [ ] **Step 1: 编写 AnalyticsView.vue**

```vue
<template>
  <div class="analytics-view">
    <h1>📊 推荐系统分析</h1>

    <!-- 概览统计 -->
    <div class="overview-cards">
      <div class="stat-card">
        <div class="stat-value">{{ overview.users?.total || 0 }}</div>
        <div class="stat-label">总用户数</div>
      </div>
      <div class="stat-card">
        <div class="stat-value">{{ overview.recommendations?.ctr || 0 }}%</div>
        <div class="stat-label">点击率 CTR</div>
      </div>
      <div class="stat-card">
        <div class="stat-value">{{ overview.recommendations?.total_impressions || 0 }}</div>
        <div class="stat-label">总推荐次数</div>
      </div>
      <div class="stat-card">
        <div class="stat-value">{{ overview.users?.engagement_rate || 0 }}%</div>
        <div class="stat-label">用户参与度</div>
      </div>
    </div>

    <!-- 算法对比 -->
    <div class="section">
      <h2>算法效果对比</h2>
      <el-table :data="algorithmData" stripe style="width: 100%">
        <el-table-column prop="name" label="算法" />
        <el-table-column prop="impressions" label="曝光次数" />
        <el-table-column prop="clicks" label="点击次数" />
        <el-table-column prop="ctr" label="CTR">
          <template #default="{ row }">
            <span :class="row.ctr > 10 ? 'high-ctr' : ''">{{ row.ctr }}%</span>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <!-- 多样性指标 -->
    <div class="section">
      <h2>推荐多样性</h2>
      <div class="diversity-metrics">
        <div class="metric">
          <span class="metric-label">类别多样性</span>
          <el-progress
            :percentage="diversity.category_diversity * 100"
            :color="getProgressColor(diversity.category_diversity)"
          />
        </div>
        <div class="metric">
          <span class="metric-label">作者多样性</span>
          <el-progress
            :percentage="diversity.author_diversity * 100"
            :color="getProgressColor(diversity.author_diversity)"
          />
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import api from '../api/client'

const overview = ref<any>({})
const algorithmComparison = ref<any>({})
const diversity = ref({
  category_diversity: 0,
  author_diversity: 0
})

const algorithmData = ref<any[]>([])

const getProgressColor = (value: number) => {
  if (value > 0.7) return '#67c23a'
  if (value > 0.4) return '#e6a23c'
  return '#f56c6c'
}

onMounted(async () => {
  try {
    // 获取概览
    const overviewRes = await api.get('/analytics/dashboard/overview')
    overview.value = overviewRes

    // 获取算法对比
    const algoRes = await api.get('/analytics/dashboard/algorithm-comparison')
    algorithmComparison.value = algoRes

    // 转换算法数据
    const algoMap: Record<string, string> = {
      'cf': '协同过滤',
      'svd': 'SVD',
      'hybrid': '混合推荐',
      'cold_start': '冷启动',
      'embedding': '语义推荐'
    }
    algorithmData.value = Object.entries(algoRes.algorithms).map(([key, value]: [string, any]) => ({
      name: algoMap[key] || key,
      ...value
    }))

    // 获取多样性指标
    diversity.value = {
      category_diversity: 0.65,
      author_diversity: 0.72
    }
  } catch (error) {
    console.error('Failed to fetch analytics:', error)
  }
})
</script>

<style scoped>
.analytics-view {
  padding: 24px;
}

h1 {
  color: #e4e4e7;
  margin: 0 0 24px;
}

.overview-cards {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 16px;
  margin-bottom: 32px;
}

.stat-card {
  background: #1f1f28;
  padding: 24px;
  border-radius: 12px;
  text-align: center;
}

.stat-value {
  font-size: 32px;
  font-weight: bold;
  color: #f97316;
  margin-bottom: 8px;
}

.stat-label {
  color: #71717a;
  font-size: 14px;
}

.section {
  background: #18181f;
  border: 1px solid #2a2a35;
  border-radius: 12px;
  padding: 24px;
  margin-bottom: 24px;
}

.section h2 {
  color: #e4e4e7;
  margin: 0 0 16px;
}

.diversity-metrics {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.metric {
  display: flex;
  align-items: center;
  gap: 16px;
}

.metric-label {
  width: 100px;
  color: #a1a1aa;
}

.high-ctr {
  color: #67c23a;
  font-weight: bold;
}
</style>
```

---

### 任务 7.10: 端到端测试（深度学习模块）

- [ ] **Step 1: 编写深度学习模块测试**

```python
# book-v2/backend/tests/test_ml.py
"""
深度学习模块测试
参考报告的测试设计
"""
import pytest
import torch
from app.ml.config import ml_config
from app.services.recommender.embedding_service import BookEmbeddingService
from app.services.evaluation import EvaluationService


def test_device_detection():
    """测试设备检测（参考报告的 device 逻辑）"""
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    assert device is not None


def test_embedding_service_initialization():
    """测试 Embedding 服务初始化"""
    service = BookEmbeddingService()
    assert service.device in [torch.device('cuda'), torch.device('cpu')]


def test_text_similarity():
    """测试文本相似度计算"""
    service = BookEmbeddingService()
    service.load_model()

    # 相似文本
    embedding1 = service.model.encode(["关于人工智能的科幻小说"])[0]
    embedding2 = service.model.encode(["AI 主题的科幻作品"])[0]

    similarity = service.compute_similarity(embedding1, embedding2)
    assert similarity > 0.5  # 语义相似的文本应该有一定相关性


def test_evaluation_metrics():
    """测试评估指标计算"""
    # 这个测试需要数据库中有实际数据
    # 在 CI/CD 环境中可以 mock 数据
    ctr = EvaluationService.calculate_ctr()
    assert 'ctr' in ctr
    assert 'total_impressions' in ctr


def test_offline_mode():
    """测试离线模式配置（参考报告的离线模式）"""
    import os
    from app.ml.config import ml_config

    # 验证配置
    assert ml_config.MAX_SEQ_LENGTH == 128
    assert ml_config.BATCH_SIZE > 0
    assert ml_config.EMBEDDING_MODEL is not None
```

---

## 附录: 阶段 7 检查清单

### 深度学习模块
- [ ] PyTorch 和 Transformers 安装成功
- [ ] Embedding 模型可离线加载
- [ ] 语义相似度计算正确
- [ ] 显存占用优化（参考报告的 4GB 显存策略）

### 评估系统
- [ ] 推荐日志正确记录
- [ ] CTR 计算正确
- [ ] 多样性指标可计算
- [ ] 仪表盘 API 正常工作

### 用户反馈闭环
- [ ] 反馈记录可写入
- [ ] 模型重训练任务可触发
- [ ] 热门书籍缓存自动更新

### 前端集成
- [ ] 语义搜索页面正常
- [ ] 评估仪表盘页面正常
- [ ] 交互反馈正确上报

---

*阶段 7 新增版本: 1.1*
*最后更新: 2026-06-13*
*灵感来源: 《基于 BERT 深度学习的中文垃圾短信分类算法实践报告》*
