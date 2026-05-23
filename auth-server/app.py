
import os
import jwt
import datetime
from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

class LoginRequest(BaseModel):
    username: str
    password: str

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

SECRET_KEY     = os.environ['JWT_SECRET_KEY']
ADMIN_USERNAME = os.environ.get('ADMIN_USERNAME', 'admin')
ADMIN_PASSWORD = os.environ['ADMIN_PASSWORD']

@app.post('/login')
async def login(user_credentials: LoginRequest):
    username = user_credentials.username
    password = user_credentials.password

    if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
        # Create the JWT token
        token = jwt.encode({
            'user': username,
            'exp': datetime.datetime.utcnow() + datetime.timedelta(hours=1)
        }, SECRET_KEY, algorithm="HS256")

        return {'token': token}

    raise HTTPException(status_code=401, detail="Invalid credentials")

@app.get("/health")
def health_check():
    """
    Docker HEALTHCHECK를 위한 간단한 엔드포인트.
    성공적으로 응답하면 'ok' 상태를 반환합니다.
    """
    return {"status": "health ok"}


@app.get("/ready")
def ready_check():
    """
    Docker HEALTHCHECK를 위한 간단한 엔드포인트.
    성공적으로 응답하면 'ok' 상태를 반환합니다.
    """
    return {"status": "ready ok"}

# The if __name__ == '__main__': block is removed as Uvicorn will run the app directly.
# Example command to run with Uvicorn: uvicorn app:app --host 0.0.0.0 --port 5001
