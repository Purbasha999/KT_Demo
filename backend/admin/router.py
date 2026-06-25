import uuid
from typing import Optional
from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, Form, Query

from core.security import require_admin, hash_password
from core.config import settings
from models.schemas import (
    SchemaUploadRequest,
    RoleCreateRequest, RoleResponse,
    UserCreateRequest, UserUpdateRequest, UserRoleAssignRequest, UserListItem,
    DocumentUploadResponse, DocumentListItem,
)
import db.platform_db as pdb
from rag.ingestion import ingest_pdf
from rag.vector_store import delete_by_firm_and_source

router = APIRouter(dependencies=[Depends(require_admin)])


# Schema 
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


# Roles
@router.post("/role", response_model=RoleResponse, status_code=201)
async def create_role(body: RoleCreateRequest, admin=Depends(require_admin)):
    firm_id = admin["firm_id"]
    schema  = await pdb.get_schema(firm_id)

    if schema and body.allowed_tables not in (["*"], []):
        valid   = {t["name"] for t in schema["tables"]}
        invalid = [t for t in body.allowed_tables if t not in valid]
        if invalid:
            raise HTTPException(
                status_code=400,
                detail=f"Tables not in schema: {invalid}. Valid: {sorted(valid)}"
            )

    role_id = await pdb.create_or_update_role(
        firm_id, body.role_name, body.allowed_tables,
        body.allowed_documents, body.row_filters,
    )
    return RoleResponse(
        role_id=role_id, role_name=body.role_name,
        allowed_tables=body.allowed_tables,
        allowed_documents=body.allowed_documents,
        row_filters=body.row_filters,
    )


@router.get("/roles", response_model=list[RoleResponse])
async def list_roles(admin=Depends(require_admin)):
    return await pdb.get_roles_for_firm(admin["firm_id"])


@router.put("/role/{role_id}", response_model=RoleResponse)
async def update_role(role_id: int, body: RoleCreateRequest, admin=Depends(require_admin)):
    firm_id = admin["firm_id"]
    role = await pdb.get_role(role_id)
    if not role or role["firm_id"] != firm_id:
        raise HTTPException(status_code=404, detail="Role not found.")

    schema = await pdb.get_schema(firm_id)
    if schema and body.allowed_tables not in (["*"], []):
        valid   = {t["name"] for t in schema["tables"]}
        invalid = [t for t in body.allowed_tables if t not in valid]
        if invalid:
            raise HTTPException(status_code=400, detail=f"Tables not in schema: {invalid}")

    await pdb.update_role(role_id, firm_id, body.role_name,
                          body.allowed_tables, body.allowed_documents, body.row_filters)
    return RoleResponse(role_id=role_id, role_name=body.role_name,
                        allowed_tables=body.allowed_tables,
                        allowed_documents=body.allowed_documents,
                        row_filters=body.row_filters)


@router.delete("/role/{role_id}", status_code=204)
async def delete_role(role_id: int, admin=Depends(require_admin)):
    role = await pdb.get_role(role_id)
    if not role or role["firm_id"] != admin["firm_id"]:
        raise HTTPException(status_code=404, detail="Role not found.")
    await pdb.delete_role(role_id)


@router.delete("/user/{user_id}", status_code=204)
async def delete_user(user_id: str, admin=Depends(require_admin)):
    await pdb.delete_user(user_id, admin["firm_id"])


# Users
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


@router.put("/user/{user_id}", status_code=200)
async def update_user(user_id: str, body: UserUpdateRequest, admin=Depends(require_admin)):
    firm_id = admin["firm_id"]
    user = await pdb.get_user_by_id(user_id, firm_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")
    password_hash = hash_password(body.password) if body.password else None
    await pdb.update_user_details(
        user_id, firm_id,
        body.display_name or body.login_id,
        body.login_id,
        password_hash,
    )
    if body.role_id is not None:
        await pdb.assign_role_to_user(user_id, body.role_id)
    return {"message": "User updated"}


@router.post("/user/assign-role")
async def assign_role(body: UserRoleAssignRequest, admin=Depends(require_admin)):
    await pdb.assign_role_to_user(body.user_id, body.role_id)
    return {"message": "Role assigned"}


# Documents 
@router.post("/documents/upload", response_model=DocumentUploadResponse, status_code=201)
async def upload_document(
    file: UploadFile = File(...),
    replace: bool = Query(True, description="Replace existing vectors for this file"),
    description: Optional[str] = Form(None),
    admin=Depends(require_admin),
):
    firm_id  = admin["firm_id"]
    filename = file.filename or "upload.pdf"

    if not filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are accepted.")

    contents  = await file.read()
    max_bytes = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024
    if len(contents) > max_bytes:
        raise HTTPException(
            status_code=413,
            detail=f"File exceeds the {settings.MAX_UPLOAD_SIZE_MB} MB limit.",
        )

    try:
        result = await ingest_pdf(contents, filename, firm_id, replace=replace)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Ingestion failed: {exc}")

    if result["status"] == "success":
        await pdb.save_document_record(firm_id, filename, result["chunks_ingested"], description)

    return DocumentUploadResponse(
        filename=filename,
        chunks_ingested=result["chunks_ingested"],
        status=result["status"],
    )


@router.get("/documents", response_model=list[DocumentListItem])
async def list_documents(admin=Depends(require_admin)):
    return await pdb.get_documents_for_firm(admin["firm_id"])


@router.delete("/documents/{filename}", status_code=204)
async def delete_document(filename: str, admin=Depends(require_admin)):
    firm_id = admin["firm_id"]
    try:
        await delete_by_firm_and_source(firm_id, filename)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Vector deletion failed: {exc}")
    await pdb.delete_document_record(firm_id, filename)
