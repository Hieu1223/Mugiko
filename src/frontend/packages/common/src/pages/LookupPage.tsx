import { useEffect, useState } from 'react'
import { useSearchParams } from '../libs/router'
import { lookupKanji, lookupWord, prefixWithFallback } from '../libs/lookup'
import { useAsync, useDebounced, useDocumentTitle } from '../libs/hooks'
import { PageTitle, Tabs } from '../components/ui/Layout'
import { Button } from '../components/ui/Button'
import { Input } from '../components/ui/Field'
import { EmptyState, ErrorState, LoadingState } from '../components/ui/States'
import { cx } from '../utils/format'
import type { DictionaryEntry, KanjiEntry } from '../libs/types'

type Mode = 'word' | 'prefix' | 'kanji'

const MODE_TABS: Array<{ id: Mode; label: string }> = [
  { id: 'word', label: 'Word' },
  { id: 'prefix', label: 'Prefix' },
  { id: 'kanji', label: 'Kanji' },
]

export function LookupPage() {
  useDocumentTitle('Lookup')
  const [params, setParams] = useSearchParams()
  const initialMode = (params.get('mode') as Mode) || 'word'
  const initialQuery = params.get('q') || ''
  const [mode, setMode] = useState<Mode>(MODE_TABS.some((tab) => tab.id === initialMode) ? initialMode : 'word')
  const [query, setQuery] = useState(initialQuery)
  const [submitted, setSubmitted] = useState(initialQuery)
  const debounced = useDebounced(query.trim(), 300)

  const isKanji = mode === 'kanji'
  const effectiveQuery = mode === 'prefix' ? debounced : submitted

  useEffect(() => {
    const next = new URLSearchParams()
    if (effectiveQuery) next.set('q', effectiveQuery)
    if (mode !== 'word') next.set('mode', mode)
    if (next.toString() !== params.toString()) setParams(next, { replace: true })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [effectiveQuery, mode])

  useEffect(() => {
    if (mode !== 'prefix') return
    setSubmitted(debounced)
    if (debounced) setQuery(debounced)
  }, [debounced, mode])

  const wordState = useAsync<DictionaryEntry>(
    (signal) => lookupWord(effectiveQuery, signal),
    [effectiveQuery],
    { enabled: mode === 'word' && Boolean(effectiveQuery) },
  )

  const prefixState = useAsync(
    (signal) => prefixWithFallback(effectiveQuery, signal),
    [effectiveQuery],
    { enabled: mode === 'prefix' && Boolean(effectiveQuery) },
  )

  const kanjiState = useAsync<KanjiEntry>(
    (signal) => lookupKanji(effectiveQuery, signal),
    [effectiveQuery],
    { enabled: isKanji && Boolean(effectiveQuery) },
  )

  const activeState = mode === 'word' ? wordState : mode === 'prefix' ? prefixState : kanjiState

  return (
    <div className="page">
      <PageTitle title="Lookup" />

      <Tabs
        tabs={MODE_TABS}
        value={mode}
        onChange={(next) => {
          setMode(next)
          if (next !== 'prefix') setSubmitted(query.trim())
        }}
        ariaLabel="Lookup mode"
      />

      <form
        className={cx('form-row', mode === 'kanji' && 'lookup-form--kanji')}
        onSubmit={(event) => {
          event.preventDefault()
          setSubmitted(query.trim())
        }}
      >
        <Input
          label={mode === 'kanji' ? 'Kanji' : mode === 'prefix' ? 'Prefix' : 'Word'}
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder={mode === 'kanji' ? '日' : mode === 'prefix' ? '食べ' : '食べる'}
          maxLength={mode === 'kanji' ? 1 : 100}
          autoFocus
        />
        <Button type="submit" variant="primary" disabled={!query.trim()}>
          {mode === 'prefix' ? 'Search' : 'Look up'}
        </Button>
      </form>

      {!effectiveQuery && <EmptyState title="No query." />}

      {effectiveQuery && activeState.loading && <LoadingState label="Looking up" />}

      {effectiveQuery && activeState.error && (
        <ErrorState
          message={activeState.error}
          forbidden={activeState.forbidden}
          onRetry={activeState.reload}
        />
      )}

      {mode === 'word' && wordState.data && !wordState.loading && (
        <WordResult entry={wordState.data} />
      )}

      {mode === 'prefix' && prefixState.data && !prefixState.loading && (
        <PrefixResults
          results={prefixState.data.results}
          usedPrefix={prefixState.data.usedPrefix}
          query={effectiveQuery}
          onSelect={(word) => {
            setMode('word')
            setQuery(word)
            setSubmitted(word)
          }}
        />
      )}

      {isKanji && kanjiState.data && !kanjiState.loading && <KanjiResult entry={kanjiState.data} />}
    </div>
  )
}

function WordResult({ entry }: { entry: DictionaryEntry }) {
  return (
    <div className="result-block">
      <h2>{entry.word}</h2>
      {entry.readings && entry.readings.length > 0 ? (
        <table>
          <thead>
            <tr>
              <th>Reading</th>
              <th>Meaning</th>
            </tr>
          </thead>
          <tbody>
            {entry.readings.map((reading, index) => (
              <tr key={`${reading.kana}-${index}`}>
                <td>{reading.kana || '—'}</td>
                <td>{reading.meaning || '—'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      ) : (
        <p className="status">No readings.</p>
      )}
    </div>
  )
}

function PrefixResults({
  results,
  usedPrefix,
  query,
  onSelect,
}: {
  results: string[]
  usedPrefix: string
  query: string
  onSelect: (word: string) => void
}) {
  if (results.length === 0) {
    return <EmptyState title={`No matches for “${query}”.`} />
  }

  return (
    <div className="result-block">
      <h2>
        {results.length} matches{usedPrefix !== query ? ` for “${usedPrefix}”` : ''}
      </h2>
      <ul className="lookup-list">
        {results.map((word) => (
          <li key={word}>
            <button type="button" className="lookup-list__item" onClick={() => onSelect(word)}>
              {word}
            </button>
          </li>
        ))}
      </ul>
    </div>
  )
}

function KanjiResult({ entry }: { entry: KanjiEntry }) {
  return (
    <div className="result-block">
      <h2>{entry.kanji}</h2>
      <table>
        <tbody>
          <tr>
            <th>Reading</th>
            <td>{entry.reading || '—'}</td>
          </tr>
          <tr>
            <th>Meanings</th>
            <td>{entry.meanings || '—'}</td>
          </tr>
          <tr>
            <th>Strokes</th>
            <td>{entry.strokes ?? '—'}</td>
          </tr>
          <tr>
            <th>Radical</th>
            <td>{entry.radical || '—'}</td>
          </tr>
          <tr>
            <th>Unicode</th>
            <td>{entry.unicode || '—'}</td>
          </tr>
          <tr>
            <th>Shape</th>
            <td>{entry.shape || '—'}</td>
          </tr>
        </tbody>
      </table>
    </div>
  )
}
