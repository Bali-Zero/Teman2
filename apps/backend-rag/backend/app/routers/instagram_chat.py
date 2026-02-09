from fastapi import APIRouter
router = APIRouter(prefix="/api/instagram", tags=["instagram"])
@router.get("/conversations")
async def get_ig_convs(): return []
@router.get("/messages/{user_id}")
async def get_ig_msgs(user_id: str): return []
