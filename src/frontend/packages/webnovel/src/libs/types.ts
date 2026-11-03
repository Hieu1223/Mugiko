export type NovelSource = 'syosetsu'

export interface Novel {
  id: string
  source: NovelSource
  source_id?: string
  url: string
  title: string
  author?: string
  synopsis?: string
  added_by?: string
  created_at?: string
}

export interface Chapter {
  id: string
  novel_id: string
  idx: number
  title: string
  created_at?: string
}

export interface Paragraph {
  id: string
  chapter_id: string
  idx: number
  text: string
  words: unknown
}

export interface NovelWithChapters extends Novel {
  chapters: Chapter[]
}

export interface ChapterWithParagraphs extends Chapter {
  paragraphs: Paragraph[]
}

export interface PaginatedNovels {
  novels: Novel[]
  total: number
  page: number
  page_size: number
}

export interface PreviewResponse {
  url: string
  title: string
  author?: string
  synopsis?: string
  source: NovelSource
}

export interface AddNovelResponse {
  novel: Novel
  job_id?: string
}

export interface NovelSearchResponse {
  items: Novel[]
  total: number
}

export interface NovelReaderSettings {
  fontScale: number
  lineHeight: number
  widthPercent: number
  showFurigana: boolean
}
