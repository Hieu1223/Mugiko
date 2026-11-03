"""API routes for word operations."""
from fastapi import APIRouter, Depends, Query, Response, status
from uuid import UUID
from typing import AsyncGenerator

from mugiko.modules.core.word_deck.api.schemas.word import (
    DeckWordCreateRequest,
    DeckWordUpdateRequest,
    DeckWordResponse,
    PaginatedDeckWordsResponse,
)
from mugiko.modules.core.word_deck.api.dependencies import get_word_service
from mugiko.modules.core.word_deck.service.word_service import WordService
from mugiko.modules.core.user_management.api.dependencies import require_user
from mugiko.modules.core.user_management.service.dtos import AuthContext


router = APIRouter(prefix="/decks/{deck_id}/words", tags=["word_deck"])


@router.post(
    "",
    response_model=DeckWordResponse,
    status_code=status.HTTP_201_CREATED,
)
async def add_word(
    deck_id: UUID,
    request: DeckWordCreateRequest,
    response: Response,
    auth_context: AuthContext = Depends(require_user),
    word_service: WordService = Depends(get_word_service),
):
    """Add a word to a deck."""
    from mugiko.modules.core.word_deck.persistent.dtos import CreateDeckWordRequest
    service_request = CreateDeckWordRequest(word=request.word, meaning=request.meaning)
    word = await word_service.add_word(deck_id, auth_context.user_id, service_request)
    return DeckWordResponse(
        id=word.id,
        deck_id=word.deck_id,
        word=word.word,
        meaning=word.meaning,
        created_at=word.created_at,
        updated_at=word.updated_at,
    )


@router.get(
    "",
    response_model=PaginatedDeckWordsResponse,
)
async def list_words(
    deck_id: UUID,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    auth_context: AuthContext = Depends(require_user),
    word_service: WordService = Depends(get_word_service),
):
    """List words in a deck with pagination."""
    result = await word_service.list_words(deck_id, auth_context.user_id, page, page_size)
    return PaginatedDeckWordsResponse(
        words=[
            DeckWordResponse(
                id=w.id,
                deck_id=w.deck_id,
                word=w.word,
                meaning=w.meaning,
                created_at=w.created_at,
                updated_at=w.updated_at,
            )
            for w in result.words
        ],
        total=result.total,
        page=result.page,
        page_size=result.page_size,
    )


@router.patch(
    "/{word_id}",
    response_model=DeckWordResponse,
)
async def update_word(
    deck_id: UUID,
    word_id: UUID,
    request: DeckWordUpdateRequest,
    auth_context: AuthContext = Depends(require_user),
    word_service: WordService = Depends(get_word_service),
):
    """Update a word."""
    from mugiko.modules.core.word_deck.persistent.dtos import UpdateDeckWordRequest
    service_request = UpdateDeckWordRequest(word=request.word, meaning=request.meaning)
    word = await word_service.update_word(word_id, auth_context.user_id, service_request)
    return DeckWordResponse(
        id=word.id,
        deck_id=word.deck_id,
        word=word.word,
        meaning=word.meaning,
        created_at=word.created_at,
        updated_at=word.updated_at,
    )


@router.delete(
    "/{word_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_word(
    deck_id: UUID,
    word_id: UUID,
    response: Response,
    auth_context: AuthContext = Depends(require_user),
    word_service: WordService = Depends(get_word_service),
):
    """Delete a word."""
    await word_service.delete_word(word_id, auth_context.user_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)