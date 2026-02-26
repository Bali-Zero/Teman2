from fastapi import APIRouter

router = APIRouter(prefix="/api/twitter", tags=["twitter"])


@router.get("/conversations")
async def get_tw_convs():
    return []


@router.get("/messages/{user_id}")
async def get_tw_msgs(user_id: str):
    return []
