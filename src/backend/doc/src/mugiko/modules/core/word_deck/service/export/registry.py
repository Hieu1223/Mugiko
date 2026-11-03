"""Exporter registry for word deck module."""
from typing import TypeVar, Generic
from pydantic import BaseModel

from mugiko.modules.core.word_deck.service.export.base import DeckExporter, ExportParams, ExportResultDTO, P
from mugiko.modules.core.word_deck.service.export.csv_exporter import CsvExporter, CsvExportParams


class ExporterRegistry:
    """Registry for deck exporters."""

    def __init__(self):
        self._exporters: dict[str, DeckExporter] = {}
        self._params_schemas: dict[str, type[ExportParams]] = {}
        # Register built-in exporters
        self.register(CsvExporter())

    def register(self, exporter: DeckExporter[P]) -> None:
        """Register an exporter."""
        self._exporters[exporter.format_key] = exporter
        # We can't easily get the params type from the instance, so we'll map known ones
        if exporter.format_key == "csv":
            self._params_schemas["csv"] = CsvExportParams

    def get_exporter(self, format_key: str) -> DeckExporter | None:
        """Get an exporter by format key."""
        return self._exporters.get(format_key)

    def get_params_schema(self, format_key: str) -> type[ExportParams] | None:
        """Get the params schema for a format."""
        return self._params_schemas.get(format_key)

    def list_formats(self) -> list[str]:
        """List available export formats."""
        return list(self._exporters.keys())


# Global registry instance
registry = ExporterRegistry()