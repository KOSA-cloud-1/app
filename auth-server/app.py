
import jwt
import datetime
from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# Define a Pydantic model for login request
class LoginRequest(BaseModel):
    username: str
    password: str

app = FastAPI()

# Configure CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
)

# In a real application, this secret key should be complex and stored securely.
SECRET_KEY = 'your-super-secret-key-change-it' # Moved from app.config

@app.post('/login')
async def login(user_credentials: LoginRequest):
    """
    Handles user login.
    Expects a JSON payload with 'username' and 'password'.
    """
    username = user_credentials.username
    password = user_credentials.password

    # Hardcoded credentials for demonstration purposes.
    # In a real-world scenario, you would validate against a user database.
    if username == 'admin' and password == 'password':
        # Create the JWT token
        token = jwt.encode({
            'user': username,
            'exp': datetime.datetime.utcnow() + datetime.timedelta(hours=1)
        }, SECRET_KEY, algorithm="HS256")

        return {'token': token}

    raise HTTPException(status_code=401, detail="Invalid credentials")

# The if __name__ == '__main__': block is removed as Uvicorn will run the app directly.
# Example command to run with Uvicorn: uvicorn app:app --host 0.0.0.0 --port 5001
