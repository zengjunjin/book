import asyncio
import subprocess
import sys
import os
import time

# 启动后端（使用 SQLite 模式）
env = os.environ.copy()
env["USE_SQLITE"] = "1"

backend_dir = r"C:\Users\15116\Desktop\book\book-v2\backend"
frontend_dir = r"C:\Users\15116\Desktop\book\book-v2\frontend-v2"

print("=== 启动后端服务 (SQLite)...")
backend = subprocess.Popen(
    [sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8001", "--reload"],
    cwd=backend_dir,
    env=env
)
print(f"后端 PID: {backend.pid}")

time.sleep(5)

print("\n=== 启动前端服务...")
frontend = subprocess.Popen(
    [sys.executable, "-m", "vite", "--host", "127.0.0.1", "--port", "5173"],
    cwd=frontend_dir,
    env=env
)
print(f"前端 PID: {frontend.pid}")

print("\n=== 服务启动完成！")
print(f"后端: http://127.0.0.1:8001")
print(f"前端: http://127.0.0.1:5173")
print("按 Ctrl+C 停止服务...")

try:
    while True:
        time.sleep(1)
        if backend.poll() is not None:
            print(f"后端已停止，退出码: {backend.returncode}")
            break
        if frontend.poll() is not None:
            print(f"前端已停止，退出码: {frontend.returncode}")
            break
except KeyboardInterrupt:
    print("\n正在停止服务...")
    backend.terminate()
    frontend.terminate()
    print("服务已停止")