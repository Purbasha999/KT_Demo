from fastapi import APIRouter, Depends
from models.schemas import ChatRequest, ChatResponse
from core.security import get_current_user
from chat.service import handle_chat

router = APIRouter()

@router.post("/query", response_model=ChatResponse)
async def chat_query(body: ChatRequest, current_user: dict = Depends(get_current_user)):
    result = await handle_chat(
        question=body.question,
        user_id=current_user["sub"],
        firm_id=current_user["firm_id"],
    )
    return ChatResponse(**result)
