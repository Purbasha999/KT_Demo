from pydantic import BaseModel, model_validator
from typing import Optional


class SchemaField(BaseModel):
    name:        str
    type:        str
    description: Optional[str] = ""
    constraints: Optional[list[str]] = []

    model_config = {"extra": "ignore"}


class SchemaTable(BaseModel):
    name:        str
    description: str
    fields:      list[SchemaField]

    model_config = {"extra": "ignore"}


class SchemaRelationship(BaseModel):
    from_field:  str = ""
    to_field:    str = ""
    type:        str = "FK"
    description: Optional[str] = ""

    model_config = {"extra": "ignore", "populate_by_name": True}

    @model_validator(mode="before")
    @classmethod
    def map_from_to(cls, values):
        if isinstance(values, dict):
            if "from" in values:
                values["from_field"] = values.pop("from")
            if "to" in values:
                values["to_field"] = values.pop("to")
        return values


class SchemaUploadRequest(BaseModel):
    tables:        list[SchemaTable]
    relationships: Optional[list[SchemaRelationship]] = []

    model_config = {"extra": "ignore"}  # drops "company" and "roles" keys silently


# Auth
class LoginRequest(BaseModel):
    firm_id:  str
    login_id: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type:   str = "bearer"
    is_admin:     bool
    display_name: str
    firm_id:      str


# Firm
class FirmListItem(BaseModel):
    firm_id:     str
    firm_name:   str
    description: Optional[str] = ""


# Roles
class RoleCreateRequest(BaseModel):
    role_name:         str
    allowed_tables:    list[str]
    allowed_documents: list[str] = ["*"]
    row_filters:       Optional[dict] = {}


class RoleResponse(BaseModel):
    role_id:           int
    role_name:         str
    allowed_tables:    list[str]
    allowed_documents: list[str] = ["*"]
    row_filters:       Optional[dict]


# Users
class UserCreateRequest(BaseModel):
    login_id:     str
    password:     str
    display_name: Optional[str] = ""
    role_id:      Optional[int] = None


class UserRoleAssignRequest(BaseModel):
    user_id: str
    role_id: int


class UserListItem(BaseModel):
    user_id:      str
    login_id:     str
    display_name: Optional[str]
    role_name:    Optional[str]
    role_id:      Optional[int]


# Chat
class ChatRequest(BaseModel):
    question: str


class ChatResponse(BaseModel):
    answer:     str
    rows_count: Optional[int] = None
    attempts:   Optional[int] = None


# Documents
class DocumentUploadResponse(BaseModel):
    filename:        str
    chunks_ingested: int
    status:          str


class DocumentListItem(BaseModel):
    filename:     str
    chunks_count: int
    description:  Optional[str] = None
    uploaded_at:  Optional[str] = None