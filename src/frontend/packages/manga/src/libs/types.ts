export interface MangaProviderDTO {
  id: string
  owner_id: string
  name: string
  base_url: string
  visibility: string
  is_builtin: boolean
  created_at: string
  updated_at: string
}

export interface MangaTag {
  id: string
  name: string
  slug: string
  category: string
}

export interface ChapterSummary {
  id: string
  manga_id: string
  number: string
  title: string
  published_at: string
  page_count: number
}

export interface MangaSummary {
  id: string
  slug: string
  title: string
  alternative_titles: string[]
  cover_url: string
  thumbnail_url: string
  tags: MangaTag[]
  score: number
  views: number
  latest_chapters: ChapterSummary[]
  updated_at: string
}

export interface MangaDetail extends MangaSummary {
  description: string
  source_url: string
  created_at: string
}

export interface PageSummary {
  index: number
  url: string
  width: number
  height: number
}

export interface ChapterDetail extends ChapterSummary {
  pages: PageSummary[]
}

export interface MangaListResponse {
  items: MangaSummary[]
  page: number
  page_size: number
  total: number
  total_pages: number
}

export interface ChapterListResponse {
  items: ChapterSummary[]
  page: number
  page_size: number
  total: number
  total_pages: number
}

export interface TagListResponse {
  items: MangaTag[]
  page: number
  page_size: number
  total: number
  total_pages: number
}

export interface FilterListResponse {
  items: Record<string, MangaTag[]>
}
