import ForceGraph3D from 'react-force-graph-3d'

// Isolated so `three` (~1 MB) is only fetched when a viewer switches to 3D.
export interface Canvas3DProps {
  graphData: { nodes: object[]; links: object[] }
  width: number
  height: number
  backgroundColor: string
  nodeLabel: (n: object) => string
  nodeColor: (n: object) => string
  linkColor: () => string
  onNodeClick: (n: object) => void
  cooldownTicks: number
  enableNodeDrag: boolean
}

export default function GraphCanvas3D(props: Canvas3DProps) {
  return (
    <ForceGraph3D
      {...props}
      nodeOpacity={0.9}
      nodeResolution={12}
      linkOpacity={0.35}
    />
  )
}
