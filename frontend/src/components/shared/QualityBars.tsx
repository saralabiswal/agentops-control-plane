export function QualityBars({ score }: { score: number | null }) {
  const pct = Math.round((score ?? 0) * 100)
  return (
    <div className="quality-bars">
      <span>Quality</span>
      <div><i style={{ width: `${pct}%` }} /></div>
      <b>{score === null ? 'Pending' : `${pct}%`}</b>
    </div>
  )
}

