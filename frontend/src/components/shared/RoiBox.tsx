export function RoiBox({ impact, cost }: { impact: number; cost: number }) {
  const roi = cost > 0 ? impact / cost : 0
  return (
    <section className="roi-box">
      <span>Outcome ROI</span>
      <strong>{roi.toFixed(1)}x</strong>
      <p>${Math.round(impact).toLocaleString()} protected against ${cost.toFixed(2)} model cost</p>
    </section>
  )
}

