import os

from datetime import datetime, timedelta, timezone

from dotenv import load_dotenv

from fastapi import Depends, HTTPException

from fastapi.security import (
    HTTPAuthorizationCredentials,
    HTTPBearer
)

from jose import JWTError, jwt

from passlib.context import CryptContext

from sqlalchemy.orm import Session

from database import get_db

from model import User


load_dotenv()


SECRET_KEY = os.getenv("SECRET_KEY")

if not SECRET_KEY:
    raise RuntimeError(
        "SECRET_KEY missing in .env"
    )


ALGORITHM = "HS256"

EXPIRE_MINUTES = int(
    os.getenv(
        "ACCESS_TOKEN_EXPIRE_MINUTES",
        "120"
    )
)


pwd_context = CryptContext(
    schemes=["bcrypt"],
    deprecated="auto"
)


security = HTTPBearer()


def _fit(password):
    # bcrypt only uses the first 72 bytes; newer versions raise an error on longer input
    return password.encode("utf-8")[:72].decode("utf-8", "ignore")


def hash_password(password):
    return pwd_context.hash(_fit(password))


def verify_password(
    password,
    password_hash
):

    return pwd_context.verify(
        _fit(password),
        password_hash
    )


def create_access_token(
    user_id,
    role
):

    expire = (
        datetime.now(timezone.utc)
        + timedelta(minutes=EXPIRE_MINUTES)
    )

    payload = {
        "sub": str(user_id),
        "role": role,
        "exp": expire
    }

    return jwt.encode(
        payload,
        SECRET_KEY,
        algorithm=ALGORITHM
    )


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
):

    try:

        payload = jwt.decode(
            credentials.credentials,
            SECRET_KEY,
            algorithms=[ALGORITHM]
        )

        user_id = int(
            payload.get("sub")
        )

    except (
        JWTError,
        ValueError,
        TypeError
    ):

        raise HTTPException(
            status_code=401,
            detail="Invalid or expired token"
        )

    user = db.get(
        User,
        user_id
    )

    if not user:

        raise HTTPException(
            status_code=401,
            detail="User not found"
        )

    return user


def require_admin(
    user=Depends(get_current_user)
):

    if user.role != "admin":

        raise HTTPException(
            status_code=403,
            detail="Admin access required"
        )

    return user