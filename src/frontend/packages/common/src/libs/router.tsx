export { Link, useNavigate, useParams, useSearchParams } from 'react-router-dom'

const UUID_PATTERN =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i

/** All API resource IDs are UUIDs. */
export function isUuid(value: string | null | undefined): boolean {
  return Boolean(value && UUID_PATTERN.test(value))
}
