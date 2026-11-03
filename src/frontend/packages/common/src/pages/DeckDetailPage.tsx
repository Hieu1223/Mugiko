import { useEffect, useState } from 'react'
import { Link, useParams } from '../libs/router'
import {
  addDeckWord,
  deleteDeckWord,
  getDeck,
  listDeckWords,
  renameDeck,
  updateDeckWord,
} from '../libs/decks'
import { useAsync, useDocumentTitle } from '../libs/hooks'
import { errorDetail, isApiError } from '../libs/api'
import { useSession } from '../libs/SessionContext'
import { useToast } from '../libs/ToastContext'
import { PageTitle } from '../components/ui/Layout'
import { Button } from '../components/ui/Button'
import { Input } from '../components/ui/Field'
import { Dialog } from '../components/ui/Dialog'
import { EmptyState, ErrorState, LoadingState } from '../components/ui/States'
import { Pagination } from '../components/ui/Pagination'
import { formatDate } from '../utils/format'
import type { DeckWord } from '../libs/types'

export function DeckDetailPage() {
  const { deckId = '' } = useParams()
  const [page, setPage] = useState(1)
  const [word, setWord] = useState('')
  const [meaning, setMeaning] = useState('')
  const [adding, setAdding] = useState(false)
  const [addError, setAddError] = useState<string | null>(null)
  const [editing, setEditing] = useState<DeckWord | null>(null)
  const [editWord, setEditWord] = useState('')
  const [editMeaning, setEditMeaning] = useState('')
  const [editBusy, setEditBusy] = useState(false)
  const [editError, setEditError] = useState<string | null>(null)
  const [deckName, setDeckName] = useState('')
  const [renameBusy, setRenameBusy] = useState(false)
  const [renameError, setRenameError] = useState<string | null>(null)
  const { revision } = useSession()
  const { toast } = useToast()

  useDocumentTitle('Deck')

  const state = useAsync((signal) => listDeckWords(deckId, page, 20), [deckId, page, revision], {
    enabled: Boolean(deckId),
  })

  const deck = useAsync((signal) => getDeck(deckId), [deckId, revision], {
    enabled: Boolean(deckId),
  })

  useEffect(() => {
    if (page > 1 && state.data && state.data.total_pages > 0 && page > state.data.total_pages) {
      setPage(state.data.total_pages)
    }
  }, [state.data, page])

  useEffect(() => {
    if (deck.data) setDeckName(deck.data.name)
  }, [deck.data])

  const add = async () => {
    if (!word.trim() || !meaning.trim()) {
      setAddError('Word and meaning are required.')
      return
    }
    setAdding(true)
    setAddError(null)
    try {
      await addDeckWord(deckId, word.trim(), meaning.trim())
      toast('Word added.', 'success')
      setWord('')
      setMeaning('')
      state.reload()
    } catch (err) {
      setAddError(
        isApiError(err) && err.status === 403
          ? 'This session cannot write to decks.'
          : errorDetail(err, 'Could not add the word.'),
      )
    } finally {
      setAdding(false)
    }
  }

  const openEdit = (item: DeckWord) => {
    setEditing(item)
    setEditWord(item.word)
    setEditMeaning(item.meaning)
    setEditError(null)
  }

  const saveEdit = async () => {
    if (!editing) return
    setEditBusy(true)
    setEditError(null)
    try {
      await updateDeckWord(deckId, editing.id, { word: editWord.trim(), meaning: editMeaning.trim() })
      toast('Word updated.', 'success')
      setEditing(null)
      state.reload()
    } catch (err) {
      setEditError(errorDetail(err, 'Could not update the word.'))
    } finally {
      setEditBusy(false)
    }
  }

  const removeWord = async (item: DeckWord) => {
    if (!window.confirm(`Remove “${item.word}” from this deck?`)) return
    try {
      await deleteDeckWord(deckId, item.id)
      toast('Word removed.', 'success')
      state.reload()
    } catch (err) {
      toast(errorDetail(err, 'Could not remove the word.'), 'error')
    }
  }

  const rename = async () => {
    const trimmed = deckName.trim()
    if (!trimmed) {
      setRenameError('Enter a name.')
      return
    }
    setRenameBusy(true)
    setRenameError(null)
    try {
      await renameDeck(deckId, trimmed)
      toast('Deck renamed.', 'success')
      deck.reload()
      state.reload()
    } catch (err) {
      setRenameError(errorDetail(err, 'Could not rename the deck.'))
    } finally {
      setRenameBusy(false)
    }
  }

  return (
    <div className="page">
      <PageTitle
        title={deck.data?.name || 'Deck'}
        actions={<Link to="/decks">← All decks</Link>}
      />

      <form
        className="form-row"
        onSubmit={(event) => {
          event.preventDefault()
          void rename()
        }}
      >
        <Input
          label="Rename deck"
          value={deckName}
          onChange={(event) => setDeckName(event.target.value)}
          maxLength={100}
        />
        <Button type="submit" loading={renameBusy}>
          Rename
        </Button>
      </form>
      {renameError && <p className="field__error">{renameError}</p>}

      <h2>Add word</h2>
      <form
        className="form-row"
        onSubmit={(event) => {
          event.preventDefault()
          void add()
        }}
      >
        <Input
          label="Word"
          value={word}
          onChange={(event) => setWord(event.target.value)}
          placeholder="言葉"
          maxLength={255}
        />
        <Input
          label="Meaning"
          value={meaning}
          onChange={(event) => setMeaning(event.target.value)}
          placeholder="word"
        />
        <Button type="submit" variant="primary" loading={adding}>
          Add
        </Button>
      </form>
      {addError && <p className="field__error">{addError}</p>}

      <h2>Words</h2>
      {state.loading && <LoadingState label="Loading words" />}
      {state.error && (
        <ErrorState message={state.error} forbidden={state.forbidden} onRetry={state.reload} />
      )}

      {!state.loading && !state.error && state.data && (
        <>
          {state.data.words.length === 0 ? (
            <EmptyState title="This deck is empty." />
          ) : (
            <table>
              <thead>
                <tr>
                  <th>Word</th>
                  <th>Meaning</th>
                  <th>Added</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {state.data.words.map((item) => (
                  <tr key={item.id}>
                    <td>{item.word}</td>
                    <td>{item.meaning}</td>
                    <td>{formatDate(item.created_at, true)}</td>
                    <td>
                      <Button size="sm" onClick={() => openEdit(item)}>
                        Edit
                      </Button>{' '}
                      <Button size="sm" variant="danger" onClick={() => void removeWord(item)}>
                        Remove
                      </Button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}

          <Pagination
            page={state.data.page || page}
            totalPages={state.data.total_pages || 1}
            total={state.data.total}
            onChange={setPage}
          />
        </>
      )}

      <Dialog
        open={Boolean(editing)}
        onClose={() => setEditing(null)}
        title="Edit word"
        footer={
          <>
            <Button onClick={() => setEditing(null)} disabled={editBusy}>
              Cancel
            </Button>
            <Button variant="primary" onClick={() => void saveEdit()} loading={editBusy}>
              Save
            </Button>
          </>
        }
      >
        <div className="stack">
          <Input label="Word" value={editWord} onChange={(event) => setEditWord(event.target.value)} maxLength={255} />
          <Input label="Meaning" value={editMeaning} onChange={(event) => setEditMeaning(event.target.value)} />
          {editError && <p className="field__error">{editError}</p>}
        </div>
      </Dialog>
    </div>
  )
}
