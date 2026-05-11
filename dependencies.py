from fastapi import Depends, HTTPException, Header
from sqlalchemy.orm import Session
from database import SessionLocal
from models import User
from jwt_handler import verify_token


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_current_user(
    authorization: str = Header(None),
    db: Session = Depends(get_db)
):
    if not authorization:
        raise HTTPException(status_code=401, detail="No token provided")
    
    try:
        token = authorization.split(" ")[1]
    except IndexError:
        raise HTTPException(status_code=401, detail="Invalid auth header")

    print("TOKEN RECEIVED:", token)       # 👈 add this
    payload = verify_token(token)
    print("PAYLOAD:", payload)            # 👈 add this

    if payload is None:
        raise HTTPException(status_code=401, detail="Invalid token")

    user_id = payload.get("sub")
    print("USER ID:", user_id)            # 👈 add this

    if user_id is None:
        raise HTTPException(status_code=401, detail="Invalid token payload")

    user = db.query(User).filter(User.id == user_id).first()
    print("USER FOUND:", user)            # 👈 add this

    if not user:
        raise HTTPException(status_code=401, detail="User not found")

    return user