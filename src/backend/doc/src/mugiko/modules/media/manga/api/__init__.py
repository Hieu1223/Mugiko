"""Manga module API router."""
from fastapi import APIRouter

from mugiko.modules.media.manga.api.routes import (
    providers,
    subscriptions,
    history,
    settings,
    builtin,
)

router = APIRouter()

router.include_router(providers.router)
router.include_router(subscriptions.router)
router.include_router(history.router)
router.include_router(settings.router)
router.include_router(builtin.router)