"""Mirror the provider/service registry into PostgreSQL at worker startup.

The backend creates ``subtitles`` rows that reference ``subtitle_providers``
and ``subtitle_provider_services``. This bootstrap makes sure every provider
and service declared in code exists in those tables, without changing ids on
restarts (existing foreign keys stay valid).

The schema has no unique constraints on provider names or service keys, so a
transaction-scoped advisory lock serializes concurrent worker startups.
"""

import json
import logging
import uuid
from typing import Iterable

from ..provider.registry import ProviderInfo
from .db import Database

logger = logging.getLogger(__name__)

# Arbitrary application-specific key for pg_advisory_xact_lock.
_REGISTRY_SYNC_LOCK_KEY = 0x4D5547494B4F  # "MUGIKO" in ASCII


def sync_registry(db: Database, providers: Iterable[ProviderInfo]) -> None:
    """Upsert registered providers and their services."""
    provider_count = 0
    service_count = 0

    with db.transaction() as cursor:
        cursor.execute("SELECT pg_advisory_xact_lock(%s)", (_REGISTRY_SYNC_LOCK_KEY,))

        for info in list(providers):
            cursor.execute(
                "SELECT id FROM subtitle_providers "
                "WHERE name = %s ORDER BY created_at LIMIT 1",
                (info.name,),
            )
            row = cursor.fetchone()

            if row is None:
                provider_id = str(uuid.uuid4())
                cursor.execute(
                    "INSERT INTO subtitle_providers "
                    "(id, name, kind, base_url) VALUES (%s, %s, %s, %s)",
                    (provider_id, info.name, info.kind, info.base_url),
                )
                logger.info("Registered provider '%s' (kind=%s)", info.name, info.kind)
            else:
                provider_id = row["id"]
                cursor.execute(
                    "UPDATE subtitle_providers "
                    "SET kind = %s, base_url = %s, is_active = TRUE, "
                    "    last_synced_at = NOW(), updated_at = NOW() "
                    "WHERE id = %s",
                    (info.kind, info.base_url, provider_id),
                )
            provider_count += 1

            for service_info in info.services:
                cursor.execute(
                    "SELECT id FROM subtitle_provider_services "
                    "WHERE provider_id = %s AND service_key = %s "
                    "ORDER BY created_at LIMIT 1",
                    (provider_id, service_info.service_key),
                )
                service_row = cursor.fetchone()

                if service_row is None:
                    cursor.execute(
                        "INSERT INTO subtitle_provider_services "
                        "(id, provider_id, service_key, name, options) "
                        "VALUES (%s, %s, %s, %s, %s::jsonb)",
                        (
                            str(uuid.uuid4()),
                            provider_id,
                            service_info.service_key,
                            service_info.name,
                            json.dumps(service_info.options),
                        ),
                    )
                    logger.info(
                        "Registered service '%s' on provider '%s'",
                        service_info.service_key,
                        info.name,
                    )
                else:
                    cursor.execute(
                        "UPDATE subtitle_provider_services "
                        "SET name = %s, options = %s::jsonb, is_active = TRUE, "
                        "    updated_at = NOW() "
                        "WHERE id = %s",
                        (
                            service_info.name,
                            json.dumps(service_info.options),
                            service_row["id"],
                        ),
                    )
                service_count += 1

    logger.info(
        "Registry sync done: %d provider(s), %d service(s)",
        provider_count,
        service_count,
    )
