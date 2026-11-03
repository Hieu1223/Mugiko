export function SessionBadge({ onClick }: { onClick: () => void }) {
  return (
    <button type="button" className="session-badge" onClick={onClick}>
      Session
    </button>
  )
}
