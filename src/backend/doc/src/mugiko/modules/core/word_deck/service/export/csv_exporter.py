"""CSV exporter for word deck module."""
import csv
import io
from typing import Optional
from pydantic import BaseModel, Field

from mugiko.modules.core.word_deck.service.export.base import DeckExporter, ExportParams, ExportResultDTO
from mugiko.modules.core.word_deck.persistent.dtos import DeckDTO, DeckWordDTO


class CsvExportParams(ExportParams):
    """Parameters for CSV export."""
    delimiter: str = Field(default=",", description="CSV delimiter")
    include_header: bool = Field(default=True, description="Include header row")


class CsvExporter(DeckExporter[CsvExportParams]):
    """CSV exporter implementation."""
    format_key = "csv"

    async def export(self, deck: DeckDTO, words: list[DeckWordDTO], params: CsvExportParams) -> ExportResultDTO:
        """Export deck to CSV format."""
        output = io.StringIO()
        writer = csv.writer(output, delimiter=params.delimiter)

        if params.include_header:
            writer.writerow(["word", "meaning"])

        for word in words:
            writer.writerow([word.word, word.meaning])

        # Get the content and encode as UTF-8 with BOM for Excel compatibility
        content_str = output.getvalue()
        content_bytes = "\ufeff".encode("utf-8") + content_str.encode("utf-8")

        return ExportResultDTO(
            content=content_bytes,
            media_type="text/csv; charset=utf-8",
            filename=f"{deck.name}.csv",
        )