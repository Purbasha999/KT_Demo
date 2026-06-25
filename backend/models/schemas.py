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


class SuperAdminLoginRequest(BaseModel):
    login_id: str
    password: str


class TokenResponse(BaseModel):
    access_token:  str
    token_type:    str  = "bearer"
    is_admin:      bool
    is_superadmin: bool = False
    display_name:  str
    firm_id:       str  = ""


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


class UserUpdateRequest(BaseModel):
    login_id:     str
    display_name: Optional[str] = ""
    password:     Optional[str] = None
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


# Superadmin schemas
class FirmCreateRequest(BaseModel):
    firm_id:     str
    firm_name:   str
    description: Optional[str] = ""
    db_type:     str            = "none"
    db_host:     Optional[str] = None
    db_port:     Optional[int] = None
    db_name:     Optional[str] = None
    db_user:     Optional[str] = None
    db_password: Optional[str] = None
    mongo_uri:   Optional[str] = None


class FirmUpdateRequest(BaseModel):
    firm_name:   str
    description: Optional[str] = ""
    db_type:     str            = "none"
    db_host:     Optional[str] = None
    db_port:     Optional[int] = None
    db_name:     Optional[str] = None
    db_user:     Optional[str] = None
    db_password: Optional[str] = None
    mongo_uri:   Optional[str] = None


class FirmDetailItem(BaseModel):
    firm_id:          str
    firm_name:        str
    description:      Optional[str] = ""
    db_type:          str
    db_host:          Optional[str] = None
    db_port:          Optional[int] = None
    db_name:          Optional[str] = None
    db_user:          Optional[str] = None
    created_at:       Optional[str] = None
    last_accessed_at: Optional[str] = None
    user_count:       int = 0
    admin_count:      int = 0


class AdminCreateRequest(BaseModel):
    firm_id:      str
    login_id:     str
    display_name: Optional[str] = ""
    password:     str


class AdminUpdateRequest(BaseModel):
    login_id:     str
    display_name: Optional[str] = ""
    password:     Optional[str] = None


class AdminListItem(BaseModel):
    user_id:      str
    firm_id:      str
    firm_name:    str
    login_id:     str
    display_name: Optional[str] = None
    created_at:   Optional[str] = None


class SuperAdminUserItem(BaseModel):
    user_id:      str
    firm_id:      str
    firm_name:    str
    login_id:     str
    display_name: Optional[str] = None
    role_name:    Optional[str] = None
    created_at:   Optional[str] = None


class SuperAdminUserUpdateRequest(BaseModel):
    login_id:     str
    display_name: Optional[str] = ""
    password:     Optional[str] = None


# Chat
class HistoryMessage(BaseModel):
    role:    str   # "user" | "assistant"
    content: str


class ChatRequest(BaseModel):
    question: str
    history:  list[HistoryMessage] = []


class ChatResponse(BaseModel):
    answer:     str
    rows_count: Optional[int]  = None
    attempts:   Optional[int]  = None
    chart_data: Optional[dict] = None


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