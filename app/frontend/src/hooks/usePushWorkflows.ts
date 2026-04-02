export type PushErrorKind = 'generic' | 'auth_expired' | 'repo_deleted' | 'no_commits'

/**
 * Call /api/remote/push for one provider and normalise the error into a
 * PushErrorKind so callers never have to inspect raw error strings.
 *
 * Throws a PushErrorKind string on failure so Promise.allSettled callers
 * can inspect reason without parsing error messages themselves.
 */
export async function pushWorkflows(
  projectId: string,
  folder: string,
  provider: 'github' | 'gitlab',
): Promise<{ repo_url: string; created: boolean }> {
  const res = await fetch('/api/remote/push', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ project_id: projectId, folder, provider }),
  })
  const data = await res.json()
  if (data.success) return data

  const err: string = data.error ?? ''
  if (err === 'no_commits') throw new Error('no_commits' satisfies PushErrorKind)
  if (err === 'repo_deleted') throw new Error('repo_deleted' satisfies PushErrorKind)
  if (err.toLowerCase().includes('auth') || err.includes('401'))
    throw new Error('auth_expired' satisfies PushErrorKind)
  throw new Error('generic' satisfies PushErrorKind)
}
