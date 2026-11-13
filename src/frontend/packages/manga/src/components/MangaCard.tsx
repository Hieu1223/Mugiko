import { Link } from '@mugiko/common'
import type { MangaSummary } from '../libs/types'

export function MangaCard({ manga }: { manga: MangaSummary }) {
  const tags = (manga.tags || []).slice(0, 4)

  return (
    <article className="manga-card">
      <div className="manga-card__cover">
        {manga.cover_url ? (
          <img
            className="manga-card__cover-img"
            src={manga.cover_url}
            alt={manga.title}
            loading="lazy"
            decoding="async"
          />
        ) : (
          <span className="manga-card__cover--empty">no cover</span>
        )}
      </div>
      <div className="manga-card__body">
        <Link to={`/manga/${manga.slug}`} className="manga-card__title">
          {manga.title}
        </Link>
        <p className="manga-card__meta">
          {manga.score > 0 ? `score ${manga.score.toFixed(1)}` : ''}
          {manga.views > 0 ? ` · views ${manga.views}` : ''}
        </p>
        <div className="manga-tags">
          {tags.map((tag) => (
            <span key={tag.slug} className="manga-tag">
              {tag.name}
            </span>
          ))}
        </div>
      </div>
    </article>
  )
}
