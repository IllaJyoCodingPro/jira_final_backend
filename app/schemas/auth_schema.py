from pydantic import BaseModel
from typing import Optional

class LoginRequest(BaseModel):
    email: str
    password: str

class SignupRequest(BaseModel):
    username: str
    email: str
    password: str
    role: Optional[str] = "DEVELOPER"

class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str
