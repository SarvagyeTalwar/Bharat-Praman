// frontend/src/lib/api.ts
// Typed API client for FastAPI backend with automated token handling

import type { RagAskRequest, RagAskResponse, UserProfile, ByodDoc } from './types';

const API_BASE = import.meta.env.VITE_API_BASE || '';

export function getAuthToken(): string {
  return localStorage.getItem('bp_auth_token') || '';
}

export function setAuthToken(token: string) {
  if (token) {
    localStorage.setItem('bp_auth_token', token);
  } else {
    localStorage.removeItem('bp_auth_token');
  }
}

export async function askIntelligence(req: RagAskRequest): Promise<RagAskResponse> {
  const token = getAuthToken();
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
  };
  if (token) headers['Authorization'] = `Bearer ${token}`;

  const res = await fetch(`${API_BASE}/api/rag/ask`, {
    method: 'POST',
    headers,
    body: JSON.stringify({ ...req, auth_token: token || undefined }),
  });

  const data = await res.json();
  if (!res.ok) {
    throw new Error(data.detail || data.error || `HTTP ${res.status}`);
  }
  return data;
}

export async function streamIntelligence(
  req: RagAskRequest,
  onMeta: (meta: any) => void,
  onDelta: (text: string) => void,
  onReasoning?: (text: string) => void
): Promise<string> {
  const token = getAuthToken();
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    'Accept': 'text/event-stream',
  };
  if (token) headers['Authorization'] = `Bearer ${token}`;

  const res = await fetch(`${API_BASE}/api/rag/ask/stream`, {
    method: 'POST',
    headers,
    body: JSON.stringify({ ...req, auth_token: token || undefined }),
  });

  if (!res.ok || !res.body) {
    throw new Error(`Stream connection failed: HTTP ${res.status}`);
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let accumulated = '';
  let buf = '';

  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buf += decoder.decode(value, { stream: true });

    let idx;
    while ((idx = buf.indexOf('\n\n')) !== -1) {
      const frame = buf.slice(0, idx);
      buf = buf.slice(idx + 2);
      const line = frame.split('\n').find((l) => l.startsWith('data:'));
      if (!line) continue;
      try {
        const ev = JSON.parse(line.slice(5).trim());
        if (ev.type === 'meta') {
          onMeta(ev);
        } else if (ev.type === 'content' && ev.delta) {
          accumulated += ev.delta;
          onDelta(ev.delta);
        } else if (ev.type === 'reasoning' && ev.delta && onReasoning) {
          onReasoning(ev.delta);
        } else if (ev.type === 'done' && ev.answer) {
          if (!accumulated) {
            // If the query was served from cache, stream the tokens quickly for visual continuity
            accumulated = ev.answer;
            const words = ev.answer.split(' ');
            for (let i = 0; i < words.length; i++) {
              const piece = (i === 0 ? '' : ' ') + words[i];
              onDelta(piece);
              if (i % 3 === 0) {
                await new Promise((r) => setTimeout(r, 12));
              }
            }
          }
        }
      } catch {}
    }
  }

  return accumulated;
}

export async function getCurrentUser(): Promise<UserProfile | null> {
  const token = getAuthToken();
  if (!token) return null;
  try {
    const res = await fetch(`${API_BASE}/api/auth/me`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    if (!res.ok) {
      setAuthToken('');
      return null;
    }
    const data = await res.json();
    return data.user || null;
  } catch {
    return null;
  }
}

export async function loginUser(email: string, password: string) {
  const res = await fetch(`${API_BASE}/api/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password }),
  });
  const data = await res.json();
  if (!res.ok) throw new Error(data.detail || 'Login failed.');
  if (data.token) setAuthToken(data.token);
  return data;
}

export async function registerUser(email: string, password: string, name = '', promoCode = '') {
  const res = await fetch(`${API_BASE}/api/auth/register`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password, name, promo_code: promoCode || undefined }),
  });
  const data = await res.json();
  if (!res.ok) throw new Error(data.detail || 'Registration failed.');
  if (data.token) setAuthToken(data.token);
  return data;
}

export async function upgradeAccount(promoCode: string) {
  const token = getAuthToken();
  const res = await fetch(`${API_BASE}/api/auth/upgrade`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify({ promo_code: promoCode }),
  });
  const data = await res.json();
  if (!res.ok) throw new Error(data.detail || 'Upgrade failed.');
  return data;
}

export async function uploadByodDocument(file: File): Promise<ByodDoc> {
  const reader = new FileReader();
  const b64 = await new Promise<string>((resolve, reject) => {
    reader.onload = () => resolve((reader.result as string).split(',')[1]);
    reader.onerror = reject;
    reader.readAsDataURL(file);
  });

  const res = await fetch(`${API_BASE}/api/byod/upload`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ filename: file.name, content_base64: b64, title: file.name }),
  });
  const data = await res.json();
  if (!res.ok) throw new Error(data.detail || 'Upload failed');
  return data;
}

export async function uploadVaultDocument(file: File): Promise<ByodDoc> {
  const token = getAuthToken();
  const reader = new FileReader();
  const b64 = await new Promise<string>((resolve, reject) => {
    reader.onload = () => resolve((reader.result as string).split(',')[1]);
    reader.onerror = reject;
    reader.readAsDataURL(file);
  });

  const res = await fetch(`${API_BASE}/api/byod/vault/index`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify({ filename: file.name, content_base64: b64, title: file.name }),
  });
  const data = await res.json();
  if (!res.ok) throw new Error(data.detail || 'Neo4j Vault indexing failed');
  return data;
}

export async function getVaultDocs(): Promise<ByodDoc[]> {
  const token = getAuthToken();
  if (!token) return [];
  try {
    const res = await fetch(`${API_BASE}/api/byod/vault/docs`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    if (!res.ok) return [];
    return await res.json();
  } catch {
    return [];
  }
}
