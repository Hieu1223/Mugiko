import { useState } from 'react'
import {
  EmptyState,
  ErrorState,
  Link,
  LoadingState,
  PageTitle,
  Pagination,
  Tabs,
  useAsync,
  useDocumentTitle,
  useSession,
} from '@mugiko/common'
import { listAllNovels, listNovels } from '../libs/novels'
import { NovelTable } from '../components/NovelCard'

type Tab = 'mine' | 'all'

export function WebNovelHomePage() {
  useDocumentTitle('Web novel')
  const { revision } = useSession()
  const [tab, setTab] = useState<Tab>('mine')
  const [page, setPage] = useState(1)

  const state = useAsync(
    (signal) => (tab === 'mine' ? listNovels(page, 12) : listAllNovels(page, 12)),
    [tab, page, revision],
  )

  const novels = state.data?.novels || []

  return (
    <div className="page">
      <PageTitle title="Library" actions={<Link to="/webnovel/add">Add novel</Link>} />

      <Tabs
        tabs={[
          { id: 'mine' as Tab, label: 'My novels' },
          { id: 'all' as Tab, label: 'All novels' },
        ]}
        value={tab}
        onChange={(next) => {
          setTab(next)
          setPage(1)
        }}
        ariaLabel="Novel library"
      />

      {state.loading && <LoadingState label="Loading library" />}
      {state.error && (
        <ErrorState message={state.error} forbidden={state.forbidden} onRetry={state.reload} />
      )}

      {!state.loading && !state.error && novels.length === 0 && (
        <EmptyState
          title={tab === 'mine' ? 'No novels.' : 'No public novels.'}
          action={<Link to="/webnovel/add">Add novel</Link>}
        />
      )}

      {!state.loading && novels.length > 0 && (
        <>
          <NovelTable novels={novels} />
          <Pagination
            page={state.data?.page || page}
            totalPages={Math.max(1, Math.ceil((state.data?.total || 0) / 12))}
            total={state.data?.total}
            onChange={setPage}
          />
        </>
      )}
    </div>
  )
}
