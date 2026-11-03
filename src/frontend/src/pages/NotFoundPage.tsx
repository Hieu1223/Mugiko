import { Link } from '@mugiko/common'

export function NotFoundPage() {
  return (
    <div className="page">
      <h1>Not found</h1>
      <p>
        <Link to="/">Home</Link>
      </p>
    </div>
  )
}
