"""
独立脚本：从数据库构建 FAISS 索引并保存到 data/faiss.bin

用法：
    # 全量构建（默认）
    python scripts/build_faiss_index.py

    # 只构建前 N 本书（调试用）
    python scripts/build_faiss_index.py --limit 5000

    # 指定输出路径
    python scripts/build_faiss_index.py --path data/faiss.bin

成功后生成：
    backend/data/faiss.bin          (FAISS 原始索引)
    backend/data/faiss_meta.pkl     (id_to_book 映射/元数据)
"""

import argparse
import os
import sys
import time

# 使 backend 包可从 scripts 目录导入
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_BACKEND_DIR = os.path.dirname(_SCRIPT_DIR)
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)


def _init_flask_app():
    """初始化 Flask 应用 & SQLAlchemy，返回 app。失败时返回 None。"""
    try:
        from app import create_app
        app = create_app()
        return app
    except Exception as e:
        print(f'[build_faiss_index] 无法初始化 Flask app: {e}')
        try:
            from extensions import db
            from config import Config
            from flask import Flask
            app = Flask(__name__)
            app.config.from_object(Config)
            db.init_app(app)
            with app.app_context():
                try:
                    db.create_all()
                except Exception:
                    pass
            return app
        except Exception as e2:
            print(f'[build_faiss_index] 备用初始化也失败: {e2}')
            return None


def main():
    parser = argparse.ArgumentParser(description='构建 FAISS 向量索引')
    parser.add_argument('--limit', type=int, default=None,
                        help='只处理前 N 本书（None 表示全量）')
    parser.add_argument('--path', type=str, default=None,
                        help='输出 faiss.bin 路径，默认 backend/data/faiss.bin')
    args = parser.parse_args()

    app = _init_flask_app()
    if app is None:
        print('[build_faiss_index] Flask 应用初始化失败，终止')
        return 2

    try:
        with app.app_context():
            from services.embedding_service import get_embedding_service
            svc = get_embedding_service()

            # 确认模型已加载
            if svc is None or svc.model is None:
                print('[build_faiss_index] Embedding 模型未加载，退出')
                return 3

            # 统计 DB 书籍数量
            try:
                from models import Book
                total = Book.query.count()
            except Exception:
                total = -1
            print(f'[build_faiss_index] 数据库书籍总数: {total}')

            # 构建索引
            t0 = time.time()
            limit = args.limit if args.limit and args.limit > 0 else None
            print(f'[build_faiss_index] 开始构建索引 (limit={limit})...')
            built = svc.build_index_from_db(limit=limit)
            dt = time.time() - t0
            print(f'[build_faiss_index] 构建完成，处理 {built} 本书，耗时 {dt:.1f}s')

            if built <= 0:
                print('[build_faiss_index] 未构建任何书籍，跳过保存')
                return 4

            # 保存到磁盘
            out_path = args.path or os.path.join(_BACKEND_DIR, 'data', 'faiss.bin')
            print(f'[build_faiss_index] 保存索引到: {out_path}')
            ok = svc.save_index(out_path)
            if ok:
                print('[build_faiss_index] 成功 ✓')
                print(f'  - index_size: {svc.index_size}')
                return 0
            print('[build_faiss_index] 保存失败')
            return 5
    except Exception as e:
        print(f'[build_faiss_index] 异常: {e}')
        import traceback
        traceback.print_exc()
        return 1


if __name__ == '__main__':
    sys.exit(main())
