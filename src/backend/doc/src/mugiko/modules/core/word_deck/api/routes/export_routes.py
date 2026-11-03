"""API routes for export operations."""
from fastapi import APIRouter, Depends, Query, Response
from uuid import UUID

from mugiko.modules.core.word_deck.api.schemas.export import CsvExportParams
from mugiko.modules.core.word_deck.api.dependencies import get_export_service
from mugiko.modules.core.word_deck.service.export_service import ExportService
from mugiko.modules.core.user_management.api.dependencies import require_user
from mugiko.modules.core.user_management.service.dtos import AuthContext
from mugiko.modules.core.word_deck.service.export.registry import registry


router = APIRouter(prefix="/decks/{deck_id}/export", tags=["word_deck"])


@router.get(
    "/csv",
    summary="Export deck as CSV",
    responses={
        200: {
            "description": "CSV file download",
            "content": {"text/csv": {}},
        }
    },
)
async def export_csv(
    deck_id: UUID,
    delimiter: str = Query(",", description="CSV delimiter"),
    include_header: bool = Query(True, description="Include header row"),
    auth_context: AuthContext = Depends(require_user),
    export_service: ExportService = Depends(get_export_service),
):
    """Export a deck as CSV file."""
    params = CsvExportParams(delimiter=delimiter, include_header=include_header)
    result = await export_service.export_deck(deck_id, auth_context.user_id, "csv", params)
    
    return Response(
        content=result.content,
        media_type=result.media_type,
        headers={
            "Content-Disposition": f'attachment; filename="{result.filename}"'
        },
    )


@router.get(
    "/formats",
    summary="List available export formats",
)
async def list_export_formats():
    """List available export formats."""
    return {"formats": registry.list_formats()}