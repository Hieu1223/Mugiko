import { useMemo, useState } from 'react'
import {
  Button,
  EmptyState,
  ErrorState,
  FieldShell,
  Input,
  Link,
  LoadingState,
  PageTitle,
  Pagination,
  Select,
  useAsync,
  useDebounced,
  useDocumentTitle,
} from '@mugiko/common'
import { listManga, listFilters } from '../libs/manga'
import type { MangaTag } from '../libs/types'
import { MangaCard } from '../components/MangaCard'

const PAGE_SIZE = 24

type Sort = 'updated_at' | 'title' | 'score' | 'views' | 'release_year'

const SORTS: Array<{ id: Sort; label: string }> = [
  { id: 'updated_at', label: 'Last updated' },
  { id: 'title', label: 'Title' },
  { id: 'score', label: 'Score' },
  { id: 'views', label: 'Views' },
  { id: 'release_year', label: 'Release year' },
]

export function MangaHomePage() {
  useDocumentTitle('Manga library')
  const [query, setQuery] = useState('')
  const [genre, setGenre] = useState('')
  const [author, setAuthor] = useState('')
  const [status, setStatus] = useState('')
  const [type, setType] = useState('')
  const [sort, setSort] = useState<Sort>('updated_at')
  const [order, setOrder] = useState<'asc' | 'desc'>('desc')
  const [page, setPage] = useState(1)

  const debouncedQuery = useDebounced(query.trim(), 300)

  const filters = useAsync((signal) => listFilters(signal), [])
  const grouped: Record<string, MangaTag[]> = filters.data?.items || {}
  const genreOptions = grouped['genre'] || []
  const statusOptions = grouped['status'] || []
  const typeOptions = grouped['type'] || []

  const manga = useAsync(
    (signal) =>
      listManga(
        {
          q: debouncedQuery || undefined,
          genre: genre || undefined,
          author: author || undefined,
          status: status || undefined,
          type: type || undefined,
          sort,
          order,
          page,
          page_size: PAGE_SIZE,
        },
        signal,
      ),
    [debouncedQuery, genre, author, status, type, sort, order, page],
  )

  if (manga.loading) {
    return (
      <div className="page">
        <PageTitle title="Manga library" />
        <LoadingState label="Loading manga" />
      </div>
    )
  }
  if (manga.error) {
    return (
      <div className="page">
        <PageTitle title="Manga library" />
        <ErrorState message={manga.error} onRetry={manga.reload} forbidden={manga.forbidden} />
      </div>
    )
  }

  const items = manga.data?.items || []
  const totalPages = Math.max(manga.data?.total_pages || 1, 1)
  const loaded = manga.data !== null

  return (
    <div className="page">
      <PageTitle title="Manga library" />

      <form className="form-row" onSubmit={(event) => event.preventDefault()}>
        <FieldShell label="Search">
          <Input
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Title, author, tag…"
          />
        </FieldShell>
        <FieldShell label="Genre">
          <Select value={genre} onChange={(event) => setGenre(event.target.value)}>
            <option value="">Any</option>
            {genreOptions.map((tag) => (
              <option key={tag.slug} value={tag.slug}>
                {tag.name}
              </option>
            ))}
          </Select>
        </FieldShell>
        <FieldShell label="Author">
          <Input
            value={author}
            onChange={(event) => setAuthor(event.target.value)}
            placeholder="Author name"
          />
        </FieldShell>
        <FieldShell label="Status">
          <Select value={status} onChange={(event) => setStatus(event.target.value)}>
            <option value="">Any</option>
            {statusOptions.map((tag) => (
              <option key={tag.slug} value={tag.slug}>
                {tag.name}
              </option>
            ))}
          </Select>
        </FieldShell>
        <FieldShell label="Type">
          <Select value={type} onChange={(event) => setType(event.target.value)}>
            <option value="">Any</option>
            {typeOptions.map((tag) => (
              <option key={tag.slug} value={tag.slug}>
                {tag.name}
              </option>
            ))}
          </Select>
        </FieldShell>
        <FieldShell label="Sort">
          <Select value={sort} onChange={(event) => setSort(event.target.value as Sort)}>
            {SORTS.map((option) => (
              <option key={option.id} value={option.id}>
                {option.label}
              </option>
            ))}
          </Select>
        </FieldShell>
        <FieldShell label="Order">
          <Select value={order} onChange={(event) => setOrder(event.target.value as 'asc' | 'desc')}>
            <option value="asc">Ascending</option>
            <option value="desc">Descending</option>
          </Select>
        </FieldShell>
        <Button type="submit" variant="primary" onClick={() => setPage(1)}>
          Go
        </Button>
      </form>

      {loaded && items.length === 0 && !manga.loading && !manga.error && (
        <EmptyState title="No manga found" action={<Button onClick={() => setPage(1)}>Reset filters</Button>} />
      )}

      {items.length > 0 && (
        <div className="manga-grid">
          {items.map((manga) => (
            <MangaCard key={manga.id} manga={manga} />
          ))}
        </div>
      )}

      {items.length > 0 && (
        <Pagination
          page={page}
          totalPages={totalPages}
          total={manga.data?.total}
          onChange={setPage}
        />
      )}
    </div>
  )
}
