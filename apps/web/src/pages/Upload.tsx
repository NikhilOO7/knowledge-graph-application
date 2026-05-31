import { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from '../lib/api';
import { useBucket } from '../lib/BucketContext';
import type { IngestResponse } from '../lib/types';

export default function Upload() {
  const { buckets, selectedBucketId } = useBucket();
  const queryClient = useQueryClient();

  // "" => auto-route (let the Context-Router decide the bucket)
  const [targetBucket, setTargetBucket] = useState('');
  const [file, setFile] = useState<File | null>(null);
  const [title, setTitle] = useState('');
  const [text, setText] = useState('');
  const [jobId, setJobId] = useState<string | null>(null);
  const [lastResponse, setLastResponse] = useState<IngestResponse | null>(null);

  const onIngested = (data: IngestResponse) => {
    setJobId(data.job_id || null);
    setLastResponse(data);
    queryClient.invalidateQueries({ queryKey: ['buckets'] });
  };

  const uploadMutation = useMutation({
    mutationFn: () => api.ingest.upload(file!, targetBucket || undefined),
    onSuccess: onIngested,
  });

  const textMutation = useMutation({
    mutationFn: () => api.ingest.text(title || 'Pasted document', text, targetBucket || undefined),
    onSuccess: onIngested,
  });

  const { data: job } = useQuery({
    queryKey: ['job', jobId],
    queryFn: () => api.ingest.status(jobId!),
    enabled: !!jobId,
    refetchInterval: (q) => {
      const s = q.state.data?.status;
      if (s === 'completed' || s === 'failed') {
        // Refresh bucket list/counts once the pipeline settles.
        queryClient.invalidateQueries({ queryKey: ['buckets'] });
        return false;
      }
      return 1500;
    },
  });

  return (
    <div className="space-y-8 animate-fadeIn">
      <div>
        <h1 className="text-3xl font-bold bg-gradient-to-r from-gray-900 to-gray-700 bg-clip-text text-transparent">
          Upload a document
        </h1>
        <p className="text-sm text-gray-500 mt-2">
          The system extracts context, builds a knowledge graph, and routes it to a new or existing bucket.
        </p>
      </div>

      {/* Bucket target selector */}
      <div className="bg-white rounded-2xl border border-gray-200/60 p-6">
        <label className="block text-sm font-semibold text-gray-700 mb-2">Target context bucket</label>
        <select
          value={targetBucket}
          onChange={(e) => setTargetBucket(e.target.value)}
          className="w-full px-4 py-3 border-2 border-gray-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-indigo-500 bg-white"
        >
          <option value="">Auto-route (detect or create a bucket)</option>
          {buckets.map((b) => (
            <option key={b.id} value={b.id}>Append to: {b.name}</option>
          ))}
          {selectedBucketId && <option value={selectedBucketId}>Append to current bucket</option>}
        </select>
        <p className="mt-2 text-xs text-gray-500">
          Leave on auto-route to let the Context-Router match existing buckets by similarity, or pick a bucket to force-append.
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* File upload */}
        <div className="bg-white rounded-2xl border border-gray-200/60 p-8">
          <h2 className="text-xl font-bold text-gray-900 mb-1">File (PDF / text)</h2>
          <p className="text-sm text-gray-500 mb-6">Upload a PDF or plain-text document.</p>
          <input
            type="file"
            accept=".pdf,.txt,.md,text/plain"
            onChange={(e) => setFile(e.target.files?.[0] ?? null)}
            className="block w-full text-sm text-gray-600 file:mr-4 file:py-2 file:px-4 file:rounded-lg file:border-0 file:bg-indigo-600 file:text-white file:font-semibold hover:file:bg-indigo-700"
          />
          <button
            onClick={() => uploadMutation.mutate()}
            disabled={!file || uploadMutation.isPending}
            className="mt-6 w-full bg-gradient-to-r from-indigo-600 to-indigo-700 hover:from-indigo-700 hover:to-indigo-800 disabled:from-gray-300 disabled:to-gray-300 text-white font-semibold py-3.5 rounded-xl shadow-lg transition-all"
          >
            {uploadMutation.isPending ? 'Uploading…' : 'Upload & build graph'}
          </button>
          {uploadMutation.isError && (
            <p className="mt-3 text-sm text-red-700">{(uploadMutation.error as Error).message}</p>
          )}
        </div>

        {/* Paste text */}
        <div className="bg-white rounded-2xl border border-gray-200/60 p-8">
          <h2 className="text-xl font-bold text-gray-900 mb-1">Paste text</h2>
          <p className="text-sm text-gray-500 mb-6">Paste raw content directly.</p>
          <input
            type="text"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            placeholder="Document title"
            className="w-full px-4 py-3 mb-3 border-2 border-gray-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-purple-500"
          />
          <textarea
            rows={6}
            value={text}
            onChange={(e) => setText(e.target.value)}
            placeholder="Paste document text here…"
            className="w-full px-4 py-3 border-2 border-gray-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-purple-500 resize-none text-sm"
          />
          <button
            onClick={() => textMutation.mutate()}
            disabled={text.trim().length < 30 || textMutation.isPending}
            className="mt-6 w-full bg-gradient-to-r from-purple-600 to-purple-700 hover:from-purple-700 hover:to-purple-800 disabled:from-gray-300 disabled:to-gray-300 text-white font-semibold py-3.5 rounded-xl shadow-lg transition-all"
          >
            {textMutation.isPending ? 'Processing…' : 'Ingest text & build graph'}
          </button>
          {textMutation.isError && (
            <p className="mt-3 text-sm text-red-700">{(textMutation.error as Error).message}</p>
          )}
        </div>
      </div>

      {/* Job status */}
      {jobId && job && (
        <div className="bg-white rounded-2xl border border-gray-200/60 p-8">
          <h2 className="text-xl font-bold text-gray-900 mb-4">Processing status</h2>
          <div className="space-y-3">
            <Row label="Stage" value={job.stage ?? job.status} />
            <div className="w-full bg-gray-200 rounded-full h-2.5 overflow-hidden">
              <div
                className="h-2.5 rounded-full bg-gradient-to-r from-indigo-500 to-purple-500 transition-all duration-500"
                style={{ width: `${job.progress}%` }}
              />
            </div>
            {(job.bucket_action || lastResponse?.bucket_action) && (
              <Row
                label="Bucket decision"
                value={
                  (job.bucket_action || lastResponse?.bucket_action) === 'created'
                    ? '🆕 Created a new context bucket'
                    : (job.bucket_action || lastResponse?.bucket_action) === 'appended'
                    ? '➕ Appended to an existing bucket'
                    : 'Detecting…'
                }
              />
            )}
            {job.stats && Object.keys(job.stats).length > 0 && (
              <Row label="Extracted" value={`${job.stats.nodes_added ?? 0} nodes, ${job.stats.edges_added ?? 0} edges`} />
            )}
            {job.error && <p className="text-sm text-red-700">{job.error}</p>}
          </div>
        </div>
      )}
    </div>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between p-4 bg-gray-50 rounded-xl">
      <span className="text-sm font-semibold text-gray-600">{label}</span>
      <span className="text-sm font-medium text-gray-900">{value}</span>
    </div>
  );
}
