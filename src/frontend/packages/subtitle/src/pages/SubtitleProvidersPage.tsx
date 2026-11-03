import { useState } from 'react'
import {
  Button,
  ErrorState,
  Input,
  LoadingState,
  PageTitle,
  Select,
  relativeDate,
  useAsync,
  useDocumentTitle,
  useSession,
  useToast,
} from '@mugiko/common'
import { createSubtitleProvider, listSubtitleProviders } from '../libs/subtitles'

export function SubtitleProvidersPage() {
  useDocumentTitle('Subtitle providers')
  const { revision } = useSession()
  const { toast } = useToast()
  const [name, setName] = useState('')
  const [kind, setKind] = useState<'remote' | 'youtube'>('remote')
  const [baseUrl, setBaseUrl] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const providers = useAsync((signal) => listSubtitleProviders(), [revision])

  const submit = async () => {
    if (!name.trim()) {
      setError('A provider name is required.')
      return
    }
    setBusy(true)
    setError(null)
    try {
      await createSubtitleProvider({
        name: name.trim(),
        kind,
        base_url: baseUrl.trim() || undefined,
      })
      toast('Provider created.', 'success')
      setName('')
      setBaseUrl('')
      setKind('remote')
      providers.reload()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not create the provider.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="page">
      <PageTitle title="Providers" />

      <form
        className="form-row"
        onSubmit={(event) => {
          event.preventDefault()
          void submit()
        }}
      >
        <Input
          label="Name"
          value={name}
          onChange={(event) => setName(event.target.value)}
          placeholder="Provider name"
          maxLength={100}
        />
        <Select
          label="Kind"
          value={kind}
          onChange={(event) => setKind(event.target.value as 'remote' | 'youtube')}
        >
          <option value="remote">remote</option>
          <option value="youtube">youtube</option>
        </Select>
        <Input
          label="Base URL"
          value={baseUrl}
          onChange={(event) => setBaseUrl(event.target.value)}
          placeholder="https://example.com"
        />
        <Button type="submit" variant="primary" loading={busy}>
          Create
        </Button>
      </form>
      {error && <p className="field__error">{error}</p>}

      {providers.loading && <LoadingState label="Loading providers" />}
      {providers.error && (
        <ErrorState
          message={providers.error}
          forbidden={providers.forbidden}
          onRetry={providers.reload}
        />
      )}

      {!providers.loading && !providers.error && providers.data && providers.data.length === 0 && (
        <p className="status">No providers.</p>
      )}

      {providers.data && providers.data.length > 0 && (
        <table>
          <thead>
            <tr>
              <th>Name</th>
              <th>Kind</th>
              <th>Base URL</th>
              <th>Last sync</th>
              <th>Services</th>
            </tr>
          </thead>
          <tbody>
            {providers.data.map((provider) => (
              <tr key={provider.id}>
                <td>
                  {provider.name}
                  {provider.is_active === false && <span className="muted"> · inactive</span>}
                </td>
                <td>
                  {provider.kind}
                  {!['remote', 'youtube'].includes(provider.kind) && (
                    <span className="muted small"> · legacy</span>
                  )}
                </td>
                <td>{provider.base_url || '—'}</td>
                <td>{provider.last_synced_at ? relativeDate(provider.last_synced_at) : 'never'}</td>
                <td>
                  {provider.services && provider.services.length > 0 ? (
                    <ul className="lookup-list">
                      {provider.services.map((service) => (
                        <li key={service.id}>
                          {service.name || service.service_key}
                          <span className="muted small">
                            {' '}
                            · {service.service_key}
                            {service.is_active ? '' : ' · off'}
                          </span>
                        </li>
                      ))}
                    </ul>
                  ) : (
                    <span className="muted">none</span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  )
}
