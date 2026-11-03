import { useEffect, useState } from 'react'
import {
  Button,
  InlineNotice,
  PageTitle,
  useAsync,
  useDocumentTitle,
  useSession,
  useToast,
} from '@mugiko/common'
import { getSubtitleSettings, updateSubtitleSettings } from '../libs/subtitles'
import { useSubtitlePreferences } from '../libs/preferences'

const SCHEMA_VERSION = 1

export function SubtitleSettingsPage() {
  useDocumentTitle('Subtitle settings')
  const { revision } = useSession()
  const { toast } = useToast()
  const [prefs, setPrefs] = useSubtitlePreferences()
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [remoteLoaded, setRemoteLoaded] = useState(false)

  const settings = useAsync((signal) => getSubtitleSettings(), [revision])

  useEffect(() => {
    if (!settings.data || remoteLoaded) return
    const data = settings.data.data || {}
    setPrefs((current) => ({
      ...current,
      fontScale: typeof data.font_scale === 'number' ? data.font_scale : current.fontScale,
      autoScroll: typeof data.auto_scroll === 'boolean' ? data.auto_scroll : current.autoScroll,
      showTimestamps:
        typeof data.show_timestamps === 'boolean' ? data.show_timestamps : current.showTimestamps,
      lookupOnClick:
        typeof data.lookup_on_click === 'boolean' ? data.lookup_on_click : current.lookupOnClick,
      displayMode:
        data.display_mode === 'normal' ||
        data.display_mode === 'hiragana' ||
        data.display_mode === 'both' ||
        data.display_mode === 'reverse'
          ? data.display_mode
          : current.displayMode,
      layout:
        data.layout === 'side-left' ||
        data.layout === 'side-right' ||
        data.layout === 'stack-top' ||
        data.layout === 'stack-bottom'
          ? data.layout
          : current.layout,
    }))
    setRemoteLoaded(true)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [settings.data])

  const save = async () => {
    setBusy(true)
    setError(null)
    try {
      await updateSubtitleSettings(SCHEMA_VERSION, {
        font_scale: prefs.fontScale,
        auto_scroll: prefs.autoScroll,
        show_timestamps: prefs.showTimestamps,
        lookup_on_click: prefs.lookupOnClick,
        display_mode: prefs.displayMode,
        layout: prefs.layout,
      })
      toast('Settings saved.', 'success')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not save settings.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="page">
      <PageTitle title="Settings" />

      <div className="stack">
        <label className="slider-field">
          <span className="field__label">Transcript size · {Math.round(prefs.fontScale * 100)}%</span>
          <input
            type="range"
            min={0.8}
            max={1.6}
            step={0.05}
            value={prefs.fontScale}
            onChange={(event) =>
              setPrefs((current) => ({ ...current, fontScale: Number(event.target.value) }))
            }
          />
        </label>

        <label>
          Display{' '}
          <select
            value={prefs.displayMode}
            onChange={(event) =>
              setPrefs((current) => ({
                ...current,
                displayMode: event.target.value as typeof current.displayMode,
              }))
            }
          >
            <option value="normal">Normal</option>
            <option value="hiragana">Hiragana</option>
            <option value="both">Both (ruby)</option>
            <option value="reverse">Reverse (kanji on top)</option>
          </select>
        </label>

        <label>
          Layout{' '}
          <select
            value={prefs.layout}
            onChange={(event) =>
              setPrefs((current) => ({
                ...current,
                layout: event.target.value as typeof current.layout,
              }))
            }
          >
            <option value="side-left">Video left</option>
            <option value="side-right">Video right</option>
            <option value="stack-top">Video top</option>
            <option value="stack-bottom">Video bottom</option>
          </select>
        </label>

        <label>
          <input
            type="checkbox"
            checked={prefs.autoScroll}
            onChange={(event) =>
              setPrefs((current) => ({ ...current, autoScroll: event.target.checked }))
            }
          />{' '}
          Auto-scroll
        </label>

        <label>
          <input
            type="checkbox"
            checked={prefs.showTimestamps}
            onChange={(event) =>
              setPrefs((current) => ({ ...current, showTimestamps: event.target.checked }))
            }
          />{' '}
          Timestamps
        </label>

        <label>
          <input
            type="checkbox"
            checked={prefs.lookupOnClick}
            onChange={(event) =>
              setPrefs((current) => ({ ...current, lookupOnClick: event.target.checked }))
            }
          />{' '}
          Word lookup
        </label>

        {error && <InlineNotice tone="error">{error}</InlineNotice>}

        <div>
          <Button
            variant="primary"
            loading={busy}
            onClick={() => void save()}
            disabled={settings.forbidden}
          >
            Save
          </Button>
        </div>

        {settings.forbidden && <p className="status">Remote settings unavailable.</p>}
        {settings.error && !settings.forbidden && <p className="field__error">{settings.error}</p>}
      </div>
    </div>
  )
}
