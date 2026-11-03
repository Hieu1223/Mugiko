"""API routes for lookup module."""
from fastapi import APIRouter, Depends

from mugiko.modules.core.lookup.api.schemas.lookup import (
    DictionaryEntrySchema,
    PrefixSearchResponseSchema,
    KanjiEntrySchema,
    WordLookupRequest,
    PrefixSearchRequest,
    KanjiLookupRequest,
    DictionaryReadingSchema,
)
from mugiko.modules.core.lookup.api.dependencies import get_lookup_service

router = APIRouter(prefix="/lookup", tags=["lookup"])


@router.post(
    "/word",
    response_model=DictionaryEntrySchema,
    summary="Look up a word in the dictionary",
)
async def lookup_word(
    request: WordLookupRequest,
    lookup_service=Depends(get_lookup_service),
) -> DictionaryEntrySchema:
    """Look up a word in the Japanese dictionary."""
    result = lookup_service.lookup_word(request.word)
    return DictionaryEntrySchema(
        word=result.word,
        readings=[DictionaryReadingSchema(kana=r["kana"], meaning=r["meaning"]) for r in result.readings],
    )


@router.post(
    "/prefix",
    response_model=PrefixSearchResponseSchema,
    summary="Search words by prefix",
)
async def prefix_search(
    request: PrefixSearchRequest,
    lookup_service=Depends(get_lookup_service),
) -> PrefixSearchResponseSchema:
    """Search for words starting with the given prefix."""
    result = lookup_service.prefix_search(request.prefix, request.limit)
    return PrefixSearchResponseSchema(
        entries=[
            DictionaryEntrySchema(
                word=e.word,
                readings=[DictionaryReadingSchema(kana=r["kana"], meaning=r["meaning"]) for r in e.readings],
            )
            for e in result.entries
        ],
        count=result.count,
    )


@router.post(
    "/kanji",
    response_model=KanjiEntrySchema,
    summary="Look up a kanji character",
)
async def lookup_kanji(
    request: KanjiLookupRequest,
    lookup_service=Depends(get_lookup_service),
) -> KanjiEntrySchema:
    """Look up a single kanji character in the kanji dictionary."""
    result = lookup_service.lookup_kanji(request.kanji)
    return KanjiEntrySchema(
        kanji=result.kanji,
        reading=result.reading,
        meanings=result.meanings,
        strokes=result.strokes,
        radical=result.radical,
        penstrokes=result.penstrokes,
        shape=result.shape,
        unicode=result.unicode,
    )