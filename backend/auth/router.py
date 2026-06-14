from fastapi import APIRouter, HTTPException, status
from models.schemas import LoginRequest, TokenResponse, FirmListItem
from core.security import verify_password, create_access_token
import db.platform_db as pdb

router = APIRouter()


@router.get("/firms", response_model=list[FirmListItem])
async def list_firms():
    return await pdb.get_all_firms()


@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest):
    user = await pdb.get_user_by_login(body.firm_id, body.login_id)
    if not user or not verify_password(body.password, user["password_hash"]):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    token = create_access_token({
        "sub":      user["user_id"],
        "firm_id":  user["firm_id"],
        "is_admin": bool(user["is_admin"]),
    })
    return TokenResponse(
        access_token=token,
        is_admin=bool(user["is_admin"]),
        display_name=user["display_name"] or user["login_id"],
        firm_id=user["firm_id"],
    )
