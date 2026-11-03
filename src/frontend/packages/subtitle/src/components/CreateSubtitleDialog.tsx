import { useEffect, useMemo, useState } from 'react'
import {
  Button,
  Dialog,
  ErrorState,
  InlineNotice,
  Input,
  Link,
  LoadingState,
  Select,
  useAsync,
  useDebounced,
  useNavigate,
  useSession,
  useToast,
} from '@mugiko/common'
import { createSubtitle, listSubtitleProviders } from '../libs/subtitles'
import { parseVideoUrl } from '../utils/video'
import { VideoPreview } from './VideoPreview'

export function CreateSubtitleDialog({ onClose }: { onClose: () => void }) {
  const navigate = useNavigate()
  const { revision } = useSession()
  const { toast } = useToast()

  const [videoUrl, setVideoUrl] = useState('')
  const [providerId, setProviderId] = useState('')
  const [serviceKey, setServiceKey] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({})

  const debouncedUrl = useDebounced(videoUrl, 350)
  const source = useMemo(() => parseVideoUrl(debouncedUrl), [debouncedUrl])

  const providers = useAsync((signal) => listSubtitleProviders(), [revision])

  useEffect(() => {
    if (!providerId && providers.data && providers.data.length > 0) {
      setProviderId(providers.data[0].id)
    }
  }, [providers.data, providerId])

  const selectedProvider = providers.data?.find((provider) => provider.id === providerId)
  const services = (selectedProvider?.services || []).filter((service) => service.is_active !== false)

  useEffect(() => {
    if (services.length === 0) {
      setServiceKey('')
      return
    }
    if (!services.some((service) => service.service_key === serviceKey)) {
      setServiceKey(services[0].service_key)
    }
  }, [services, serviceKey])

  const close = () => {
    if (busy) return
    onClose()
  }

  const submit = async () => {
    const errors: Record<string, string> = {}
    const parsed = parseVideoUrl(videoUrl)
    if (!videoUrl.trim()) errors.video = 'A video URL is required.'
    else if (parsed.kind === 'unsupported') errors.video = 'Use a YouTube link or a direct video file.'
    if (!providerId) errors.provider = 'Choose a provider.'
    if (!serviceKey) errors.service = 'Choose a service.'
    setFieldErrors(errors)
    if (Object.keys(errors).length > 0) return

    setBusy(true)
    setError(null)
    try {
      const subtitle = await createSubtitle({
        video_url: videoUrl.trim(),
        provider_id: providerId,
        service_key: serviceKey,
      })
      const failed = subtitle.status === 'failed'
      toast(
        subtitle.status === 'queued'
          ? 'Subtitle queued for processing.'
          : failed
            ? 'Subtitle creation failed.'
            : 'Subtitle created.',
        failed ? 'error' : 'success',
      )
      navigate(`/subtitle/${subtitle.id}`)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not create the subtitle.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <Dialog
      open
      onClose={close}
      title="New subtitle"
      footer={
        <>
          <Button onClick={close} disabled={busy}>
            Cancel
          </Button>
          <Button
            variant="primary"
            loading={busy}
            onClick={() => void submit()}
            disabled={!providers.data || providers.data.length === 0}
          >
            Create
          </Button>
        </>
      }
    >
      <div className="stack">
        <Input
          label="Video URL"
          value={videoUrl}
          onChange={(event) => {
            setVideoUrl(event.target.value)
            setFieldErrors((current) => ({ ...current, video: '' }))
          }}
          placeholder="https://www.youtube.com/watch?v=…"
          error={fieldErrors.video || undefined}
          autoComplete="off"
          spellCheck={false}
          required
        />

        <p className="status">
          {source.kind === 'youtube'
            ? `YouTube · ${source.videoId}`
            : source.kind === 'file'
              ? 'Direct video'
              : videoUrl.trim()
                ? 'Unsupported URL'
                : ''}
        </p>

        <VideoPreview url={debouncedUrl} title="Preview" />

        {providers.loading && <LoadingState label="Loading providers" />}
        {providers.error && (
          <ErrorState
            message={providers.error}
            forbidden={providers.forbidden}
            onRetry={providers.reload}
          />
        )}

        {!providers.loading && !providers.error && (
          <>
            {providers.data && providers.data.length === 0 && (
              <InlineNotice>
                No providers. <Link to="/subtitle/providers">Add a provider</Link>.
              </InlineNotice>
            )}

            <Select
              label="Provider"
              value={providerId}
              onChange={(event) => setProviderId(event.target.value)}
              error={fieldErrors.provider}
              disabled={!providers.data?.length}
              required
            >
              <option value="">Select provider</option>
              {(providers.data || []).map((provider) => (
                <option key={provider.id} value={provider.id}>
                  {provider.name} · {provider.kind}
                </option>
              ))}
            </Select>

            <Select
              label="Service"
              value={serviceKey}
              onChange={(event) => setServiceKey(event.target.value)}
              error={fieldErrors.service}
              disabled={services.length === 0}
              required
            >
              <option value="">Select service</option>
              {services.map((service) => (
                <option key={service.id} value={service.service_key}>
                  {service.name || service.service_key}
                </option>
              ))}
            </Select>

            {error && <InlineNotice tone="error">{error}</InlineNotice>}
          </>
        )}
      </div>
    </Dialog>
  )
}
