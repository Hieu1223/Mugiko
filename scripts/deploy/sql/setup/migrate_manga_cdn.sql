BEGIN;

-- Migrate manga CDN host from rcdn.kyut.dev to cdn.rawkuma.com.
--
-- Applies to all stored manga URLs:
--   * manga_providers.base_url  (provider base URL used to fetch manga data)
--   * manga_history.cover_url   (cover URL cached in user reading history)
--
-- Live manga data (covers, chapter pages) is served directly by the provider,
-- so updating the provider base_url is sufficient for future fetches.
UPDATE manga_providers
SET base_url = REPLACE(base_url, 'rcdn.kyut.dev', 'cdn.rawkuma.com'),
    updated_at = NOW()
WHERE base_url LIKE '%rcdn.kyut.dev%';

UPDATE manga_history
SET cover_url = REPLACE(cover_url, 'rcdn.kyut.dev', 'cdn.rawkuma.com')
WHERE cover_url LIKE '%rcdn.kyut.dev%';

COMMIT;
