import React from 'react'
import {
  ReactFlow,
  Controls,
  Background,
  MiniMap,
  useNodesState,
  useEdgesState,
  MarkerType,
  Node,
  Edge,
} from '@xyflow/react'

interface GraphViewProps {
  initialNodes: Node[]
  initialEdges: Edge[]
  onNodeSelect?: (nodeId: string) => void
}

export const GraphView: React.FC<GraphViewProps> = ({
  initialNodes,
  initialEdges,
  onNodeSelect,
}) => {
  const [nodes, , onNodesChange] = useNodesState(initialNodes)
  const [edges, , onEdgesChange] = useEdgesState(initialEdges)

  return (
    <div className="w-full h-[520px] bg-[#090d16] rounded-xl border border-border relative overflow-hidden">
      <div className="absolute top-4 left-4 z-10 bg-[#101726]/80 backdrop-blur-md px-3 py-1.5 rounded-lg border border-border text-xs text-slate-300 flex items-center gap-2">
        <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
        <span>Live Knowledge Graph Projection</span>
      </div>

      <ReactFlow
        nodes={nodes}
        edges={edges.map((e) => ({
          ...e,
          animated: true,
          style: { stroke: '#3b82f6', strokeWidth: 2 },
          markerEnd: { type: MarkerType.ArrowClosed, color: '#3b82f6' },
        }))}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onNodeClick={(_, node) => onNodeSelect && onNodeSelect(node.id)}
        fitView
      >
        <Background color="#1e293b" gap={20} size={1} />
        <Controls className="bg-[#101726] border-border text-slate-300 fill-slate-300" />
        <MiniMap
          nodeColor={(n) => (n.data?.is_origin ? '#ef4444' : '#3b82f6')}
          className="bg-[#101726] border border-border rounded-lg"
          maskColor="rgba(9, 13, 22, 0.7)"
        />
      </ReactFlow>
    </div>
  )
}
