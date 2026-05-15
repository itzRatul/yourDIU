from fastapi import APIRouter
from .auth     import router as auth_router
from .routines import router as routines_router
from .teachers import router as teachers_router
from .chat     import router as chat_router

# Phase 4+ routers
# from .community     import router as community_router
# from .notices       import router as notices_router
# from .notifications import router as notifications_router

api_router = APIRouter()
api_router.include_router(auth_router)
api_router.include_router(routines_router)
api_router.include_router(teachers_router)
api_router.include_router(chat_router)
