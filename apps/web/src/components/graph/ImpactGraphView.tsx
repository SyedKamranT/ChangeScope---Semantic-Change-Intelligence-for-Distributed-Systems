import React, { useState, useMemo } from 'react'
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
import { ServiceNode, DatabaseNode, EndpointNode, EventNode } from './CustomNodes'
import { NodeDetailDrawer, SelectedNodeDetail } from './NodeDetailDrawer'
import { Button } from '../ui/Button'

const nodeTypes = {
  service: ServiceNode,
  database: DatabaseNode,
  endpoint: EndpointNode,
  event: EventNode,
}

export interface ImpactGraphViewProps {
  initialNodes?: Node[]
  initialEdges?: Edge[]
  scenarioPR?: number
}

export const ImpactGraphView: React.FC<ImpactGraphViewProps> = ({
  initialNodes: propNodes,
  initialEdges: propEdges,
  scenarioPR = 142,
}) => {
  const [selectedNode, setSelectedNode] = useState<SelectedNodeDetail | null>(null)
  const [filterMode, setFilterMode] = useState<'ALL' | 'DIRECT_ONLY' | 'RUNTIME_ONLY'>('ALL')

  const defaultNodes: Node[] = useMemo(
    () => [
      {
        id: 'srv-inventory',
        type: 'service',
        position: { x: 300, y: 40 },
        data: {
          label: 'inventory-service',
          serviceName: 'inventory-service',
          tier: 'Tier 1 • Mission Critical',
          is_origin: scenarioPR === 142,
          riskLevel: scenarioPR === 142 ? 'CRITICAL' : 'LOW',
          rpm: 12500,
        },
      },
      {
        id: 'srv-checkout',
        type: 'service',
        position: { x: 60, y: 220 },
        data: {
          label: 'checkout-service',
          serviceName: 'checkout-service',
          tier: 'Tier 1 • Direct Caller',
          is_origin: false,
          riskLevel: scenarioPR === 142 ? 'CRITICAL' : 'LOW',
          rpm: 18500,
          hop: 1,
        },
      },
      {
        id: 'srv-analytics',
        type: 'service',
        position: { x: 540, y: 220 },
        data: {
          label: 'analytics-pipeline',
          serviceName: 'analytics-pipeline',
          tier: 'Tier 2 • Kafka Consumer',
          is_origin: false,
          riskLevel: 'MEDIUM',
          rpm: 4200,
          hop: 1,
        },
      },
      {
        id: 'srv-billing',
        type: 'service',
        position: { x: 60, y: 400 },
        data: {
          label: 'billing-ledger',
          serviceName: 'billing-ledger',
          tier: 'Tier 1 • Transitive',
          is_origin: false,
          riskLevel: scenarioPR === 142 ? 'HIGH' : 'LOW',
          rpm: 8900,
          hop: 2,
        },
      },
      {
        id: 'db-postgres',
        type: 'database',
        position: { x: 320, y: 400 },
        data: {
          label: 'inventory-primary-pg',
        },
      },
    ],
    [scenarioPR]
  )

  const defaultEdges: Edge[] = useMemo(
    () => [
      {
        id: 'e-checkout-inv',
        source: 'srv-checkout',
        target: 'srv-inventory',
        label: 'POST /orders (12.5k RPM)',
        animated: true,
        style: { stroke: '#dc2626', strokeWidth: 2 },
        markerEnd: { type: MarkerType.ArrowClosed, color: '#dc2626' },
      },
      {
        id: 'e-analytics-inv',
        source: 'srv-analytics',
        target: 'srv-inventory',
        label: 'Kafka: order.events',
        animated: true,
        style: { stroke: '#d97706', strokeWidth: 1.5 },
        markerEnd: { type: MarkerType.ArrowClosed, color: '#d97706' },
      },
      {
        id: 'e-billing-checkout',
        source: 'srv-billing',
        target: 'srv-checkout',
        label: 'RPC: VerifyCharge (Hop 2)',
        animated: false,
        style: { stroke: '#2563eb', strokeWidth: 1.5, strokeDasharray: '4,4' },
        markerEnd: { type: MarkerType.ArrowClosed, color: '#2563eb' },
      },
      {
        id: 'e-inv-db',
        source: 'srv-inventory',
        target: 'db-postgres',
        label: 'SQL: inventory_items',
        animated: false,
        style: { stroke: '#0284c7', strokeWidth: 1.5 },
        markerEnd: { type: MarkerType.ArrowClosed, color: '#0284c7' },
      },
    ],
    []
  )

  const [nodes, , onNodesChange] = useNodesState(propNodes || defaultNodes)
  const [edges, , onEdgesChange] = useEdgesState(propEdges || defaultEdges)

  const handleNodeClick = (_: React.MouseEvent, node: Node) => {
    const isTarget = node.id === 'srv-inventory'
    const detail: SelectedNodeDetail = {
      id: node.id,
      name: (node.data?.serviceName as string) || (node.data?.label as string) || node.id,
      urn: `urn:changescope:service:${node.id}`,
      type: node.type === 'database' ? 'Database Cluster' : 'Microservice',
      tier: (node.data?.tier as string) || 'Tier 1 • Platform Core',
      isTarget,
      riskScore: isTarget ? 85 : node.id === 'srv-checkout' ? 82 : 45,
      riskLevel: isTarget || node.id === 'srv-checkout' ? 'CRITICAL' : 'MEDIUM',
      rpm: (node.data?.rpm as number) || 12500,
      p95LatencyMs: 18.4,
      callers:
        node.id === 'srv-inventory'
          ? [{ name: 'checkout-service', protocol: 'HTTP', rpm: 12500 }]
          : [],
      consumers:
        node.id === 'srv-checkout'
          ? [{ name: 'billing-ledger', protocol: 'GRPC', rpm: 8900 }]
          : node.id === 'srv-inventory'
          ? [{ name: 'analytics-pipeline', protocol: 'KAFKA', rpm: 4200 }]
          : [],
      evidenceCitations: [
        {
          identifier: 'OrderStatus schema definition',
          path: 'src/api/schemas/order.py',
          lines: '42-48',
        },
        {
          identifier: 'OpenAPI Operation POST /orders',
          path: 'docs/api/openapi.json',
          lines: '112-140',
        },
      ],
    }
    setSelectedNode(detail)
  }

  return (
    <div className="w-full bg-white border border-slate-200/90 rounded-2xl overflow-hidden flex flex-col shadow-premium">
      {/* Top Filter and Legend Toolbar */}
      <div className="px-5 py-3 border-b border-slate-200 bg-slate-50/70 flex flex-wrap items-center justify-between gap-3 text-xs">
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-1.5 text-slate-800 font-semibold">
            <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
            <span>Interactive Blast Radius DAG</span>
          </div>

          <div className="hidden sm:flex items-center gap-2 pl-3 border-l border-slate-200 text-[11px] text-slate-500 font-medium">
            <span className="flex items-center gap-1">
              <span className="w-2 h-0.5 bg-red-500 inline-block" />
              Direct Breaking Edge
            </span>
            <span>•</span>
            <span className="flex items-center gap-1">
              <span className="w-2 h-0.5 bg-blue-600 border-t border-dashed inline-block" />
              Transitive (Hop 2+)
            </span>
            <span>•</span>
            <span className="flex items-center gap-1">
              <span className="w-2 h-0.5 bg-amber-600 inline-block" />
              Kafka Stream
            </span>
          </div>
        </div>

        {/* Filter Controls */}
        <div className="flex items-center gap-1.5">
          <Button
            size="sm"
            variant={filterMode === 'ALL' ? 'primary' : 'outline'}
            onClick={() => setFilterMode('ALL')}
          >
            All Entities
          </Button>
          <Button
            size="sm"
            variant={filterMode === 'DIRECT_ONLY' ? 'primary' : 'outline'}
            onClick={() => setFilterMode('DIRECT_ONLY')}
          >
            Direct Callers
          </Button>
          <Button
            size="sm"
            variant={filterMode === 'RUNTIME_ONLY' ? 'primary' : 'outline'}
            onClick={() => setFilterMode('RUNTIME_ONLY')}
          >
            Observed OTel Only
          </Button>
        </div>
      </div>

      {/* ReactFlow Interactive Canvas */}
      <div className="w-full h-[580px] bg-[#fafafa] relative">
        <ReactFlow
          nodes={nodes}
          edges={edges}
          nodeTypes={nodeTypes}
          onNodesChange={onNodesChange}
          onEdgesChange={onEdgesChange}
          onNodeClick={handleNodeClick}
          fitView
          fitViewOptions={{ padding: 0.2 }}
        >
          <Background color="#cbd5e1" gap={24} size={1.2} />
          <Controls className="bg-white border border-slate-200 text-slate-600 shadow-md" />
          <MiniMap
            nodeColor={(n) => (n.data?.is_origin ? '#dc2626' : '#2563eb')}
            className="bg-white border border-slate-200 rounded-lg shadow-sm"
            maskColor="rgba(248, 250, 252, 0.75)"
          />
        </ReactFlow>
      </div>

      {/* Selected Node Details Drawer */}
      <NodeDetailDrawer node={selectedNode} onClose={() => setSelectedNode(null)} />
    </div>
  )
}
