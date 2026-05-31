import type {
  Bucket,
  DocumentItem,
  GraphEdge,
  GraphNode,
  GraphStats,
  IngestResponse,
  JobStatus,
  NodeDetail,
  QAResponse,
} from './types';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:3000';

async function fetchAPI<T>(endpoint: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${API_URL}${endpoint}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...options?.headers,
    },
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Unknown error' }));
    throw new Error(error.detail || error.error || `HTTP ${response.status}`);
  }
  return response.json();
}

export const api = {
  buckets: {
    list: () => fetchAPI<{ buckets: Bucket[] }>('/api/buckets'),
    get: (id: string) => fetchAPI<Bucket>(`/api/buckets/${id}`),
    create: (name: string, description?: string) =>
      fetchAPI<Bucket>('/api/buckets', {
        method: 'POST',
        body: JSON.stringify({ name, description }),
      }),
    remove: (id: string) =>
      fetchAPI<{ deleted: string }>(`/api/buckets/${id}`, { method: 'DELETE' }),
  },

  documents: {
    list: (bucketId?: string, limit = 20) => {
      const qp = new URLSearchParams();
      if (bucketId) qp.set('bucket_id', bucketId);
      qp.set('limit', String(limit));
      return fetchAPI<{ documents: DocumentItem[] }>(`/api/documents?${qp}`);
    },
    processing: () => fetchAPI<{ documents: DocumentItem[] }>('/api/documents/processing'),
    process: (id: string) =>
      fetchAPI<{ job_id: string; document_id: string; status: string }>(
        `/api/documents/${id}/process`,
        { method: 'POST' }
      ),
  },

  graph: {
    nodes: (bucketId: string, params?: { type?: string; search?: string; limit?: number }) => {
      const qp = new URLSearchParams({ bucket_id: bucketId });
      if (params?.type) qp.set('type', params.type);
      if (params?.search) qp.set('search', params.search);
      if (params?.limit) qp.set('limit', String(params.limit));
      return fetchAPI<{ nodes: GraphNode[] }>(`/api/graph/nodes?${qp}`);
    },
    node: (id: string) => fetchAPI<NodeDetail>(`/api/graph/nodes/${id}`),
    edges: (bucketId: string, params?: { type?: string; limit?: number }) => {
      const qp = new URLSearchParams({ bucket_id: bucketId });
      if (params?.type) qp.set('type', params.type);
      if (params?.limit) qp.set('limit', String(params.limit));
      return fetchAPI<{ edges: GraphEdge[] }>(`/api/graph/edges?${qp}`);
    },
    stats: (bucketId: string) => fetchAPI<GraphStats>(`/api/graph/stats?bucket_id=${bucketId}`),
  },

  ingest: {
    upload: (file: File, bucketId?: string) => {
      const form = new FormData();
      form.append('file', file);
      if (bucketId) form.append('bucket_id', bucketId);
      form.append('auto_process', 'true');
      return fetch(`${API_URL}/api/ingest/upload`, { method: 'POST', body: form }).then(
        async (r) => {
          if (!r.ok) throw new Error((await r.json()).detail || `HTTP ${r.status}`);
          return r.json() as Promise<IngestResponse>;
        }
      );
    },
    text: (title: string, text: string, bucketId?: string) =>
      fetchAPI<IngestResponse>('/api/ingest/text', {
        method: 'POST',
        body: JSON.stringify({ title, text, bucket_id: bucketId, auto_process: true }),
      }),
    status: (jobId: string) => fetchAPI<JobStatus>(`/api/ingest/status/${jobId}`),
  },

  qa: {
    ask: (bucketId: string, question: string) =>
      fetchAPI<QAResponse>('/api/qa', {
        method: 'POST',
        body: JSON.stringify({ bucket_id: bucketId, question }),
      }),
  },
};
