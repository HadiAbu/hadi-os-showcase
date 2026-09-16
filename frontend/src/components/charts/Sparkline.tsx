export function Sparkline({
  values,
  width = 120,
  height = 32,
  className,
}: {
  values: number[]
  width?: number
  height?: number
  className?: string
}) {
  if (values.length === 0) {
    return (
      <svg width={width} height={height} className={className} aria-hidden>
        <line
          x1={0}
          y1={height - 1}
          x2={width}
          y2={height - 1}
          stroke="var(--hairline)"
          strokeWidth={1.5}
        />
      </svg>
    )
  }
  const max = Math.max(...values, 1)
  const step = values.length > 1 ? width / (values.length - 1) : 0
  const pad = 3
  const points = values
    .map((v, i) => {
      const x = i * step
      const y = pad + (1 - v / max) * (height - pad * 2)
      return `${x.toFixed(1)},${y.toFixed(1)}`
    })
    .join(' ')
  return (
    <svg width={width} height={height} className={className} aria-hidden>
      <polyline
        points={points}
        fill="none"
        stroke="var(--aqua)"
        strokeWidth={1.8}
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  )
}
