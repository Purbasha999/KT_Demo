import uuid
from fastapi import APIRouter, HTTPException, Depends

from core.security import require_superadmin, hash_password, encrypt_value
from models.schemas import (
    FirmCreateRequest, FirmUpdateRequest, FirmDetailItem,
    AdminCreateRequest, AdminUpdateRequest, AdminListItem,
    SuperAdminUserItem, SuperAdminUserUpdateRequest,
)
import db.platform_db as pdb
from rag.vector_store import delete_all_by_firm

router = APIRouter(dependencies=[Depends(require_superadmin)])


# ── Dashboard ─────────────────────────────────────────────────────────────────
@router.get("/stats")
async def get_stats(_=Depends(require_superadmin)):
    return await pdb.get_superadmin_stats()


# ── Firms ─────────────────────────────────────────────────────────────────────
@router.get("/firms", response_model=list[FirmDetailItem])
async def list_firms(_=Depends(require_superadmin)):
    return await pdb.get_all_firms_detailed()


@router.get("/firms-list")
async def firms_list(_=Depends(require_superadmin)):
    return await pdb.get_firms_list()


@router.post("/firm", status_code=201)
async def create_firm(body: FirmCreateRequest, _=Depends(require_superadmin)):
    if await pdb.get_firm(body.firm_id):
        raise HTTPException(status_code=400, detail="Firm ID already exists.")

    db_password_enc = encrypt_value(body.db_password) if body.db_password else None
    mongo_uri_enc   = encrypt_value(body.mongo_uri)   if body.mongo_uri   else None

    await pdb.create_firm(
        firm_id=body.firm_id,
        firm_name=body.firm_name,
        description=body.description or "",
        db_type=body.db_type,
        db_host=body.db_host,
        db_port=body.db_port,
        db_name=body.db_name,
        db_user=body.db_user,
        db_password_enc=db_password_enc,
        mongo_uri_enc=mongo_uri_enc,
    )
    return {"message": "Firm created", "firm_id": body.firm_id}


@router.put("/firm/{firm_id}", status_code=200)
async def update_firm(firm_id: str, body: FirmUpdateRequest, _=Depends(require_superadmin)):
    if not await pdb.get_firm(firm_id):
        raise HTTPException(status_code=404, detail="Firm not found.")

    db_password_enc = encrypt_value(body.db_password) if body.db_password else None
    mongo_uri_enc   = encrypt_value(body.mongo_uri)   if body.mongo_uri   else None

    await pdb.update_firm(
        firm_id=firm_id,
        firm_name=body.firm_name,
        description=body.description or "",
        db_type=body.db_type,
        db_host=body.db_host,
        db_port=body.db_port,
        db_name=body.db_name,
        db_user=body.db_user,
        db_password_enc=db_password_enc,
        mongo_uri_enc=mongo_uri_enc,
    )
    return {"message": "Firm updated"}


@router.delete("/firm/{firm_id}", status_code=204)
async def delete_firm(firm_id: str, _=Depends(require_superadmin)):
    if not await pdb.get_firm(firm_id):
        raise HTTPException(status_code=404, detail="Firm not found.")
    try:
        await delete_all_by_firm(firm_id)
    except Exception:
        pass  # Qdrant may be offline; proceed with DB deletion
    await pdb.delete_firm(firm_id)


# ── Admins ────────────────────────────────────────────────────────────────────
@router.get("/admins", response_model=list[AdminListItem])
async def list_admins(_=Depends(require_superadmin)):
    return await pdb.get_all_admins()


@router.post("/admin", status_code=201)
async def create_admin(body: AdminCreateRequest, _=Depends(require_superadmin)):
    if not await pdb.get_firm(body.firm_id):
        raise HTTPException(status_code=404, detail="Firm not found.")
    if await pdb.get_user_by_login(body.firm_id, body.login_id):
        raise HTTPException(status_code=400, detail="Login ID already exists for this firm.")

    user_id = str(uuid.uuid4())
    await pdb.create_admin(
        user_id=user_id,
        firm_id=body.firm_id,
        login_id=body.login_id,
        password_hash=hash_password(body.password),
        display_name=body.display_name or body.login_id,
    )
    return {"message": "Admin created", "user_id": user_id}


@router.put("/admin/{user_id}", status_code=200)
async def update_admin(user_id: str, body: AdminUpdateRequest, _=Depends(require_superadmin)):
    password_hash = hash_password(body.password) if body.password else None
    await pdb.update_admin(
        user_id=user_id,
        display_name=body.display_name or body.login_id,
        login_id=body.login_id,
        password_hash=password_hash,
    )
    return {"message": "Admin updated"}


@router.delete("/admin/{user_id}", status_code=204)
async def delete_admin(user_id: str, _=Depends(require_superadmin)):
    await pdb.delete_admin(user_id)


# ── Users ─────────────────────────────────────────────────────────────────────
@router.get("/users", response_model=list[SuperAdminUserItem])
async def list_users(_=Depends(require_superadmin)):
    return await pdb.get_all_users_superadmin()


@router.put("/user/{user_id}", status_code=200)
async def update_user(user_id: str, body: SuperAdminUserUpdateRequest, _=Depends(require_superadmin)):
    password_hash = hash_password(body.password) if body.password else None
    await pdb.update_user_superadmin(
        user_id=user_id,
        display_name=body.display_name or body.login_id,
        login_id=body.login_id,
        password_hash=password_hash,
    )
    return {"message": "User updated"}


@router.delete("/user/{user_id}", status_code=204)
async def delete_user(user_id: str, _=Depends(require_superadmin)):
    await pdb.delete_user_superadmin(user_id)
