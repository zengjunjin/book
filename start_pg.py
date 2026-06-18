import subprocess
result = subprocess.run(
    [r"c:\Users\15116\Desktop\book\pgsql\pgsql\bin\pg_ctl", "-D", r"c:\Users\15116\Desktop\book\pgsql\data", "start"],
    capture_output=True, text=True
)
print("stdout:", result.stdout)
print("stderr:", result.stderr)
print("returncode:", result.returncode)
