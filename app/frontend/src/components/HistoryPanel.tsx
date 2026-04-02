import { useState, useEffect } from 'react'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Textarea } from '@/components/ui/textarea'
import { Cloud } from 'lucide-react'
import { cn } from '@/lib/utils'
import { BranchChip } from '@/components/BranchChip'
import { pushWorkflows } from '@/hooks/usePushWorkflows'

function humanizeBranchName(branch: string): string {
  const withoutPrefix = branch.replace(/^experiment\/(\d{4}-\d{2}-\d{2}-)?/, '')
  const withSpaces = withoutPrefix.replace(/-/g, ' ')
  return withSpaces.charAt(0).toUpperCase() + withSpaces.slice(1)
}

type PRState = 'idle' | 'loading' | 'done' | 'error'

export interface CommitEntry {
  sha: string
  message: string
  author: string
  timestamp: string        // ISO-8601 string
  files_changed: string[]  // workflow file basenames
  has_parent: boolean
  is_pushed: boolean
}

interface RemoteStatus {
  ahead: number
  behind: number
  github_connected: boolean
  gitlab_connected: boolean
  repo_url: string | null
}

interface HistoryPanelProps {
  entries: CommitEntry[]
  projectId: string
  projectPath: string
  onSelectEntry: (entry: CommitEntry, file: string) => void
  onUndo: () => void
  lastPushTimestamp?: number
  onNavigate?: (view: 'remote') => void
  onPushComplete?: () => void
  onBranchSwitch?: () => void
  activeBranch?: string
  allBranchEntries?: CommitEntry[]
}

function formatRelativeTime(isoTimestamp: string): string {
  const diffMs = Date.now() - new Date(isoTimestamp).getTime()
  const diffSec = Math.floor(diffMs / 1000)
  if (diffSec < 60) return 'just now'
  const diffMin = Math.floor(diffSec / 60)
  if (diffMin < 60) return `${diffMin} min ago`
  const diffHours = Math.floor(diffMin / 60)
  if (diffHours < 24) return `${diffHours} hour${diffHours !== 1 ? 's' : ''} ago`
  return new Date(isoTimestamp).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
}

function buildTooltip(remoteStatus: RemoteStatus | null): string {
  if (!remoteStatus) return 'Backed up'
  const remotes: string[] = []
  if (remoteStatus.github_connected) remotes.push('GitHub')
  if (remoteStatus.gitlab_connected) remotes.push('GitLab')
  if (remotes.length === 0) return 'Backed up'
  return `Backed up to ${remotes.join(' · ')}`
}

function EntryRow({
  entry,
  isLatest,
  onSelectEntry,
  remoteConnected,
  remoteStatus,
}: {
  entry: CommitEntry
  isLatest: boolean
  onSelectEntry: (entry: CommitEntry, file: string) => void
  remoteConnected: boolean
  remoteStatus: RemoteStatus | null
}) {
  const [selectedFile, setSelectedFile] = useState<string | null>(null)
  const fileCount = entry.files_changed.length

  function handleRowClick() {
    if (fileCount === 0) {
      onSelectEntry(entry, '')
    } else if (fileCount === 1) {
      onSelectEntry(entry, entry.files_changed[0])
    }
    // For multiple files: selection is handled by inline file selector
  }

  function handleTabClick(file: string, e: React.MouseEvent) {
    e.stopPropagation()
    setSelectedFile(file)
    onSelectEntry(entry, file)
  }

  function handleSelectChange(e: React.ChangeEvent<HTMLSelectElement>) {
    e.stopPropagation()
    const file = e.target.value
    setSelectedFile(file)
    onSelectEntry(entry, file)
  }

  const truncatedMessage =
    entry.message.length > 60
      ? entry.message.slice(0, 60) + '…'
      : entry.message

  return (
    <div
      className={cn(
        'rounded-md px-3 py-2 cursor-pointer hover:bg-muted/60 transition-colors',
        fileCount <= 1 ? '' : 'cursor-default'
      )}
      onClick={fileCount <= 1 ? handleRowClick : undefined}
      role={fileCount <= 1 ? 'button' : undefined}
      tabIndex={fileCount <= 1 ? 0 : undefined}
      onKeyDown={
        fileCount <= 1
          ? (e) => {
              if (e.key === 'Enter' || e.key === ' ') handleRowClick()
            }
          : undefined
      }
    >
      <div className="flex items-start justify-between gap-2">
        <div className="flex-1 min-w-0">
          <p className="text-sm font-medium truncate">{truncatedMessage}</p>
          <p className="text-xs text-muted-foreground mt-0.5">
            {entry.author} · {formatRelativeTime(entry.timestamp)}
          </p>
        </div>
        <div className="flex items-center gap-1.5 shrink-0 mt-0.5">
          {remoteConnected && entry.is_pushed && (
            <span
              title={buildTooltip(remoteStatus)}
              aria-label="Backed up to remote"
            >
              <Cloud className="h-3.5 w-3.5 text-blue-500" />
            </span>
          )}
          {isLatest && (
            <Badge variant="secondary">
              Latest
            </Badge>
          )}
        </div>
      </div>

      {/* Inline file selector for 2-4 files */}
      {fileCount >= 2 && fileCount <= 4 && (
        <div className="flex flex-wrap gap-1 mt-2">
          {entry.files_changed.map((file) => (
            <button
              key={file}
              onClick={(e) => handleTabClick(file, e)}
              className={cn(
                'text-xs px-2 py-1 rounded-md border transition-colors',
                selectedFile === file
                  ? 'bg-primary text-primary-foreground border-primary'
                  : 'bg-background hover:bg-muted border-input'
              )}
            >
              {file}
            </button>
          ))}
        </div>
      )}

      {/* Native select for 5+ files */}
      {fileCount >= 5 && (
        <div className="mt-2" onClick={(e) => e.stopPropagation()}>
          <select
            value={selectedFile ?? ''}
            onChange={handleSelectChange}
            className="w-full text-xs rounded-md border border-input bg-background px-2 py-1.5 text-foreground focus:outline-none focus:ring-2 focus:ring-ring"
          >
            <option value="" disabled>
              Select a file…
            </option>
            {entry.files_changed.map((file) => (
              <option key={file} value={file}>
                {file}
              </option>
            ))}
          </select>
        </div>
      )}
    </div>
  )
}

interface GraphViewProps {
  entries: CommitEntry[]
  onSelectEntry: (entry: CommitEntry, file: string) => void
  remoteConnected: boolean
  remoteStatus: RemoteStatus | null
  activeBranch?: string
  allBranchEntries?: CommitEntry[]
}

const NODE_R = 8
const NODE_SPACING = 48
const SVG_COL_WIDTH = 36

function GraphView({ entries, onSelectEntry, remoteConnected, remoteStatus, activeBranch, allBranchEntries }: GraphViewProps) {
  if (entries.length === 0) {
    return (
      <p className="text-sm text-muted-foreground text-center py-8">
        No saved versions yet.
      </p>
    )
  }

  // Multi-branch mode: on experiment branch AND there are experiment-unique commits
  const mainShaSet = new Set((allBranchEntries ?? []).map(e => e.sha))
  const expUniqueEntries = entries.filter(e => !mainShaSet.has(e.sha))
  const isMultiBranch = activeBranch?.startsWith('experiment/') &&
    allBranchEntries && allBranchEntries.length > 0 && expUniqueEntries.length > 0

  if (isMultiBranch && allBranchEntries) {
    // Combined timeline: merge main + exp-unique, sorted newest first
    const combined = [...allBranchEntries, ...expUniqueEntries]
      .sort((a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime())
    const rowIndex = new Map(combined.map((e, i) => [e.sha, i]))
    const expUniqueShaSet = new Set(expUniqueEntries.map(e => e.sha))

    const totalRows = combined.length
    const svgWidth = SVG_COL_WIDTH * 2
    const svgHeight = NODE_R + totalRows * NODE_SPACING

    const mainColX = SVG_COL_WIDTH / 2   // 18
    const expColX = SVG_COL_WIDTH * 1.5  // 54

    // Branch connector: from newest main commit → oldest experiment-unique commit
    const newestMain = allBranchEntries[0]
    const oldestExpUnique = expUniqueEntries[expUniqueEntries.length - 1]
    const newestMainRow = rowIndex.get(newestMain?.sha ?? '') ?? 0
    const oldestExpRow = rowIndex.get(oldestExpUnique?.sha ?? '') ?? 0

    return (
      <div className="flex-1 overflow-y-auto p-3 flex flex-col gap-0">
        <div className="relative" style={{ height: svgHeight }}>
          <svg
            width={svgWidth}
            height={svgHeight}
            className="absolute top-0 left-0 shrink-0"
            aria-hidden="true"
          >
            {/* Main vertical line */}
            {allBranchEntries.length > 1 && (
              <line
                x1={mainColX}
                y1={NODE_R + (rowIndex.get(allBranchEntries[0].sha) ?? 0) * NODE_SPACING}
                x2={mainColX}
                y2={NODE_R + (rowIndex.get(allBranchEntries[allBranchEntries.length - 1].sha) ?? 0) * NODE_SPACING}
                stroke="currentColor"
                strokeWidth={2}
                className="text-border"
              />
            )}
            {/* Experiment vertical line */}
            {expUniqueEntries.length > 1 && (
              <line
                x1={expColX}
                y1={NODE_R + (rowIndex.get(expUniqueEntries[0].sha) ?? 0) * NODE_SPACING}
                x2={expColX}
                y2={NODE_R + oldestExpRow * NODE_SPACING}
                stroke="#f59e0b"
                strokeWidth={2}
              />
            )}
            {/* Branch connector: diagonal from newest main to oldest exp-unique */}
            {newestMain && oldestExpUnique && (
              <line
                x1={mainColX}
                y1={NODE_R + newestMainRow * NODE_SPACING}
                x2={expColX}
                y2={NODE_R + oldestExpRow * NODE_SPACING}
                stroke="#f59e0b"
                strokeWidth={2}
              />
            )}
            {/* Main column nodes */}
            {allBranchEntries.map((entry) => {
              const cy = NODE_R + (rowIndex.get(entry.sha) ?? 0) * NODE_SPACING
              const isPushedNode = remoteConnected && entry.is_pushed
              return (
                <g key={entry.sha} onClick={() => onSelectEntry(entry, entry.files_changed[0] ?? '')} className="cursor-pointer group" role="button" aria-label={entry.message} tabIndex={0} onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') onSelectEntry(entry, entry.files_changed[0] ?? '') }}>
                  {isPushedNode ? (
                    <><circle cx={mainColX} cy={cy} r={NODE_R} fill="#3b82f6" className="group-hover:opacity-80 transition-opacity" /><circle cx={mainColX} cy={cy} r={NODE_R - 3.5} fill="white" /></>
                  ) : (
                    <circle cx={mainColX} cy={cy} r={NODE_R} fill="hsl(var(--muted-foreground))" className="group-hover:opacity-80 transition-opacity" />
                  )}
                </g>
              )
            })}
            {/* Experiment column nodes (amber) */}
            {expUniqueEntries.map((entry) => {
              const cy = NODE_R + (rowIndex.get(entry.sha) ?? 0) * NODE_SPACING
              return (
                <g key={entry.sha} onClick={() => onSelectEntry(entry, entry.files_changed[0] ?? '')} className="cursor-pointer group" role="button" aria-label={entry.message} tabIndex={0} onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') onSelectEntry(entry, entry.files_changed[0] ?? '') }}>
                  <circle cx={expColX} cy={cy} r={NODE_R} fill="#f59e0b" className="group-hover:opacity-80 transition-opacity" />
                </g>
              )
            })}
          </svg>

          {/* Commit info rows — right of SVG */}
          <div className="absolute top-0 right-0 flex flex-col" style={{ left: svgWidth + 8 }}>
            {combined.map((entry, rowIdx) => {
              const isExp = expUniqueShaSet.has(entry.sha)
              const truncated = entry.message.length > 46 ? entry.message.slice(0, 46) + '…' : entry.message
              const isPushed = remoteConnected && entry.is_pushed
              return (
                <div key={entry.sha} className="flex flex-col justify-center cursor-pointer hover:bg-muted/50 rounded px-1 py-0.5 transition-colors" style={{ height: NODE_SPACING }} onClick={() => onSelectEntry(entry, entry.files_changed[0] ?? '')} role="button" tabIndex={0} onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') onSelectEntry(entry, entry.files_changed[0] ?? '') }} aria-label={entry.message}>
                  <div className="flex items-center gap-1">
                    <p className={cn('text-xs font-medium truncate', rowIdx === 0 && 'text-foreground', isExp && 'text-amber-700')}>
                      {truncated}
                    </p>
                    {rowIdx === 0 && <span className="text-[10px] font-semibold px-1 py-0.5 rounded bg-muted text-muted-foreground shrink-0">latest</span>}
                    {isPushed && <span title={buildTooltip(remoteStatus)}><Cloud className="h-3 w-3 text-blue-500 shrink-0" /></span>}
                  </div>
                  <p className="text-xs text-muted-foreground">{formatRelativeTime(entry.timestamp)}</p>
                </div>
              )
            })}
          </div>
        </div>
      </div>
    )
  }

  // Single-branch path (unchanged from Phase 16.1)
  const svgHeight = NODE_R + entries.length * NODE_SPACING

  return (
    <div className="flex-1 overflow-y-auto p-3 flex flex-col gap-0">
      <div className="relative" style={{ height: svgHeight }}>
        {/* SVG track — left column */}
        <svg
          width={SVG_COL_WIDTH}
          height={svgHeight}
          className="absolute top-0 left-0 shrink-0"
          aria-hidden="true"
        >
          {/* Vertical connecting line */}
          {entries.length > 1 && (
            <line
              x1={SVG_COL_WIDTH / 2}
              y1={NODE_R}
              x2={SVG_COL_WIDTH / 2}
              y2={svgHeight - NODE_R}
              stroke="currentColor"
              strokeWidth={2}
              className="text-border"
            />
          )}
          {entries.map((entry, i) => {
            const cy = NODE_R + i * NODE_SPACING
            const isPushedNode = remoteConnected && entry.is_pushed
            return (
              <g
                key={entry.sha}
                onClick={() => onSelectEntry(entry, entry.files_changed[0] ?? '')}
                className="cursor-pointer group"
                role="button"
                aria-label={entry.message}
                tabIndex={0}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' || e.key === ' ') {
                    onSelectEntry(entry, entry.files_changed[0] ?? '')
                  }
                }}
              >
                {isPushedNode ? (
                  <>
                    {/* Blue ring for pushed commits */}
                    <circle
                      cx={SVG_COL_WIDTH / 2}
                      cy={cy}
                      r={NODE_R}
                      fill="#3b82f6"
                      className="group-hover:opacity-80 transition-opacity"
                    />
                    <circle
                      cx={SVG_COL_WIDTH / 2}
                      cy={cy}
                      r={NODE_R - 3.5}
                      fill="white"
                    />
                  </>
                ) : (
                  <circle
                    cx={SVG_COL_WIDTH / 2}
                    cy={cy}
                    r={NODE_R}
                    fill="hsl(var(--muted-foreground))"
                    className="group-hover:opacity-80 transition-opacity"
                  />
                )}
              </g>
            )
          })}
        </svg>

        {/* Commit info rows — right of SVG column */}
        <div
          className="absolute top-0 right-0 flex flex-col"
          style={{ left: SVG_COL_WIDTH + 8 }}
        >
          {entries.map((entry, i) => {
            const truncated = entry.message.length > 50
              ? entry.message.slice(0, 50) + '…'
              : entry.message
            const isPushed = remoteConnected && entry.is_pushed
            return (
              <div
                key={entry.sha}
                className="flex flex-col justify-center cursor-pointer hover:bg-muted/50 rounded px-1 py-0.5 transition-colors"
                style={{ height: NODE_SPACING }}
                onClick={() => onSelectEntry(entry, entry.files_changed[0] ?? '')}
                role="button"
                tabIndex={0}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' || e.key === ' ') {
                    onSelectEntry(entry, entry.files_changed[0] ?? '')
                  }
                }}
                aria-label={entry.message}
              >
                <div className="flex items-center gap-1">
                  <p className={cn('text-xs font-medium truncate', i === 0 && 'text-foreground')}>
                    {truncated}
                  </p>
                  {i === 0 && (
                    <span className="text-[10px] font-semibold px-1 py-0.5 rounded bg-muted text-muted-foreground shrink-0">
                      latest
                    </span>
                  )}
                  {isPushed && (
                    <span title={buildTooltip(remoteStatus)}>
                      <Cloud className="h-3 w-3 text-blue-500 shrink-0" />
                    </span>
                  )}
                </div>
                <p className="text-xs text-muted-foreground">
                  {formatRelativeTime(entry.timestamp)}
                </p>
              </div>
            )
          })}
        </div>
      </div>
    </div>
  )
}

interface BehindCommit {
  sha: string
  short_sha: string
  message: string
  author: string
  timestamp: string
}

export function HistoryPanel({
  entries,
  projectId,
  projectPath,
  onSelectEntry,
  onUndo,
  lastPushTimestamp,
  onNavigate,
  onPushComplete,
  onBranchSwitch,
  activeBranch,
  allBranchEntries,
}: HistoryPanelProps) {
  const [remoteStatus, setRemoteStatus] = useState<RemoteStatus | null>(null)
  const [pushState, setPushState] = useState<'idle' | 'pushing' | 'error'>('idle')
  const [pushError, setPushError] = useState<string | null>(null)
  const [behindCommits, setBehindCommits] = useState<BehindCommit[]>([])
  const [behindExpanded, setBehindExpanded] = useState(false)
  const [viewMode, setViewMode] = useState<'list' | 'graph'>(() => {
    try {
      return (localStorage.getItem('history_view_mode') as 'list' | 'graph') ?? 'list'
    } catch {
      return 'list'
    }
  })

  // PR state
  const [prState, setPrState] = useState<PRState>('idle')
  const [prUrl, setPrUrl] = useState<string | null>(null)
  const [prError, setPrError] = useState<string | null>(null)
  const [showPRForm, setShowPRForm] = useState(false)
  const [prTitle, setPrTitle] = useState('')
  const [prDescription, setPrDescription] = useState('')

  function handleToggle(mode: 'list' | 'graph') {
    setViewMode(mode)
    try {
      localStorage.setItem('history_view_mode', mode)
    } catch { /* ignore */ }
  }

  async function fetchRemoteStatus({ fast = false }: { fast?: boolean } = {}) {
    if (!projectId || !projectPath) return
    try {
      const res = await fetch(
        `/api/remote/status?project_id=${encodeURIComponent(projectId)}&folder=${encodeURIComponent(projectPath)}${fast ? '&fast=true' : ''}`
      )
      if (!res.ok) return
      const data: RemoteStatus = await res.json()
      setRemoteStatus(data)
      if (data.behind > 0) {
        fetchBehindCommits()
      } else {
        setBehindCommits([])
        setBehindExpanded(false)
      }
    } catch { /* ignore */ }
  }

  async function fetchBehindCommits() {
    if (!projectPath) return
    try {
      const res = await fetch(
        `/api/remote/behind-commits?folder=${encodeURIComponent(projectPath)}`
      )
      if (!res.ok) return
      setBehindCommits(await res.json())
    } catch { /* ignore */ }
  }

  useEffect(() => {
    if (!projectId) return
    fetchRemoteStatus({ fast: true })  // immediate: show cached counts
    fetchRemoteStatus()                // background: fetch from remote for fresh counts

    // Local refresh every 10s — reads local remote-tracking refs, no network
    const localTimer = setInterval(() => fetchRemoteStatus({ fast: true }), 10_000)
    // Remote fetch every 3 min — actual git fetch, matches VS Code's autofetch default
    const remoteTimer = setInterval(() => fetchRemoteStatus(), 3 * 60 * 1000)

    return () => {
      clearInterval(localTimer)
      clearInterval(remoteTimer)
    }
  }, [projectId]) // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (!lastPushTimestamp) return
    fetchRemoteStatus()
  }, [lastPushTimestamp]) // eslint-disable-line react-hooks/exhaustive-deps

  async function handlePush() {
    if (!projectId || !projectPath || !remoteStatus) return
    // If not connected: navigate to remote panel
    if (!remoteStatus.github_connected && !remoteStatus.gitlab_connected) {
      onNavigate?.('remote')
      return
    }
    setPushState('pushing')
    setPushError(null)
    const providers: Array<'github' | 'gitlab'> = []
    if (remoteStatus.github_connected) providers.push('github')
    if (remoteStatus.gitlab_connected) providers.push('gitlab')
    const results = await Promise.allSettled(
      providers.map((provider) => pushWorkflows(projectId, projectPath, provider))
    )
    const anySucceeded = results.some((r) => r.status === 'fulfilled')
    const failed = providers.filter((_, i) => results[i].status === 'rejected')
    if (anySucceeded) {
      setPushState('idle')
      await fetchRemoteStatus()
      onPushComplete?.()
    } else {
      setPushState('error')
    }
    if (failed.length > 0) {
      const names = failed.map((p) => p === 'github' ? 'GitHub' : 'GitLab').join(' and ')
      const isNoCommits = results
        .filter((r) => r.status === 'rejected')
        .some((r) => (r as PromiseRejectedResult).reason?.message === 'no_commits')
      if (isNoCommits) {
        setPushError('Save your workflow first before pushing to GitHub/GitLab.')
      } else {
        setPushError(`${names} backup failed. Check your connection and try again.`)
      }
      setTimeout(() => { setPushState('idle'); setPushError(null) }, 5000)
    }
  }

  const remoteConnected = !!(remoteStatus?.github_connected || remoteStatus?.gitlab_connected)
  const aheadCount = remoteStatus?.ahead ?? 0
  const behindCount = remoteStatus?.behind ?? 0
  const isExperiment = activeBranch?.startsWith('experiment/')

  async function fetchPRStatus() {
    if (!projectId || !projectPath || !isExperiment) return
    const providers: Array<'github' | 'gitlab'> = []
    if (remoteStatus?.github_connected) providers.push('github')
    if (remoteStatus?.gitlab_connected) providers.push('gitlab')
    for (const provider of providers) {
      try {
        const params = new URLSearchParams({ folder: projectPath, project_id: projectId, provider, branch: activeBranch! })
        const res = await fetch(`/api/remote/pr/status?${params}`)
        const data = await res.json()
        if (data.pr_exists && data.pr_url) {
          setPrUrl(data.pr_url)
          setPrState('done')
          return
        }
      } catch { /* silent */ }
    }
  }

  async function handleCreatePR() {
    if (!projectId || !projectPath || prTitle.trim() === '') return
    const providers: Array<'github' | 'gitlab'> = []
    if (remoteStatus?.github_connected) providers.push('github')
    if (remoteStatus?.gitlab_connected) providers.push('gitlab')
    if (providers.length === 0) return
    setPrState('loading')
    setPrError(null)
    for (const provider of providers) {
      try {
        const res = await fetch('/api/remote/pr/create', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ project_id: projectId, folder: projectPath, provider, title: prTitle, description: prDescription, branch: activeBranch }),
        })
        const data = await res.json()
        if (data.pr_url) {
          setPrUrl(data.pr_url)
          setPrState('done')
          setShowPRForm(false)
          return
        }
        if (data.error) setPrError(data.error)
      } catch { /* try next provider */ }
    }
    setPrState('error')
  }

  useEffect(() => {
    if (remoteConnected && isExperiment) fetchPRStatus()
  }, [projectId, activeBranch, remoteConnected]) // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    setPrState('idle')
    setPrUrl(null)
    setPrError(null)
    setShowPRForm(false)
    setPrTitle('')
    setPrDescription('')
  }, [projectId, activeBranch])

  async function handlePull() {
    if (!projectId || !projectPath || !remoteStatus) return
    const providers: Array<'github' | 'gitlab'> = []
    if (remoteStatus.github_connected) providers.push('github')
    if (remoteStatus.gitlab_connected) providers.push('gitlab')
    if (providers.length === 0) return
    setPushState('pushing')
    setPushError(null)
    try {
      const res = await fetch('/api/remote/pull', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ project_id: projectId, folder: projectPath, provider: providers[0] }),
      })
      const data = await res.json()
      if (data.success) {
        await fetchRemoteStatus()
        onPushComplete?.()
      } else {
        setPushState('error')
        setPushError(data.error ?? 'Pull failed')
        setTimeout(() => { setPushState('idle'); setPushError(null) }, 5000)
        return
      }
    } catch {
      setPushState('error')
    }
    setPushState('idle')
  }

  return (
    <div className="flex flex-col h-full overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b shrink-0">
        <div className="flex items-center gap-2">
          <h2 className="text-sm font-semibold">Saved Versions</h2>
          {onBranchSwitch && (
            <div className="flex flex-col">
              <BranchChip
                projectId={projectId}
                projectPath={projectPath}
                onBranchSwitch={onBranchSwitch}
              />
              {remoteConnected && (
                <div className="mt-0.5 flex items-center gap-1.5">
                  <span className={`text-xs ${aheadCount > 0 ? 'text-foreground font-medium' : 'text-muted-foreground'}`}>
                    ↑ {aheadCount} ahead
                  </span>
                  <span className="text-xs text-muted-foreground">·</span>
                  {behindCount > 0 ? (
                    <button
                      className="text-xs text-amber-600 hover:text-amber-700 transition-colors flex items-center gap-0.5"
                      onClick={() => setBehindExpanded((v) => !v)}
                      title="Show remote commits not yet pulled"
                    >
                      ↓ {behindCount} behind
                      <span className="text-[10px]">{behindExpanded ? '▲' : '▼'}</span>
                    </button>
                  ) : (
                    <span className="text-xs text-muted-foreground">↓ 0 behind</span>
                  )}
                </div>
              )}
            </div>
          )}
        </div>
        <div className="flex items-center gap-2">
          <div className="flex items-center gap-1 bg-muted rounded-md p-0.5">
            <button
              onClick={() => handleToggle('list')}
              className={cn(
                'px-2 py-0.5 rounded text-xs font-medium transition-colors',
                viewMode === 'list'
                  ? 'bg-background text-foreground shadow-sm'
                  : 'text-muted-foreground hover:text-foreground'
              )}
              aria-pressed={viewMode === 'list'}
            >
              &#8801; List
            </button>
            <button
              onClick={() => handleToggle('graph')}
              className={cn(
                'px-2 py-0.5 rounded text-xs font-medium transition-colors',
                viewMode === 'graph'
                  ? 'bg-background text-foreground shadow-sm'
                  : 'text-muted-foreground hover:text-foreground'
              )}
              aria-pressed={viewMode === 'graph'}
            >
              &#9638; Graph
            </button>
          </div>
          {remoteConnected && remoteStatus?.repo_url && (
            <Button
              variant="outline"
              size="sm"
              onClick={handlePull}
              disabled={pushState === 'pushing'}
              className="shrink-0"
            >
              {pushState === 'pushing'
                ? 'Pulling...'
                : behindCount > 0
                ? `↓ Pull ${behindCount} version${behindCount !== 1 ? 's' : ''}`
                : '↓ Pull'}
            </Button>
          )}
          {remoteConnected && aheadCount > 0 && (
            <Button
              variant="default"
              size="sm"
              onClick={handlePush}
              disabled={pushState === 'pushing'}
              className="shrink-0"
            >
              {pushState === 'pushing' ? 'Backing up...' : `↑ Back up ${aheadCount} version${aheadCount !== 1 ? 's' : ''}`}
            </Button>
          )}
          {remoteConnected && aheadCount === 0 && activeBranch?.startsWith('experiment/') && entries.length > 0 && !entries[0].is_pushed && (
            <Button
              variant="default"
              size="sm"
              onClick={handlePush}
              disabled={pushState === 'pushing'}
              className="shrink-0"
            >
              {pushState === 'pushing' ? 'Publishing...' : '↑ Publish branch'}
            </Button>
          )}
          {remoteConnected && isExperiment && entries.length > 0 && entries[0].is_pushed && (
            prState === 'done' && prUrl ? (
              <a
                href={prUrl}
                target="_blank"
                rel="noopener noreferrer"
                className="text-xs text-blue-500 underline underline-offset-2 hover:text-blue-600 transition-colors shrink-0"
              >
                View PR →
              </a>
            ) : (
              <Button
                variant="outline"
                size="sm"
                className="shrink-0"
                onClick={() => {
                  setShowPRForm((v) => !v)
                  if (!showPRForm && prTitle === '') setPrTitle(humanizeBranchName(activeBranch!))
                }}
              >
                Open PR
              </Button>
            )
          )}
          {entries.length > 0 && (
            <Button variant="outline" size="sm" onClick={onUndo}>
              Undo last save
            </Button>
          )}
        </div>
      </div>

      {/* Behind commits detail panel */}
      {behindExpanded && behindCount > 0 && (
        <div className="border-b bg-amber-50/50 dark:bg-amber-950/20 px-4 py-2 space-y-1">
          <p className="text-xs font-medium text-amber-700 dark:text-amber-400 mb-1.5">
            {behindCount} remote version{behindCount !== 1 ? 's' : ''} not yet pulled:
          </p>
          {behindCommits.length > 0 ? (
            behindCommits.map((c) => (
              <div key={c.sha} className="flex items-start gap-2">
                <code className="text-[10px] text-muted-foreground font-mono shrink-0 mt-0.5">{c.short_sha}</code>
                <div className="min-w-0">
                  <p className="text-xs truncate">{c.message}</p>
                  <p className="text-[10px] text-muted-foreground">{c.author} · {formatRelativeTime(c.timestamp)}</p>
                </div>
              </div>
            ))
          ) : (
            <p className="text-xs text-muted-foreground">Loading...</p>
          )}
        </div>
      )}

      {pushError && (
        <p className="text-xs text-red-500 px-4 pb-1">{pushError}</p>
      )}

      {/* Inline PR form */}
      {showPRForm && prState !== 'done' && (
        <div className="border-b px-4 py-3 space-y-2 shrink-0">
          <input
            type="text"
            placeholder="PR title"
            value={prTitle}
            onChange={(e) => setPrTitle(e.target.value)}
            className="w-full rounded-md border bg-background px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
          />
          <Textarea
            placeholder="Description (optional)"
            value={prDescription}
            onChange={(e) => setPrDescription(e.target.value)}
            className="text-sm"
            rows={2}
          />
          {prState === 'error' && (
            <p className="text-xs text-red-500">{prError ?? 'Failed to create PR. Please try again.'}</p>
          )}
          <div className="flex gap-2">
            <Button size="sm" onClick={handleCreatePR} disabled={prTitle.trim() === '' || prState === 'loading'}>
              {prState === 'loading' ? 'Creating...' : 'Create PR'}
            </Button>
            <Button size="sm" variant="ghost" onClick={() => { setShowPRForm(false); setPrTitle(''); setPrDescription('') }}>
              Cancel
            </Button>
          </div>
        </div>
      )}

      {/* Scrollable entry list or graph */}
      {viewMode === 'list' ? (
        <div className="flex-1 overflow-y-auto p-2 flex flex-col gap-0.5">
          {entries.length === 0 ? (
            <p className="text-sm text-muted-foreground text-center py-8">
              No saved versions yet.
            </p>
          ) : (
            entries.map((entry, index) => (
              <EntryRow
                key={entry.sha}
                entry={entry}
                isLatest={index === 0}
                onSelectEntry={onSelectEntry}
                remoteConnected={remoteConnected}
                remoteStatus={remoteStatus}
              />
            ))
          )}
        </div>
      ) : (
        <GraphView
          entries={entries}
          onSelectEntry={onSelectEntry}
          remoteConnected={remoteConnected}
          remoteStatus={remoteStatus}
          activeBranch={activeBranch}
          allBranchEntries={allBranchEntries}
        />
      )}
    </div>
  )
}
