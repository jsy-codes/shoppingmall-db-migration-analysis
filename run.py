import subprocess
import time
import sys
# backend 실행
backend = subprocess.Popen(
    [sys.executable, "-m", "uvicorn", "backend.app:app", "--reload"],
    shell=True
)
time.sleep(3)
# frontend 실행
frontend = subprocess.Popen(
    ["npm", "run", "dev"],
    cwd="front",
    shell=True
)

backend.wait()
frontend.wait()