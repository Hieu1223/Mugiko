import { useState } from 'react'
import { Link } from '../libs/router'
import { useSession } from '../libs/SessionContext'
import { useToast } from '../libs/ToastContext'
import { createDeck, deleteDeck, listDecks } from '../libs/decks'
import { errorDetail, isApiError } from '../libs/api'
import { useAsync, useDocumentTitle } from '../libs/hooks'
import { PageTitle } from '../components/ui/Layout'
import { Button } from '../components/ui/Button'
import { Input } from '../components/ui/Field'
import { EmptyState, ErrorState, LoadingState } from '../components/ui/States'
import { Pagination } from '../components/ui/Pagination'
import { formatDate } from '../utils/format'

export function DecksPage() {
  useDocumentTitle('Decks')
  const [page, setPage] = useState(1)
  const [name, setName] = useState('')
  const [busy, setBusy] = useState(false)
  const [formError, setFormError] = useState<string | null>(null)
  const [deleting, setDeleting] = useState<string | null>(null)
  const { revision } = useSession()
  const { toast } = useToast()

  const state = useAsync((signal) => listDecks(page, 12), [page, revision])

  const submit = async () => {
    const trimmed = name.trim()
    if (!trimmed) {
      setFormError('Enter a deck name.')
      return
    }
    setBusy(true)
    setFormError(null)
    try {
      await createDeck(trimmed)
      toast(`Deck “${trimmed}” created.`, 'success')
      setName('')
      state.reload()
    } catch (err) {
      if (isApiError(err) && err.status === 403) {
        setFormError('This session cannot create decks.')
      } else {
        setFormError(errorDetail(err, 'Could not create the deck.'))
      }
    } finally {
      setBusy(false)
    }
  }

  const remove = async (id: string, deckName: string) => {
    if (!window.confirm(`Delete the deck “${deckName}”?`)) return
    setDeleting(id)
    try {
      await deleteDeck(id)
      toast('Deck deleted.', 'success')
      state.reload()
    } catch (err) {
      toast(errorDetail(err, 'Could not delete the deck.'), 'error')
    } finally {
      setDeleting(null)
    }
  }

  return (
    <div className="page">
      <PageTitle title="Decks" />

      <form
        className="form-row"
        onSubmit={(event) => {
          event.preventDefault()
          void submit()
        }}
      >
        <Input
          label="New deck"
          value={name}
          onChange={(event) => setName(event.target.value)}
          placeholder="Deck name"
          maxLength={100}
        />
        <Button type="submit" variant="primary" loading={busy}>
          Create
        </Button>
      </form>
      {formError && <p className="field__error">{formError}</p>}

      {state.loading && <LoadingState label="Loading decks" />}
      {state.error && (
        <ErrorState message={state.error} forbidden={state.forbidden} onRetry={state.reload} />
      )}

      {!state.loading && !state.error && state.data && (
        <>
          {state.data.decks.length === 0 ? (
            <EmptyState title="No decks." />
          ) : (
            <table>
              <thead>
                <tr>
                  <th>Name</th>
                  <th>Updated</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {state.data.decks.map((deck) => (
                  <tr key={deck.id}>
                    <td>
                      <Link to={`/decks/${deck.id}`}>{deck.name}</Link>
                    </td>
                    <td>{formatDate(deck.updated_at || deck.created_at)}</td>
                    <td>
                      <Link to={`/decks/${deck.id}`}>Open</Link>{' '}
                      <Button
                        size="sm"
                        variant="danger"
                        loading={deleting === deck.id}
                        onClick={() => void remove(deck.id, deck.name)}
                      >
                        Delete
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
    </div>
  )
}
