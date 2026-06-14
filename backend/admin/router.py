import uuid
from fastapi import APIRouter, HTTPException, Depends

from core.security import require_admin, hash_password
from models.schemas import (
    SchemaUploadRequest,
    RoleCreateRequest, RoleResponse,
    UserCreateRequest, UserRoleAssignRequest, UserListItem,
)
import db.platform_db as pdb

router = APIRouter(dependencies=[Depends(require_admin)])


# ── Schema ───

@router.post("/schema")
async def upload_schema(body: SchemaUploadRequest, admin=Depends(require_admin)):
    firm_id = admin["firm_id"]
    await pdb.save_schema(firm_id, body.model_dump())
    return {"message": "Schema saved", "tables": len(body.tables)}


@router.get("/schema")
async def get_schema(admin=Depends(require_admin)):
    schema = await pdb.get_schema(admin["firm_id"])
    if not schema:
        raise HTTPException(status_code=404, detail="No schema uploaded yet.")
    return schema


# ── Roles ─────────────────────────────────────────────────────────────────────

@router.post("/role", response_model=RoleResponse, status_code=201)
async def create_role(body: RoleCreateRequest, admin=Depends(require_admin)):
    firm_id = admin["firm_id"]
    schema  = await pdb.get_schema(firm_id)
    if not schema:
        raise HTTPException(status_code=400, detail="Upload your schema before creating roles.")

    if body.allowed_tables != ["*"]:
        valid   = {t["name"] for t in schema["tables"]}
        invalid = [t for t in body.allowed_tables if t not in valid]
        if invalid:
            raise HTTPException(
                status_code=400,
                detail=f"Tables not in schema: {invalid}. Valid: {sorted(valid)}"
            )

    role_id = await pdb.create_or_update_role(
        firm_id, body.role_name, body.allowed_tables, body.row_filters
    )
    return RoleResponse(
        role_id=role_id, role_name=body.role_name,
        allowed_tables=body.allowed_tables, row_filters=body.row_filters,
    )


@router.get("/roles", response_model=list[RoleResponse])
async def list_roles(admin=Depends(require_admin)):
    return await pdb.get_roles_for_firm(admin["firm_id"])


@router.delete("/role/{role_id}", status_code=204)
async def delete_role(role_id: int, admin=Depends(require_admin)):
    role = await pdb.get_role(role_id)
    if not role or role["firm_id"] != admin["firm_id"]:
        raise HTTPException(status_code=404, detail="Role not found.")
    await pdb.delete_role(role_id)


# ── Users ─────────────────────────────────────────────────────────────────────

@router.post("/user", status_code=201)
async def create_user(body: UserCreateRequest, admin=Depends(require_admin)):
    firm_id = admin["firm_id"]
    if await pdb.get_user_by_login(firm_id, body.login_id):
        raise HTTPException(status_code=400, detail="Login ID already exists.")

    user_id = str(uuid.uuid4())
    await pdb.create_user(
        user_id=user_id, firm_id=firm_id, login_id=body.login_id,
        password_hash=hash_password(body.password),
        display_name=body.display_name or body.login_id,
        is_admin=False,
    )
    if body.role_id:
        await pdb.assign_role_to_user(user_id, body.role_id)
    return {"message": "User created", "user_id": user_id}


@router.get("/users", response_model=list[UserListItem])
async def list_users(admin=Depends(require_admin)):
    return await pdb.get_users_for_firm(admin["firm_id"])


@router.post("/user/assign-role")
async def assign_role(body: UserRoleAssignRequest, admin=Depends(require_admin)):
    await pdb.assign_role_to_user(body.user_id, body.role_id)
    return {"message": "Role assigned"}
