import { Link } from '@mugiko/common'
import type { Novel } from '../libs/types'

export function NovelTable({ novels }: { novels: Novel[] }) {
  return (
    <table>
      <thead>
        <tr>
          <th>Title</th>
          <th>Author</th>
          <th>Source</th>
        </tr>
      </thead>
      <tbody>
        {novels.map((novel) => (
          <tr key={novel.id}>
            <td>
              <Link to={`/webnovel/${novel.id}`}>{novel.title}</Link>
            </td>
            <td>{novel.author || '—'}</td>
            <td>{novel.source}</td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}

export function NovelCard({ novel }: { novel: Novel; index?: number }) {
  return (
    <article>
      <Link to={`/webnovel/${novel.id}`}>{novel.title}</Link>
      <p className="muted small">{novel.author || '—'}</p>
    </article>
  )
}
