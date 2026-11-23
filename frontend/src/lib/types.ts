// frontend/src/lib/types.ts
// Strict TypeScript types mirrored directly from FastAPI backend (main.py)

export type DetailLevel = 'short' | 'long';
export type ReasoningMode = 'auto' | 'chat' | 'reasoner';

export interface RagAskRequest {
  question: string;
  ministry?: string;
  ministries?: string[] | null;
  years?: string[] | null;
  detail_level?: DetailLevel;
  reasoning_mode?: ReasoningMode;
  byod_doc_id?: string | null;
  byod_doc_ids?: string[] | null;
  byod_text?: string | null;
  auth_token?: string | null;
}

export interface RagSource {
  title?: string;
  file?: string;
  ministry?: string;
  year?: string;
  page?: number;
  section?: string;
  breadcrumb?: string;
  score?: number;
  source_url?: string;
  is_private_byod?: boolean;
}

export interface RagResultItem {
  ministry: string;
  detail_level: DetailLevel;
  reasoning_mode: string;
  answer: string;
  graph_context?: string;
  sources: RagSource[];
  first_token_ms?: number;
  byod_active?: boolean;
}

export interface RagAskResponse {
  question: string;
  ministry: string;
  results: RagResultItem[];
  error?: string;
}

export interface UserProfile {
  id: string;
  email: string;
  name: string;
  tier: 'free' | 'premium' | 'admin';
}

export interface ByodDoc {
  doc_id: string;
  title: string;
  filename: string;
  words?: number;
  chars?: number;
  uploaded_at?: number;
}
