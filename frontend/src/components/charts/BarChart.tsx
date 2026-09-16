/** Single-hue vertical bar chart (aqua). Labels shown sparsely to avoid crowding. */
export function BarChart({
  data,
  height = 140,
}: {
  data: { label: string; value: number }[]
  height?: number
}) {
  if (data.length === 0) {
    return <p className="text-sm text-faint">No data in this window.</p>
  }
  const max = Math.max(...data.map((d) => d.value), 1)
  const labelEvery = Math.ceil(data.length / 6)
  return (
    <div className="flex items-end justify-start gap-[3px]" style={{ height }}>
      {data.map((d, i) => (
        <div
          key={d.label + i}
          className="group relative flex flex-1 flex-col items-center justify-end"
          style={{ height, maxWidth: 40 }}
        >
          <div
            className="w-full min-w-[6px] rounded-sm bg-aqua/70 transition-colors group-hover:bg-aqua"
            style={{ height: `${Math.max((d.value / max) * (height - 16), d.value > 0 ? 2 : 0)}px` }}
            title={`${d.label}: ${d.value.toLocaleString()}`}
          />
          <span className="mt-1 h-3 text-[9px] text-faint">
            {i % labelEvery === 0 ? d.label.slice(5) : ''}
          </span>
        </div>
      ))}
    </div>
  )
}
