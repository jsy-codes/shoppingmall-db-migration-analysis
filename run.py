import subprocess
import time
# backend 실행
backend = subprocess.Popen(
    ["uvicorn", "backend.app:app", "--reload"],
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