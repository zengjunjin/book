"""触发书籍统计刷新任务"""
import sys
sys.path.insert(0, '.')

from app.tasks.model_training import refresh_all_book_stats

print("触发 refresh_all_book_stats 任务...")
result = refresh_all_book_stats.delay()
print(f"Task ID: {result.id}")

print("等待任务完成（约30秒）...")
import time
time.sleep(30)

print(f"Result: {result.result}")