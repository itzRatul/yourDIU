from fastapi import APIRouter
from .auth import router as auth_router

# Phase 2+ routers will be imported and included here
# from .chat          import router as chat_router
# from .community     import router as community_router
# from .notices       import router as notices_router
# from .notifications import router as notifications_router

api_router = APIRouter()
api_router.include_router(auth_router)
