import { useState } from 'react'
import { useSession } from '../libs/SessionContext'
import { useToast } from '../libs/ToastContext'
import { maskToken, TokenFormatError } from '../libs/session'
import { Dialog } from './ui/Dialog'
import { Button } from './ui/Button'
import { Input } from './ui/Field'
import { InlineNotice } from './ui/States'
import { shortId } from '../utils/format'

export function SessionDialog({ open, onClose }: { open: boolean; onClose: () => void }) {
  const { session, applyToken, resetSession, status } = useSession()
  const { toast } = useToast()
  const [value, setValue] = useState('')
  const [reveal, setReveal] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  const close = () => {
    if (busy) return
    setValue('')
    setError(null)
    setReveal(false)
    onClose()
  }

  const submit = async () => {
    setError(null)
    setBusy(true)
    try {
      await applyToken(value)
      toast('Token applied.', 'success')
      setValue('')
      setReveal(false)
      onClose()
    } catch (err) {
      if (err instanceof TokenFormatError) setError(err.message)
      else if (err instanceof Error) setError(err.message)
      else setError('Token could not be verified.')
    } finally {
      setBusy(false)
    }
  }

  const reset = async () => {
    setError(null)
    setBusy(true)
    try {
      await resetSession()
      toast('New session created.', 'success')
      setValue('')
      onClose()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not create a session.')
    } finally {
      setBusy(false)
    }
  }

  const copyToken = async () => {
    if (!session?.token) return
    try {
      await navigator.clipboard.writeText(session.token)
      toast('Token copied.', 'success')
    } catch {
      setError('Clipboard access was blocked.')
    }
  }

  return (
    <Dialog
      open={open}
      onClose={close}
      title="Session"
      footer={
        <>
          <Button onClick={close} disabled={busy}>
            Close
          </Button>
          <Button variant="primary" onClick={() => void submit()} loading={busy} disabled={!value.trim()}>
            Apply
          </Button>
        </>
      }
    >
      <table>
        <tbody>
          <tr>
            <th>Role</th>
            <td>{session?.role || '—'}</td>
          </tr>
          <tr>
            <th>Auth</th>
            <td>{session?.authType || 'anonymous'}</td>
          </tr>
          <tr>
            <th>User</th>
            <td>{shortId(session?.userId, 12)}</td>
          </tr>
          <tr>
            <th>Status</th>
            <td>{status}</td>
          </tr>
        </tbody>
      </table>

      <p>
        <code>{reveal ? session?.token || '—' : maskToken(session?.token ?? null)}</code>
      </p>
      <p>
        <button type="button" className="text-btn" onClick={() => setReveal((current) => !current)}>
          {reveal ? 'Hide' : 'Show'}
        </button>{' '}
        <button type="button" className="text-btn" onClick={() => void copyToken()} disabled={!session?.token}>
          Copy
        </button>
      </p>

      <Input
        label="Token"
        placeholder="anonymous-…"
        value={value}
        onChange={(event) => setValue(event.target.value)}
        onKeyDown={(event) => {
          if (event.key === 'Enter') void submit()
        }}
        autoComplete="off"
        spellCheck={false}
      />

      {error && <InlineNotice tone="error">{error}</InlineNotice>}

      <p>
        <Button variant="danger" size="sm" onClick={() => void reset()} disabled={busy}>
          Reset session
        </Button>
      </p>
    </Dialog>
  )
}
