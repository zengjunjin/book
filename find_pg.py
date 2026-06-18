import subprocess
result = subprocess.run(["netstat", "-ano"], capture_output=True, text=True)
for line in result.stdout.split('\n'):
    if '5432' in line and 'LISTENING' in line:
        print(line)
