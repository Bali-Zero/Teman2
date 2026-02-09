from fastapi import APIRouter
router = APIRouter(prefix="/api/telegram", tags=["telegram"])
@router.get("/conversations")
async def get_tg_convs(): return []
@router.get("/messages/{chat_id}")
async def get_tg_msgs(chat_id: str): return []
