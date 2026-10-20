import { Background, BackgroundVariant, Controls, ReactFlow, type Edge, type Node, type NodeMouseHandler } from '@xyflow/react'
import '@xyflow/react/dist/style.css'

export default function EvidenceGraphView({ nodes, edges, height = 560, onNodeClick }: {
  nodes: Node[]
  edges: Edge[]
  height?: number
  onNodeClick?: NodeMouseHandler
}) {
  return (
    <div style={{ height }} className="overflow-hidden rounded-md border border-line">
      <ReactFlow nodes={nodes} edges={edges} fitView proOptions={{ hideAttribution: true }} onNodeClick={onNodeClick}
        minZoom={0.2} colorMode="dark" style={{ background: '#070c16' }}>
        <Background variant={BackgroundVariant.Dots} gap={18} size={1} color="#1c2940" />
        <Controls showInteractive={false} />
      </ReactFlow>
    </div>
  )
}
