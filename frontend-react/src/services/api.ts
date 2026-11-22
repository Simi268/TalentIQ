const API_BASE = 'https://talentiq-6r91.onrender.com/api';

async function request<T>(
  endpoint: string,
  options: RequestInit = {}
): Promise<T> {
  const response = await fetch(`${API_BASE}${endpoint}`, options);

  const data = await response.json().catch(() => ({}));

  if (!response.ok) {
    throw new Error(data.detail || 'API request failed');
  }

  return data as T;
}

export const api = {
  getJobs: () =>
    request<any[]>('/jobs'),

  getJob: (id: number | string) =>
    request<any>(`/jobs/${id}`),

  getCandidates: (jobId: number | string) =>
    request<any[]>(`/matching/results/${jobId}`),

  createJob: (title: string, description: string) =>
    request<any>('/jobs', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ title, description }),
    }),

  compareCandidates: (candidateIds: number[]) =>
    request<any>('/candidates/compare', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ candidate_ids: candidateIds }),
    }),

  recalculate: (jobId: number | string) =>
    request<any>(`/jobs/${jobId}/recalculate`, {
      method: 'POST',
    }),
};