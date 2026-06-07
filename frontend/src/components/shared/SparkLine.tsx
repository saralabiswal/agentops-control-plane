import { Line, LineChart, ResponsiveContainer } from 'recharts'

export function SparkLine({ values }: { values: number[] }) {
  const data = values.map((value, index) => ({ index, value }))
  return (
    <ResponsiveContainer width="100%" height={42}>
      <LineChart data={data}>
        <Line type="monotone" dataKey="value" stroke="#0f766e" strokeWidth={2} dot={false} />
      </LineChart>
    </ResponsiveContainer>
  )
}

