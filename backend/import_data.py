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
