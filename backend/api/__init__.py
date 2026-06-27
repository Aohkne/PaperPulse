from fastapi import APIRouter

from backend.api.admin import router as admin_router
from backend.api.auth import router as auth_router
from backend.api.chat import router as chat_router
from backend.api.community import admin_router as community_admin_router
from backend.api.community import router as community_router
from backend.api.notifications import router as notifications_router
from backend.api.topics import router as topics_router
from backend.api.reviews import router as reviews_router
from backend.agent.gap_detection.router import router as gap_router
from backend.module.payment.api.billing import router as billing_router
from backend.module.pdf_agent.api.annotations import router as pdf_agent_annotations_router
from backend.module.pdf_agent.api.bundle import router as pdf_agent_bundle_router
from backend.module.pdf_agent.api.save import router as pdf_agent_save_router
from backend.module.pdf_agent.api.selection import router as pdf_agent_selection_router
from backend.module.pdf_agent.api.upload import router as pdf_agent_upload_router
from backend.module.research_agent.api.research import router as research_router

api_router = APIRouter()
api_router.include_router(auth_router)
api_router.include_router(admin_router)
api_router.include_router(chat_router)
api_router.include_router(notifications_router)
api_router.include_router(topics_router)
api_router.include_router(reviews_router)
api_router.include_router(community_router)
api_router.include_router(community_admin_router)
api_router.include_router(gap_router)
api_router.include_router(billing_router)
api_router.include_router(research_router)
api_router.include_router(pdf_agent_upload_router)
api_router.include_router(pdf_agent_bundle_router)
api_router.include_router(pdf_agent_annotations_router)
api_router.include_router(pdf_agent_selection_router)
api_router.include_router(pdf_agent_save_router)


