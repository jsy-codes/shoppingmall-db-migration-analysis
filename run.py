import subprocess

# backend 실행
backend = subprocess.Popen(
    ["uvicorn", "backend.app:app", "--reload"],
    shell=True
)

# frontend 실행
frontend = subprocess.Popen(
    ["npm", "run", "dev"],
    cwd="front",
    shell=True
)

backend.wait()
frontend.wait()