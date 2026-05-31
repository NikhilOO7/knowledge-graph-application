import { useBucket } from '../lib/BucketContext';

/** Dropdown that lets the user choose which context bucket's graph to view. */
export default function BucketSelector() {
  const { buckets, selectedBucketId, setSelectedBucketId, isLoading } = useBucket();

  if (isLoading) {
    return <div className="text-sm text-gray-400 px-3 py-2">Loading buckets…</div>;
  }

  if (buckets.length === 0) {
    return (
      <span className="text-sm text-gray-400 px-3 py-2 italic">No buckets yet — upload a document</span>
    );
  }

  return (
    <div className="flex items-center space-x-2">
      <svg className="w-4 h-4 text-indigo-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" />
      </svg>
      <select
        value={selectedBucketId ?? ''}
        onChange={(e) => setSelectedBucketId(e.target.value || null)}
        className="px-3 py-2 border-2 border-gray-200 rounded-lg text-sm font-medium bg-white focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 max-w-[16rem]"
        title="Context bucket"
      >
        {buckets.map((b) => (
          <option key={b.id} value={b.id}>
            {b.name} ({b.node_count}n / {b.edge_count}e)
          </option>
        ))}
      </select>
    </div>
  );
}
