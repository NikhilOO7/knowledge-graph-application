// Client-side types mirroring the FastAPI backend schemas.

export interface Bucket {
  id: string;
  name: string;
  description?: string | null;
  entity_types: string[];
  relationship_types: string[];
  document_count: number;
  node_count: number;
  edge_count: number;
  created_at?: string;
  updated_at?: string;
}

export interface DocumentItem {
  id: string;
  bucket_id?: string | null;
  title: string;
  source_type: string;
  filename?: string | null;
  char_count: number;
  processing_status: string;
  processing_progress: number;
  processing_error?: string | null;
  created_at?: string;
}

export interface GraphNode {
  id: string;
  bucket_id: string;
  type: string;
  name: string;
  description?: string;
  properties?: Record<string, unknown>;
}

export interface GraphEdge {
  id: string;
  bucket_id: string;
  source_id: string;
  target_id: string;
  type: string;
  confidence: number;
  properties?: Record<string, unknown>;
}

export interface GraphStats {
  bucket_id?: string;
  nodes: { total: number; byType: { type: string; count: number }[] };
  edges: { total: number; byType: { type: string; count: number }[] };
}

export interface NodeDetail {
  node: GraphNode;
  outgoing_edges: GraphEdge[];
  incoming_edges: GraphEdge[];
}

export interface IngestResponse {
  job_id: string;
  document_id: string;
  bucket_id?: string | null;
  bucket_action: string;
  status: string;
}

export interface JobStatus {
  job_id: string;
  status: string;
  stage?: string;
  progress: number;
  document_id?: string;
  bucket_id?: string | null;
  bucket_action?: string | null;
  error?: string | null;
  stats?: Record<string, number>;
}

export interface QAResponse {
  question: string;
  answer: string;
  context: { source: string; type: string; target: string; confidence?: number }[];
}
