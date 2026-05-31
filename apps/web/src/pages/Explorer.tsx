import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import ReactFlow, { Background, Controls, MiniMap } from 'reactflow';
import 'reactflow/dist/style.css';
import { api } from '../lib/api';
import { useBucket } from '../lib/BucketContext';

const PALETTE = ['#3b82f6', '#10b981', '#f59e0b', '#8b5cf6', '#ef4444', '#06b6d4', '#ec4899', '#84cc16'];

export default function Explorer() {
  const { selectedBucketId, selectedBucket } = useBucket();
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  const [searchTerm, setSearchTerm] = useState('');
  const [nodeTypeFilter, setNodeTypeFilter] = useState('');

  const { data: nodesData, isLoading } = useQuery({
    queryKey: ['nodes', selectedBucketId, nodeTypeFilter, searchTerm],
    queryFn: () =>
      api.graph.nodes(selectedBucketId!, {
        type: nodeTypeFilter || undefined,
        search: searchTerm || undefined,
        limit: 150,
      }),
    enabled: !!selectedBucketId,
  });

  const { data: edgesData } = useQuery({
    queryKey: ['edges', selectedBucketId],
    queryFn: () => api.graph.edges(selectedBucketId!, { limit: 300 }),
    enabled: !!selectedBucketId,
  });

  const { data: selectedNodeData } = useQuery({
    queryKey: ['node', selectedNodeId],
    queryFn: () => api.graph.node(selectedNodeId!),
    enabled: !!selectedNodeId,
  });

  // Build a stable color map from the bucket's entity types.
  const typeColors: Record<string, string> = {};
  (selectedBucket?.entity_types ?? []).forEach((t, i) => {
    typeColors[t] = PALETTE[i % PALETTE.length];
  });
  const colorFor = (type: string) => typeColors[type] ?? '#6b7280';

  const nodes =
    nodesData?.nodes.map((node, index) => {
      const total = nodesData.nodes.length || 1;
      const radius = Math.max(400, total * 15);
      const angle = (index / total) * 2 * Math.PI;
      return {
        id: node.id,
        data: { label: node.name },
        position: { x: Math.cos(angle) * radius + 600, y: Math.sin(angle) * radius + 400 },
        style: {
          background: colorFor(node.type),
          color: '#fff',
          padding: 10,
          borderRadius: 8,
          fontSize: 12,
          fontWeight: 600,
          border: '2px solid rgba(255,255,255,0.2)',
          minWidth: 120,
          textAlign: 'center' as const,
        },
      };
    }) || [];

  const edges =
    edgesData?.edges.map((edge) => ({
      id: edge.id,
      source: edge.source_id,
      target: edge.target_id,
      label: edge.type.replace(/_/g, ' '),
      type: 'smoothstep',
      style: { stroke: '#9ca3af', strokeWidth: 2 },
      labelStyle: { fill: '#6b7280', fontWeight: 600, fontSize: 11 },
    })) || [];

  if (!selectedBucketId) {
    return <div className="text-center py-24 text-gray-500">Select or create a context bucket first.</div>;
  }

  return (
    <div className="space-y-6 animate-fadeIn">
      <div>
        <h1 className="text-3xl font-bold bg-gradient-to-r from-gray-900 to-gray-700 bg-clip-text text-transparent">
          Graph Explorer
        </h1>
        <p className="text-sm text-gray-500 mt-2">
          Exploring <span className="font-semibold">{selectedBucket?.name}</span>
        </p>
      </div>

      <div className="flex gap-6 h-[calc(100vh-14rem)]">
        <div className="flex-1 bg-white rounded-2xl border border-gray-200/60 shadow-lg overflow-hidden">
          <div className="p-5 border-b border-gray-200/60 flex gap-3">
            <input
              type="text"
              placeholder="Search entities..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="flex-1 px-4 py-3 border-2 border-gray-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-indigo-500"
            />
            <select
              value={nodeTypeFilter}
              onChange={(e) => setNodeTypeFilter(e.target.value)}
              className="px-4 py-3 border-2 border-gray-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-indigo-500 bg-white font-medium"
            >
              <option value="">All Types</option>
              {(selectedBucket?.entity_types ?? []).map((t) => (
                <option key={t} value={t}>{t}</option>
              ))}
            </select>
          </div>

          {isLoading ? (
            <div className="flex items-center justify-center h-full text-gray-500">Loading graph…</div>
          ) : nodes.length === 0 ? (
            <div className="flex items-center justify-center h-full text-gray-400">No entities yet in this bucket.</div>
          ) : (
            <ReactFlow nodes={nodes} edges={edges} onNodeClick={(_, n) => setSelectedNodeId(n.id)} fitView>
              <Background />
              <Controls />
              <MiniMap />
            </ReactFlow>
          )}
        </div>

        <div className="w-96 bg-white rounded-2xl border border-gray-200/60 shadow-lg p-6 overflow-y-auto">
          {selectedNodeData ? (
            <div className="space-y-6">
              <h3 className="text-xl font-bold text-gray-900">Node Details</h3>
              <div className="p-4 bg-blue-50 rounded-xl border border-blue-100">
                <label className="text-xs font-semibold text-blue-700 uppercase">Name</label>
                <p className="text-lg font-bold text-gray-900 mt-1">{selectedNodeData.node.name}</p>
              </div>
              <div className="p-4 bg-purple-50 rounded-xl border border-purple-100">
                <label className="text-xs font-semibold text-purple-700 uppercase">Type</label>
                <p className="text-base font-semibold text-gray-900 mt-1 capitalize">{selectedNodeData.node.type}</p>
              </div>
              {selectedNodeData.node.description && (
                <div className="p-4 bg-gray-50 rounded-xl border border-gray-200">
                  <label className="text-xs font-semibold text-gray-700 uppercase">Description</label>
                  <p className="text-sm text-gray-700 mt-2">{selectedNodeData.node.description}</p>
                </div>
              )}
              {selectedNodeData.outgoing_edges.length > 0 && (
                <EdgeList title={`Outgoing (${selectedNodeData.outgoing_edges.length})`} edges={selectedNodeData.outgoing_edges} color="emerald" />
              )}
              {selectedNodeData.incoming_edges.length > 0 && (
                <EdgeList title={`Incoming (${selectedNodeData.incoming_edges.length})`} edges={selectedNodeData.incoming_edges} color="orange" />
              )}
            </div>
          ) : (
            <div className="flex flex-col items-center justify-center h-full text-center text-gray-400">
              <p className="font-medium text-gray-600">Select a node</p>
              <p className="text-sm mt-2">Click any node to see its relationships.</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function EdgeList({ title, edges, color }: { title: string; edges: { id: string; type: string }[]; color: string }) {
  return (
    <div>
      <h4 className="text-sm font-bold text-gray-800 mb-3">{title}</h4>
      <div className="space-y-2">
        {edges.slice(0, 8).map((edge) => (
          <div key={edge.id} className={`p-3 bg-${color}-50 rounded-lg border border-${color}-200`}>
            <span className={`text-sm font-medium text-${color}-800 capitalize`}>{edge.type.replace(/_/g, ' ')}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
