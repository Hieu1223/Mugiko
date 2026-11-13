package service

import (
	"database/sql"
	"log"
	"time"

	userdto "mugiko/internal/modules/core/user/dto"
	"mugiko/internal/modules/media/manga/dto"

	"github.com/google/uuid"
)

// Fixed, deterministic identifiers so the seed is idempotent across restarts.
var (
	builtinNamespace = uuid.MustParse("c4a1f2e0-3d9b-4f1a-8c7e-6b5a4f3e2d10")

	builtinSystemAuthID = "builtin-manga-provider"
	builtinBaseURL      = "http://localhost:8090"
	builtinProviderName = "Mugiko Manga Server"
)

func systemUserID() uuid.UUID {
	return uuid.NewSHA1(builtinNamespace, []byte("mugiko-system-user"))
}

func builtinProviderID() uuid.UUID {
	return uuid.NewSHA1(builtinNamespace, []byte("mugiko-builtin-manga-provider"))
}

// EnsureBuiltinProvider idempotently creates the system user that owns the
// default built-in manga provider and the provider row itself. It is safe to
// call on every startup: existing rows are never duplicated, and the seeded
// values are reconciled so a drifted base_url or visibility is corrected.
func EnsureBuiltinProvider(db *sql.DB) error {
	now := time.Now().UTC()
	ownerID := systemUserID()

	// Make sure the system owner exists.
	if _, err := db.Exec(`
		INSERT INTO users (user_id, role, auth_type, auth_id, is_active, joined_at)
		VALUES ($1, $2, $3, $4, true, $5)
		ON CONFLICT (auth_type, auth_id) DO NOTHING
	`, ownerID.String(), userdto.RoleUser, userdto.AuthTypeSystem, builtinSystemAuthID, now.Format(time.RFC3339)); err != nil {
		return err
	}

	// Re-read the owner id in case the row already existed.
	var ownerIDStr string
	if err := db.QueryRow(`SELECT user_id FROM users WHERE auth_type = $1 AND auth_id = $2`, userdto.AuthTypeSystem, builtinSystemAuthID).Scan(&ownerIDStr); err != nil {
		return err
	}
	parsed, err := uuid.Parse(ownerIDStr)
	if err != nil {
		return err
	}
	ownerID = parsed

	providerID := builtinProviderID()
	if _, err := db.Exec(`
		INSERT INTO manga_providers (id, owner_id, name, base_url, visibility, is_builtin, created_at, updated_at)
		VALUES ($1, $2, $3, $4, $5, true, $6, $6)
		ON CONFLICT (id) DO UPDATE SET
			name = EXCLUDED.name,
			base_url = EXCLUDED.base_url,
			visibility = EXCLUDED.visibility,
			is_builtin = EXCLUDED.is_builtin,
			updated_at = EXCLUDED.updated_at
	`, providerID.String(), ownerID.String(), builtinProviderName, builtinBaseURL, dto.ProviderVisibilityPublic, now.Format(time.RFC3339)); err != nil {
		return err
	}

	log.Printf("Built-in manga provider seeded: id=%s owner_id=%s base_url=%s", providerID, ownerID, builtinBaseURL)
	return nil
}
