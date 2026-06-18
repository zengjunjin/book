import subprocess
import time

# Find and kill uvicorn processes
result = subprocess.run(["tasklist"], capture_output=True, text=True)
for line in result.stdout.split('\n'):
    if 'python.exe' in line:
        pid = line.split()[1]
        # Kill all python processes except this one
        if pid != str(__import__('os').getpid()):
            subprocess.run(["taskkill", "/F", "/PID", pid])
            print(f"Killed PID {pid}")

time.sleep(1)

# Start backend
proc = subprocess.Popen(
    [r"c:\Users\15116\Desktop\book\book-v2\backend\python.exe", "-m", "uvicorn", "app.main:app", "--reload", "--port", "8001"],
    cwd=r"c:\Users\15116\Desktop\book\book-v2\backend"
)
print(f"Started backend with PID {proc.pid}")
time.sleep(5)

# Verify
r = subprocess.run(
    ["python", "-c", "import requests; print(requests.post('http://localhost:8001/api/auth/register', json={'username': 'verify', 'email': 'verify@test.com', 'password': 'TestPass123'}).status_code)"],
    capture_output=True, text=True
)
print("Backend test:", r.stdout.strip() or r.stderr.strip())
