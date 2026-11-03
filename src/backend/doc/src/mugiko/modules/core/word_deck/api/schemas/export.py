"""API schemas for export operations."""
from pydantic import BaseModel, Field


class CsvExportParams(BaseModel):
    """CSV export query parameters."""
    delimiter: str = Field(default=",", description="CSV delimiter")
    include_header: bool = Field(default=True, description="Include header row")