import { useState } from 'react'
import {
  Button,
  ErrorState,
  InlineNotice,
  Input,
  Link,
  PageTitle,
  useDocumentTitle,
  useNavigate,
  useToast,
} from '@mugiko/common'
import { addNovel, previewNovel } from '../libs/novels'
import type { PreviewResponse } from '../libs/types'

export function WebNovelAddPage() {
  useDocumentTitle('Add novel')
  const navigate = useNavigate()
  const { toast } = useToast()
  const [url, setUrl] = useState('')
  const [preview, setPreview] = useState<PreviewResponse | null>(null)
  const [previewing, setPreviewing] = useState(false)
  const [previewError, setPreviewError] = useState<string | null>(null)
  const [adding, setAdding] = useState(false)
  const [addError, setAddError] = useState<string | null>(null)
  const [jobId, setJobId] = useState<string | null>(null)
  const [addedId, setAddedId] = useState<string | null>(null)

  const runPreview = async () => {
    const trimmed = url.trim()
    if (!trimmed) {
      setPreviewError('Enter a URL.')
      return
    }
    setPreviewing(true)
    setPreviewError(null)
    setPreview(null)
    setJobId(null)
    setAddedId(null)
    try {
      const result = await previewNovel(trimmed)
      setPreview(result)
    } catch (err) {
      setPreviewError(err instanceof Error ? err.message : 'Could not preview this URL.')
    } finally {
      setPreviewing(false)
    }
  }

  const confirmAdd = async () => {
    if (!preview) return
    setAdding(true)
    setAddError(null)
    try {
      const result = await addNovel(preview.url || url.trim())
      setJobId(result.job_id || null)
      setAddedId(result.novel.id)
      toast(`“${result.novel.title}” added.`, 'success')
    } catch (err) {
      setAddError(err instanceof Error ? err.message : 'Could not add this novel.')
    } finally {
      setAdding(false)
    }
  }

  return (
    <div className="page">
      <PageTitle title="Add novel" actions={<Link to="/webnovel">← Library</Link>} />

      <form
        className="form-row"
        onSubmit={(event) => {
          event.preventDefault()
          void runPreview()
        }}
      >
        <Input
          label="URL"
          value={url}
          onChange={(event) => setUrl(event.target.value)}
          placeholder="https://ncode.syosetu.com/…"
          autoComplete="off"
          spellCheck={false}
          error={previewError || undefined}
        />
        <Button type="submit" variant="primary" loading={previewing}>
          Preview
        </Button>
      </form>

      {preview && (
        <>
          <h2>Preview</h2>
          <table>
            <tbody>
              <tr>
                <th>Title</th>
                <td>{preview.title}</td>
              </tr>
              <tr>
                <th>Author</th>
                <td>{preview.author || '—'}</td>
              </tr>
              <tr>
                <th>Source</th>
                <td>{preview.source}</td>
              </tr>
              {preview.synopsis && (
                <tr>
                  <th>Synopsis</th>
                  <td>{preview.synopsis}</td>
                </tr>
              )}
              <tr>
                <th>URL</th>
                <td>
                  <a href={preview.url} target="_blank" rel="noreferrer noopener">
                    {preview.url}
                  </a>
                </td>
              </tr>
            </tbody>
          </table>

          <div className="form-row">
            {addedId ? (
              <>
                <Button variant="primary" onClick={() => navigate(`/webnovel/${addedId}`)}>
                  Open novel
                </Button>
                <Button
                  onClick={() => {
                    setPreview(null)
                    setUrl('')
                    setAddedId(null)
                    setJobId(null)
                  }}
                >
                  Add another
                </Button>
              </>
            ) : (
              <Button variant="primary" loading={adding} onClick={() => void confirmAdd()}>
                Add to library
              </Button>
            )}
          </div>
        </>
      )}

      {jobId && (
        <InlineNotice tone="success">
          Import queued. Job <code>{jobId}</code>.
        </InlineNotice>
      )}
      {addError && <ErrorState message={addError} />}
    </div>
  )
}
