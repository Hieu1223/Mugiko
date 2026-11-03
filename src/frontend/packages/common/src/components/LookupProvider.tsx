import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from 'react'
import { createPortal } from 'react-dom'
import { useToast } from '../libs/ToastContext'
import { errorDetail, isApiError } from '../libs/api'
import { addDeckWord, createDeck, listAllDecks } from '../libs/decks'
import { lookupWord, prefixWithFallback } from '../libs/lookup'
import type { Deck, DictionaryEntry } from '../libs/types'
import { cx } from '../utils/format'
import { Button } from './ui/Button'
import { Input } from './ui/Field'
import { InlineNotice } from './ui/States'

export interface LookupTarget {
  text: string
  rect: { left: number; top: number; right: number; bottom: number; width: number; height: number }
}

interface LookupContextValue {
  openLookup: (target: LookupTarget) => void
  /** Open the definition stage directly for an already-known word. */
  openWord: (word: string, rect: LookupTarget['rect']) => void
  closeLookup: () => void
}

const LookupContext = createContext<LookupContextValue | null>(null)

type Stage = 'candidates' | 'entry'
type DeckMode = 'idle' | 'picking' | 'creating'

const CANDIDATE_WIDTH = 320
const ENTRY_WIDTH = 352
const GAP = 10

function clamp(value: number, min: number, max: number): number {
  return Math.min(Math.max(value, min), max)
}

function popoverPosition(
  anchor: LookupTarget['rect'],
  width: number,
  estimatedHeight: number,
) {
  const margin = 12
  const viewportWidth = window.innerWidth
  const viewportHeight = window.innerHeight
  let left = anchor.left
  if (left + width > viewportWidth - margin) left = anchor.right - width
  left = clamp(left, margin, Math.max(margin, viewportWidth - width - margin))

  const placeAbove = anchor.top > viewportHeight * 0.55
  const top = placeAbove
    ? Math.max(margin, anchor.top - estimatedHeight - GAP)
    : Math.min(
        Math.max(margin, anchor.bottom + GAP),
        Math.max(margin, viewportHeight - Math.min(estimatedHeight, viewportHeight * 0.7) - margin),
      )

  return { left, top, width }
}

function entryPosition(
  anchor: LookupTarget['rect'],
  candidateLeft: number,
  width: number,
  estimatedHeight: number,
) {
  const margin = 12
  const viewportWidth = window.innerWidth
  let left = candidateLeft + CANDIDATE_WIDTH + GAP
  if (left + width > viewportWidth - margin) left = candidateLeft - width - GAP
  if (left < margin) {
    left = clamp(anchor.right - width, margin, Math.max(margin, viewportWidth - width - margin))
  }
  const placeAbove = anchor.top > window.innerHeight * 0.55
  const top = placeAbove
    ? Math.max(margin, anchor.top - estimatedHeight - GAP)
    : Math.max(margin, anchor.bottom + GAP)
  return { left, top, width }
}

export function LookupProvider({ children }: { children: ReactNode }) {
  const [target, setTarget] = useState<LookupTarget | null>(null)
  const [stage, setStage] = useState<Stage>('candidates')
  const [query, setQuery] = useState('')
  const [candidates, setCandidates] = useState<string[]>([])
  const [usedPrefix, setUsedPrefix] = useState('')
  const [loadingCandidates, setLoadingCandidates] = useState(false)
  const [candidateError, setCandidateError] = useState<string | null>(null)
  const [selectedWord, setSelectedWord] = useState('')
  const [entry, setEntry] = useState<DictionaryEntry | null>(null)
  const [loadingEntry, setLoadingEntry] = useState(false)
  const [entryError, setEntryError] = useState<string | null>(null)
  const [readingIndex, setReadingIndex] = useState(0)
  const [deckMode, setDeckMode] = useState<DeckMode>('idle')
  const [decks, setDecks] = useState<Deck[]>([])
  const [loadingDecks, setLoadingDecks] = useState(false)
  const [deckError, setDeckError] = useState<string | null>(null)
  const [newDeckName, setNewDeckName] = useState('')
  const [saving, setSaving] = useState(false)
  const [activeIndex, setActiveIndex] = useState(0)

  const { toast } = useToast()

  const openLookup = useCallback((next: LookupTarget) => {
    const text = next.text.trim()
    if (!text) return
    setTarget(next)
    setStage('candidates')
    setQuery(text)
    setCandidates([])
    setUsedPrefix('')
    setCandidateError(null)
    setSelectedWord('')
    setEntry(null)
    setEntryError(null)
    setReadingIndex(0)
    setDeckMode('idle')
    setDeckError(null)
    setNewDeckName('')
    setActiveIndex(0)
  }, [])

  const closeLookup = useCallback(() => {
    setTarget(null)
    setStage('candidates')
    setDeckMode('idle')
  }, [])
  const back = useCallback(() => {
    if (deckMode !== 'idle') {
      setDeckMode('idle')
      return
    }
    setStage('candidates')
    setEntry(null)
    setEntryError(null)
  }, [deckMode])

  // Load candidates for the current query.
  useEffect(() => {
    if (!target || stage !== 'candidates') return
    const cleaned = query.trim()
    if (!cleaned) {
      setCandidates([])
      return
    }
    const controller = new AbortController()
    setLoadingCandidates(true)
    setCandidateError(null)
    prefixWithFallback(cleaned, controller.signal)
      .then((result) => {
        if (controller.signal.aborted) return
        setCandidates(result.results)
        setUsedPrefix(result.usedPrefix)
        setActiveIndex(0)
        setLoadingCandidates(false)
      })
      .catch((err) => {
        if (controller.signal.aborted) return
        setCandidateError(errorDetail(err, 'Lookup failed.'))
        setLoadingCandidates(false)
      })
    return () => controller.abort()
  }, [target, stage, query])

  const openEntry = useCallback((word: string) => {
    setSelectedWord(word)
    setStage('entry')
    setEntry(null)
    setEntryError(null)
    setReadingIndex(0)
    setDeckMode('idle')
    setDeckError(null)
  }, [])

  const openWord = useCallback(
    (word: string, rect: LookupTarget['rect']) => {
      const text = word.trim()
      if (!text) return
      setTarget({ text, rect })
      setQuery(text)
      setCandidates([])
      setUsedPrefix('')
      setCandidateError(null)
      openEntry(text)
    },
    [openEntry],
  )

  useEffect(() => {
    if (!target || stage !== 'entry' || !selectedWord) return
    const controller = new AbortController()
    setLoadingEntry(true)
    setEntryError(null)
    lookupWord(selectedWord, controller.signal)
      .then((value) => {
        if (controller.signal.aborted) return
        setEntry(value)
        setReadingIndex(0)
        setLoadingEntry(false)
      })
      .catch((err) => {
        if (controller.signal.aborted) return
        setEntryError(errorDetail(err, 'Definition not found.'))
        setLoadingEntry(false)
      })
    return () => controller.abort()
  }, [target, stage, selectedWord])

  // Close on outside interaction / viewport changes.
  useEffect(() => {
    if (!target) return
    const onPointerDown = (event: PointerEvent) => {
      const node = event.target as HTMLElement | null
      if (node?.closest('[data-lookup-layer]') || node?.closest('[data-word-token]')) return
      closeLookup()
    }
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key !== 'Escape') return
      if (deckMode !== 'idle') {
        setDeckMode('idle')
      } else if (stage === 'entry') {
        back()
      } else {
        closeLookup()
      }
    }
    const onViewport = () => closeLookup()
    const onScroll = (event: Event) => {
      const target = event.target as Node | null
      // Ignore scrolling inside the transcript/reader and inside the popovers.
      if (target instanceof Element) {
        if (target.closest('[data-lookup-layer]')) return
        if (target !== document.documentElement && target !== document.body) return
      }
      closeLookup()
    }

    document.addEventListener('pointerdown', onPointerDown, true)
    document.addEventListener('keydown', onKeyDown, true)
    window.addEventListener('resize', onViewport)
    window.addEventListener('scroll', onScroll, true)
    return () => {
      document.removeEventListener('pointerdown', onPointerDown, true)
      document.removeEventListener('keydown', onKeyDown, true)
      window.removeEventListener('resize', onViewport)
      window.removeEventListener('scroll', onScroll, true)
    }
  }, [target, stage, deckMode, closeLookup, back])

  const reading = entry?.readings?.[readingIndex]
  const meaning = reading?.meaning || ''
  const wordForDeck = entry?.word || selectedWord

  const loadDecks = useCallback(async () => {
    setLoadingDecks(true)
    setDeckError(null)
    try {
      const list = await listAllDecks()
      setDecks(list)
    } catch (err) {
      setDeckError(errorDetail(err, 'Could not load decks.'))
    } finally {
      setLoadingDecks(false)
    }
  }, [])

  const startDeckPick = useCallback(() => {
    setDeckMode('picking')
    void loadDecks()
  }, [loadDecks])

  const saveToDeck = useCallback(
    async (deckId: string) => {
      if (!wordForDeck || !meaning) return
      setSaving(true)
      setDeckError(null)
      try {
        await addDeckWord(deckId, wordForDeck, meaning)
        toast(`Added “${wordForDeck}” to deck.`, 'success')
        setDeckMode('idle')
        setStage('candidates')
      } catch (err) {
        if (isApiError(err) && err.status === 403) {
          setDeckError('This session cannot write to decks.')
        } else if (isApiError(err) && err.status === 404) {
          setDeckError('That deck no longer exists.')
        } else {
          setDeckError(errorDetail(err, 'Could not add the word.'))
        }
      } finally {
        setSaving(false)
      }
    },
    [wordForDeck, meaning, toast],
  )

  const createAndSave = useCallback(async () => {
    const name = newDeckName.trim()
    if (!name) {
      setDeckError('Give the deck a name first.')
      return
    }
    setSaving(true)
    setDeckError(null)
    try {
      const deck = await createDeck(name)
      setDecks((current) => [...current, deck])
      await addDeckWord(deck.id, wordForDeck, meaning)
      toast(`Created “${name}” and added “${wordForDeck}”.`, 'success')
      setNewDeckName('')
      setDeckMode('idle')
      setStage('candidates')
    } catch (err) {
      if (isApiError(err) && err.status === 403) {
        setDeckError('This session cannot create decks.')
      } else {
        setDeckError(errorDetail(err, 'Could not create the deck.'))
      }
    } finally {
      setSaving(false)
    }
  }, [newDeckName, wordForDeck, meaning, toast])

  const value = useMemo(() => ({ openLookup, openWord, closeLookup }), [openLookup, openWord, closeLookup])

  const candidatePosition = target ? popoverPosition(target.rect, CANDIDATE_WIDTH, 380) : null
  const entryPos =
    target && candidatePosition
      ? entryPosition(target.rect, candidatePosition.left, ENTRY_WIDTH, 440)
      : null

  return (
    <LookupContext.Provider value={value}>
      {children}
      {target && candidatePosition && (stage === 'candidates' || candidates.length > 0) &&
        createPortal(
          <div
            className={cx(
              'lookup-popover',
              'lookup-popover--candidates',
              stage === 'entry' && 'is-behind',
            )}
            style={{ left: candidatePosition.left, top: candidatePosition.top, width: candidatePosition.width }}
            data-lookup-layer
            role="dialog"
            aria-label="Lookup candidates"
          >
            <header className="lookup-popover__head">
              <p className="lookup-popover__query">{target.text}</p>
              <button type="button" className="icon-btn" onClick={closeLookup} aria-label="Close lookup">
                ×
              </button>
            </header>

            <div className="lookup-popover__search">
              <input
                className="input input--compact"
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                onKeyDown={(event) => {
                  if (event.key === 'ArrowDown') {
                    event.preventDefault()
                    setActiveIndex((index) => Math.min(index + 1, Math.max(candidates.length - 1, 0)))
                  } else if (event.key === 'ArrowUp') {
                    event.preventDefault()
                    setActiveIndex((index) => Math.max(index - 1, 0))
                  } else if (event.key === 'Enter') {
                    event.preventDefault()
                    const candidate = candidates[activeIndex]
                    if (candidate) openEntry(candidate)
                    else if (query.trim()) openEntry(query.trim())
                  }
                }}
                placeholder="Search"
                aria-label="Search prefix"
                autoFocus
              />
              <span className="lookup-popover__count">{candidates.length}</span>
            </div>

            <div className="lookup-popover__body">
              {loadingCandidates && <p className="lookup-hint">Searching…</p>}
              {candidateError && <p className="lookup-hint lookup-hint--error">{candidateError}</p>}
              {!loadingCandidates && !candidateError && candidates.length === 0 && (
                <p className="lookup-hint">No matches.</p>
              )}
              {!loadingCandidates && candidates.length > 0 && (
                <ul className="lookup-list" role="listbox" aria-label="Matching words">
                  {candidates.map((candidate, index) => (
                    <li key={candidate}>
                      <button
                        type="button"
                        role="option"
                        aria-selected={index === activeIndex}
                        className={cx('lookup-list__item', index === activeIndex && 'is-active')}
                        onMouseEnter={() => setActiveIndex(index)}
                        onClick={() => openEntry(candidate)}
                      >
                        <span className="lookup-list__word">{candidate}</span>
                        <span className="lookup-list__arrow" aria-hidden="true">
                          →
                        </span>
                      </button>
                    </li>
                  ))}
                </ul>
              )}
              {!loadingCandidates && usedPrefix && usedPrefix !== query.trim() && candidates.length > 0 && (
                <p className="lookup-note">Matches for “{usedPrefix}”.</p>
              )}
            </div>

            <footer className="lookup-popover__foot">
              <Button size="sm" onClick={() => openEntry(query.trim())} disabled={!query.trim()}>
                Look up
              </Button>
            </footer>
          </div>,
          document.body,
        )}

      {target && entryPos && stage === 'entry' &&
        createPortal(
          <div
            className="lookup-popover lookup-popover--entry"
            style={{ left: entryPos.left, top: entryPos.top, width: entryPos.width }}
            data-lookup-layer
            role="dialog"
            aria-label="Word definition"
          >
            <header className="lookup-popover__head">
              <p className="lookup-popover__query">{selectedWord}</p>
              <div className="lookup-popover__head-actions">
                <button type="button" className="icon-btn" onClick={back} aria-label="Back to candidates">
                  ←
                </button>
                <button type="button" className="icon-btn" onClick={closeLookup} aria-label="Close lookup">
                  ×
                </button>
              </div>
            </header>

            <div className="lookup-popover__body">
              {loadingEntry && <p className="lookup-hint">Loading…</p>}
              {entryError && <p className="lookup-hint lookup-hint--error">{entryError}</p>}

              {entry && !loadingEntry && (
                <>
                  <div className="entry-word">
                    <span className="entry-word__kanji">{entry.word}</span>
                  </div>

                  {entry.readings?.length ? (
                    <ul className="reading-list">
                      {entry.readings.map((item, index) => (
                        <li key={`${item.kana}-${index}`}>
                          <button
                            type="button"
                            className={cx('reading-list__item', index === readingIndex && 'is-active')}
                            onClick={() => setReadingIndex(index)}
                            aria-pressed={index === readingIndex}
                          >
                            <span className="reading-list__kana">{item.kana || '—'}</span>
                            <span className="reading-list__meaning">{item.meaning || '—'}</span>
                          </button>
                        </li>
                      ))}
                    </ul>
                  ) : (
                    <p className="lookup-hint">No readings returned.</p>
                  )}

                  {deckMode === 'idle' && (
                    <div className="lookup-popover__actions">
                      <Button
                        variant="primary"
                        size="sm"
                        block
                        onClick={startDeckPick}
                        disabled={!meaning}
                      >
                        Add to deck
                      </Button>
                    </div>
                  )}

                  {deckMode !== 'idle' && (
                    <div className="deck-picker">
                      <div className="deck-picker__head">
                        <strong>Add to deck</strong>
                        <button type="button" className="text-btn" onClick={() => setDeckMode('idle')}>
                          Cancel
                        </button>
                      </div>
                      <p className="deck-picker__preview">
                        <strong>{wordForDeck}</strong>
                        <span>{meaning}</span>
                      </p>

                      {deckMode === 'picking' && (
                        <>
                          {loadingDecks && <p className="lookup-hint">Loading decks…</p>}
                          {!loadingDecks && decks.length > 0 && (
                            <ul className="deck-picker__list">
                              {decks.map((deck) => (
                                <li key={deck.id}>
                                  <button
                                    type="button"
                                    className="deck-picker__deck"
                                    disabled={saving}
                                    onClick={() => void saveToDeck(deck.id)}
                                  >
                                    <span>{deck.name}</span>
                                    <span aria-hidden="true">＋</span>
                                  </button>
                                </li>
                              ))}
                            </ul>
                          )}
                          {!loadingDecks && decks.length === 0 && !deckError && (
                            <p className="lookup-hint">No decks yet.</p>
                          )}
                          <Button size="sm" block onClick={() => setDeckMode('creating')}>
                            New deck
                          </Button>
                        </>
                      )}

                      {deckMode === 'creating' && (
                        <div className="deck-picker__create">
                          <Input
                            label="Deck name"
                            value={newDeckName}
                            onChange={(event) => setNewDeckName(event.target.value)}
                            placeholder="冬の言葉"
                            maxLength={100}
                            autoFocus
                            onKeyDown={(event) => {
                              if (event.key === 'Enter') void createAndSave()
                            }}
                          />
                          <Button
                            size="sm"
                            variant="primary"
                            block
                            loading={saving}
                            onClick={() => void createAndSave()}
                          >
                            Create and add
                          </Button>
                        </div>
                      )}

                      {deckError && <InlineNotice tone="error">{deckError}</InlineNotice>}
                    </div>
                  )}
                </>
              )}
            </div>
          </div>,
          document.body,
        )}
    </LookupContext.Provider>
  )
}

export function useLookup(): LookupContextValue {
  const context = useContext(LookupContext)
  if (!context) throw new Error('useLookup must be used inside LookupProvider')
  return context
}

export type WordTokenMode = 'normal' | 'hiragana' | 'both' | 'reverse'

export function WordToken({
  token,
  displayMode = 'both',
}: {
  token: { text: string; lookup: string; reading?: string }
  displayMode?: WordTokenMode
}) {
  const { openLookup } = useLookup()
  const ref = useRef<HTMLButtonElement>(null)
  const canAnnotate = Boolean(token.reading && token.reading !== token.text)
  let label: ReactNode = token.text
  if (displayMode === 'hiragana' && canAnnotate) {
    label = token.reading
  } else if (displayMode === 'both' && canAnnotate) {
    label = (
      <span className="furi">
        <span className="top">{token.reading}</span>
        <span className="main">{token.text}</span>
      </span>
    )
  } else if (displayMode === 'reverse' && canAnnotate) {
    label = (
      <span className="furi">
        <span className="top reverse">{token.text}</span>
        <span className="main">{token.reading}</span>
      </span>
    )
  }

  return (
    <button
      ref={ref}
      type="button"
      data-word-token
      className="word-token"
      title={`Look up ${token.lookup}`}
      onClick={(event) => {
        event.stopPropagation()
        const rect = ref.current?.getBoundingClientRect()
        if (!rect) return
        openLookup({
          text: token.lookup,
          rect: {
            left: rect.left,
            top: rect.top,
            right: rect.right,
            bottom: rect.bottom,
            width: rect.width,
            height: rect.height,
          },
        })
      }}
    >
      {label}
    </button>
  )
}
