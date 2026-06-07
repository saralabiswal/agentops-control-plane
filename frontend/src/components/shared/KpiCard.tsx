type KpiCardProps = {
  label: string
  value: string
  tone?: 'neutral' | 'good' | 'warn'
}

export function KpiCard({ label, value, tone = 'neutral' }: KpiCardProps) {
  return (
    <div className={`kpi kpi-${tone}`}>
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  )
}

