"""Lookup API dependencies."""
from mugiko.modules.core.lookup.service.lookup_service import LookupService


# Initialize service (stateless, no session needed)
lookup_service = LookupService()


def get_lookup_service() -> LookupService:
    """Get lookup service instance."""
    return lookup_service