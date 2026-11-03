"""API routes for deck operations."""
from fastapi import APIRouter, Depends, Query, Response, status
from uuid import UUID
from typing import AsyncGenerator

from mugiko.modules.core.word_deck.api.schemas.deck import (
    DeckCreateRequest,
    DeckUpdateRequest,
    DeckResponse,
    PaginatedDecksResponse,
)
from mugiko.modules.core.word_deck.api.dependencies import get_deck_service
from mugiko.modules.core.word_deck.service.deck_service import DeckService
from mugiko.modules.core.user_management.api.dependencies import require_user
from mugiko.modules.core.user_management.service.dtos import AuthContext


router = APIRouter(prefix="/decks", tags=["word_deck"])


@router.post(
    "",
    response_model=DeckResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_deck(
    request: DeckCreateRequest,
    response: Response,
    auth_context: AuthContext = Depends(require_user),
    deck_service: DeckService = Depends(get_deck_service),
):
    """Create a new deck."""
    from mugiko.modules.core.word_deck.persistent.dtos import CreateDeckRequest
    service_request = CreateDeckRequest(name=request.name)
    deck = await deck_service.create_deck(auth_context.user_id, service_request)
    return DeckResponse(
        id=deck.id,
        owner_id=deck.owner_id,
        name=deck.name,
        created_at=deck.created_at,
        updated_at=deck.updated_at,
    )


@router.get(
    "",
    response_model=PaginatedDecksResponse,
)
async def list_decks(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    auth_context: AuthContext = Depends(require_user),
    deck_service: DeckService = Depends(get_deck_service),
):
    """List user's decks with pagination."""
    result = await deck_service.list_decks(auth_context.user_id, page, page_size)
    return PaginatedDecksResponse(
        decks=[
            DeckResponse(
                id=d.id,
                owner_id=d.owner_id,
                name=d.name,
                created_at=d.created_at,
                updated_at=d.updated_at,
            )
            for d in result.decks
        ],
        total=result.total,
        page=result.page,
        page_size=result.page_size,
    )


@router.get(
    "/{deck_id}",
    response_model=DeckResponse,
)
async def get_deck(
    deck_id: UUID,
    auth_context: AuthContext = Depends(require_user),
    deck_service: DeckService = Depends(get_deck_service),
):
    """Get a deck by ID."""
    deck = await deck_service.get_deck(deck_id, auth_context.user_id)
    return DeckResponse(
        id=deck.id,
        owner_id=deck.owner_id,
        name=deck.name,
        created_at=deck.created_at,
        updated_at=deck.updated_at,
    )


@router.patch(
    "/{deck_id}",
    response_model=DeckResponse,
)
async def update_deck(
    deck_id: UUID,
    request: DeckUpdateRequest,
    auth_context: AuthContext = Depends(require_user),
    deck_service: DeckService = Depends(get_deck_service),
):
    """Update a deck."""
    from mugiko.modules.core.word_deck.persistent.dtos import UpdateDeckRequest
    service_request = UpdateDeckRequest(name=request.name)
    deck = await deck_service.update_deck(deck_id, auth_context.user_id, service_request)
    return DeckResponse(
        id=deck.id,
        owner_id=deck.owner_id,
        name=deck.name,
        created_at=deck.created_at,
        updated_at=deck.updated_at,
    )


@router.delete(
    "/{deck_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_deck(
    deck_id: UUID,
    response: Response,
    auth_context: AuthContext = Depends(require_user),
    deck_service: DeckService = Depends(get_deck_service),
):
    """Delete a deck."""
    await deck_service.delete_deck(deck_id, auth_context.user_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)