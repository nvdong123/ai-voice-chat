const TOKEN_KEY = 'vr360_admin_token';

export function getToken(): string {
  return localStorage.getItem(TOKEN_KEY) ?? '';
}

export function saveToken(token: string): void {
  localStorage.setItem(TOKEN_KEY, token);
}

export function removeToken(): void {
  localStorage.removeItem(TOKEN_KEY);
}

// ─── Typed API error ──────────────────────────────────────────────────────────
export class ApiError extends Error {
  readonly status: number;
  constructor(message: string, status: number) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
  }
}

// ─── Base fetch wrapper ───────────────────────────────────────────────────────
async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(path, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      'X-Admin-Token': getToken(),
      ...(options?.headers ?? {}),
    },
  });

  const data = await res.json().catch(() => ({ error: res.statusText })) as Record<string, unknown>;

  if (!res.ok) {
    throw new ApiError(String(data['error'] ?? 'Lỗi không xác định'), res.status);
  }

  return data as T;
}

// ─── Admin API surface ────────────────────────────────────────────────────────
export const adminApi = {
  login: (password: string) =>
    request<{ token: string; message: string }>('/admin/login', {
      method: 'POST',
      body: JSON.stringify({ password }),
    }),

  me: () => request<{ ok: boolean }>('/admin/api/me'),

  logout: () =>
    request<{ ok: boolean }>('/admin/logout', { method: 'POST' }),

  getPrompt: () => request<{ prompt: string }>('/admin/prompt'),

  savePrompt: (prompt: string) =>
    request<{ message: string }>('/admin/prompt', {
      method: 'POST',
      body: JSON.stringify({ prompt }),
    }),

  getModels: () =>
    request<{ models: Array<{ name: string; displayName: string }> }>('/admin/models'),

  getConfig: () =>
    request<{ model: string; voice: string; availableVoices: string[]; prompt: string }>(
      '/admin/config'
    ),

  saveConfig: (model: string, voice: string) =>
    request<{ message: string }>('/admin/config', {
      method: 'POST',
      body: JSON.stringify({ model, voice }),
    }),

  // ─── Scenes ───────────────────────────────────────────────────────────────
  getScenes: () =>
    request<Scene[]>('/admin/scenes'),

  createScene: (scene: Omit<Scene, never>) =>
    request<Scene>('/admin/scenes', {
      method: 'POST',
      body: JSON.stringify(scene),
    }),

  updateScene: (id: string, scene: Partial<Scene>) =>
    request<Scene>(`/admin/scenes/${encodeURIComponent(id)}`, {
      method: 'PUT',
      body: JSON.stringify(scene),
    }),

  deleteScene: (id: string) =>
    request<{ ok: boolean }>(`/admin/scenes/${encodeURIComponent(id)}`, {
      method: 'DELETE',
    }),
};

// ─── Shared types ─────────────────────────────────────────────────────────────
export interface Scene {
  id: string;
  panoNodeId: string;
  name: string;
  desc?: string;
  thumbClass?: string;
}
