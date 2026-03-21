from fastapi import APIRouter, Depends

from api.deps import get_current_user
from api.models import User

router = APIRouter(prefix="/api", tags=["profile"])


@router.get("/profile")
async def get_profile(current_user: User = Depends(get_current_user)):
    return {"user_id": current_user.id, "email": current_user.email}
