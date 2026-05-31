import { useQuery } from '@tanstack/react-query';
import { api } from '../lib/api';
import { useBucket } from '../lib/BucketContext';

function StatCard({ label, value, hint, color }: { label: string; value: number; hint: string; color: string }) {
  return (
    <div className="bg-white rounded-2xl border border-gray-200/60 p-6 hover:shadow-xl transition-all duration-300">
      <p className="text-sm font-medium text-gray-500 mb-1">{label}</p>
      <p className={`text-4xl font-bold ${color}`}>{value}</p>
      <p className="text-xs text-gray-400 mt-2">{hint}</p>
    </div>
  );
}

export default function Dashboard() {
  const { selectedBucket, selectedBucketId, buckets } = useBucket();

  const { data: stats } = useQuery({
    queryKey: ['graph-stats', selectedBucketId],
    queryFn: () => api.graph.stats(selectedBucketId!),
    enabled: !!selectedBucketId,
  });

  const { data: docsData } = useQuery({
    queryKey: ['documents', selectedBucketId],
    queryFn: () => api.documents.list(selectedBucketId!, 10),
    enabled: !!selectedBucketId,
  });

  const { data: processing } = useQuery({
    queryKey: ['processing-docs'],
    queryFn: () => api.documents.processing(),
    refetchInterval: 2000,
  });

  if (buckets.length === 0) {
    return (
      <div className="text-center py-24">
        <h1 className="text-2xl font-bold text-gray-900 mb-2">No context buckets yet</h1>
        <p className="text-gray-500 mb-6">Upload a document to create your first knowledge graph.</p>
        <a href="/upload" className="inline-block px-6 py-3 bg-indigo-600 text-white font-semibold rounded-xl shadow-lg">
          Upload a document
        </a>
      </div>
    );
  }

  return (
    <div className="space-y-8 animate-fadeIn">
      <div>
        <h1 className="text-3xl font-bold bg-gradient-to-r from-gray-900 to-gray-700 bg-clip-text text-transparent">
          {selectedBucket?.name ?? 'Dashboard'}
        </h1>
        <p className="text-sm text-gray-500 mt-2">
          {selectedBucket?.description?.slice(0, 160) || 'Context bucket overview'}
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <StatCard label="Entities" value={stats?.nodes.total ?? 0} hint="Nodes in this bucket" color="text-blue-600" />
        <StatCard label="Relationships" value={stats?.edges.total ?? 0} hint="Edges in this bucket" color="text-purple-600" />
        <StatCard label="Documents" value={selectedBucket?.document_count ?? 0} hint="Sources ingested" color="text-emerald-600" />
      </div>

      {/* Inferred ontology for this bucket */}
      {selectedBucket && (selectedBucket.entity_types.length > 0 || selectedBucket.relationship_types.length > 0) && (
        <div className="bg-white rounded-xl border border-gray-200 p-6">
          <h2 className="text-lg font-semibold text-gray-900 mb-4">Inferred Ontology</h2>
          <div className="space-y-3">
            <div>
              <span className="text-xs font-semibold text-gray-500 uppercase">Entity types</span>
              <div className="flex flex-wrap gap-2 mt-2">
                {selectedBucket.entity_types.map((t) => (
                  <span key={t} className="px-2.5 py-1 rounded-md text-xs font-medium bg-blue-100 text-blue-800">{t}</span>
                ))}
              </div>
            </div>
            <div>
              <span className="text-xs font-semibold text-gray-500 uppercase">Relationship types</span>
              <div className="flex flex-wrap gap-2 mt-2">
                {selectedBucket.relationship_types.map((t) => (
                  <span key={t} className="px-2.5 py-1 rounded-md text-xs font-medium bg-purple-100 text-purple-800">{t.replace(/_/g, ' ')}</span>
                ))}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Live processing across all buckets */}
      {processing && processing.documents.length > 0 && (
        <div className="bg-gradient-to-br from-orange-50 to-amber-50 rounded-2xl border-2 border-orange-200/60 p-6">
          <h2 className="text-xl font-bold text-gray-900 mb-4">Processing</h2>
          <div className="space-y-4">
            {processing.documents.map((doc) => (
              <div key={doc.id} className="bg-white rounded-xl border border-orange-200/60 p-4">
                <div className="flex items-center justify-between mb-2">
                  <h3 className="font-semibold text-gray-900 text-sm truncate">{doc.title}</h3>
                  <span className="text-xs font-bold text-orange-700">{doc.processing_status}</span>
                </div>
                <div className="w-full bg-gray-200 rounded-full h-2.5 overflow-hidden">
                  <div
                    className="h-2.5 rounded-full bg-gradient-to-r from-orange-500 to-amber-500 transition-all duration-500"
                    style={{ width: `${doc.processing_progress}%` }}
                  />
                </div>
                {doc.processing_error && (
                  <p className="text-xs text-red-700 mt-2">{doc.processing_error}</p>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {stats?.nodes.byType && stats.nodes.byType.length > 0 && (
          <DistributionCard title="Entity Distribution" total={stats.nodes.total} items={stats.nodes.byType} color="bg-blue-600" />
        )}
        {stats?.edges.byType && stats.edges.byType.length > 0 && (
          <DistributionCard title="Relationship Distribution" total={stats.edges.total} items={stats.edges.byType} color="bg-purple-600" />
        )}
      </div>

      {docsData?.documents && docsData.documents.length > 0 && (
        <div className="bg-white rounded-xl border border-gray-200 p-6">
          <h2 className="text-lg font-semibold text-gray-900 mb-4">Documents in this bucket</h2>
          <div className="space-y-3">
            {docsData.documents.map((doc) => (
              <div key={doc.id} className="p-4 bg-gray-50 rounded-lg border border-gray-200 flex items-center justify-between">
                <h3 className="font-medium text-gray-900 text-sm truncate">{doc.title}</h3>
                <span className={`text-xs font-medium px-2.5 py-0.5 rounded-md ${doc.processing_status === 'completed' ? 'bg-green-100 text-green-800' : 'bg-yellow-100 text-yellow-800'}`}>
                  {doc.processing_status}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function DistributionCard({ title, total, items, color }: { title: string; total: number; items: { type: string; count: number }[]; color: string }) {
  return (
    <div className="bg-white rounded-xl border border-gray-200 p-6">
      <h2 className="text-lg font-semibold text-gray-900 mb-4">{title}</h2>
      <div className="space-y-3">
        {items.map((item) => {
          const pct = ((item.count / (total || 1)) * 100).toFixed(1);
          return (
            <div key={item.type} className="space-y-2">
              <div className="flex items-center justify-between text-sm">
                <span className="font-medium text-gray-700 capitalize">{item.type.replace(/_/g, ' ')}</span>
                <span className="text-gray-600">{item.count} ({pct}%)</span>
              </div>
              <div className="w-full bg-gray-100 rounded-full h-2">
                <div className={`${color} h-2 rounded-full transition-all duration-500`} style={{ width: `${pct}%` }} />
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
