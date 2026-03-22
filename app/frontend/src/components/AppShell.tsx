import { useState, useEffect, useCallback } from 'react'
import { useProjectStore } from '@/store/useProjectStore'
import Sidebar from '@/components/Sidebar'
import EmptyState from '@/components/EmptyState'
import { GitIdentityCard } from '@/components/GitIdentityCard'
import { ChangesPanel } from '@/components/ChangesPanel'
import { HistoryPanel, type CommitEntry } from '@/components/HistoryPanel'
import { DiffViewer } from '@/components/DiffViewer'
import { SettingsPanel } from '@/components/SettingsPanel'
import { RemotePanel } from '@/components/RemotePanel'

interface AppShellProps {
  onAddFolder?: () => void
  showIdentityCard?: boolean
  onIdentitySaved?: () => void
}

export default function AppShell({ onAddFolder, showIdentityCard, onIdentitySaved }: AppShellProps) {
  const { projects, activeProjectId, activeBranch, setActiveBranch } = useProjectStore()
  const activeProjectChangedCount = projects.find((p) => p.id === activeProjectId)?.changedCount ?? 0
  const activeProject = projects.find((p) => p.id === activeProjectId)

  const [activeView, setActiveView] = useState<'default' | 'settings' | 'remote'>('default')
  const [lastPushTimestamp, setLastPushTimestamp] = useState(0)

  // Watch status state — fetched on project activation and after undo
  const [hasCommits, setHasCommits] = useState(false)
  const [changedFiles, setChangedFiles] = useState<string[]>([])
  const [, setTotalWorkflows] = useState(0)
  const [history, setHistory] = useState<CommitEntry[]>([])
  const [selectedDiff, setSelectedDiff] = useState<{ sha: string; file: string } | null>(null)
  const [mergeBaseSha, setMergeBaseSha] = useState<string | null>(null)
  const [allBranchEntries, setAllBranchEntries] = useState<CommitEntry[]>([])
  const [isProjectLoading, setIsProjectLoading] = useState(false)

  const fetchWatchStatus = useCallback(async (): Promise<string[]> => {
    if (!activeProject) return []
    try {
      const res = await fetch(
        `/api/watch/status?project_id=${activeProject.id}&folder=${encodeURIComponent(activeProject.path)}`
      )
      if (!res.ok) return []
      const data = await res.json()
      const files: string[] = data.changed_files ?? []
      setHasCommits(data.has_any_commits ?? false)
      setChangedFiles(files)
      setTotalWorkflows(data.total_workflows ?? 0)
      return files
    } catch {
      return []
    }
  }, [activeProject])

  const fetchHistory = useCallback(async () => {
    if (!activeProject) return
    const fetchingForProject = activeProject.id
    setAllBranchEntries([])
    try {
      // Read branch from store's latest state to avoid stale closure on initial load
      const currentBranch = useProjectStore.getState().activeBranch[activeProject.id] ?? null
      const branchParam = currentBranch ? `&branch=${encodeURIComponent(currentBranch)}` : ''
      const res = await fetch(
        `/api/history/${activeProject.id}?folder=${encodeURIComponent(activeProject.path)}${branchParam}`
      )
      if (!res.ok) return
      // Discard response if the user switched projects while the fetch was in-flight
      if (useProjectStore.getState().activeProjectId !== fetchingForProject) return
      const data: CommitEntry[] = await res.json()
      setHistory(data ?? [])
      setHasCommits((data ?? []).length > 0)
      // For experiment branches: fetch main branch history for multi-branch GraphView
      if (currentBranch?.startsWith('experiment/')) {
        try {
          let mainData: CommitEntry[] = []
          for (const base of ['main', 'master']) {
            const allRes = await fetch(
              `/api/history/${activeProject.id}?folder=${encodeURIComponent(activeProject.path)}&branch=${base}`
            )
            if (allRes.ok) {
              const d: CommitEntry[] = await allRes.json()
              if (d.length > 0) { mainData = d; break }
            }
          }
          if (useProjectStore.getState().activeProjectId === fetchingForProject) {
            setAllBranchEntries(mainData)
          }
        } catch { /* ignore */ }
      } else {
        setAllBranchEntries([])
      }
    } catch { /* ignore */ }
  }, [activeProject, activeBranch])

  const fetchBranch = useCallback(async () => {
    if (!activeProject) return
    const res = await fetch(`/api/branch/${activeProject.id}?folder=${encodeURIComponent(activeProject.path)}`)
    if (!res.ok) return
    const branches: { name: string; is_current: boolean }[] = await res.json()
    const current = branches.find((b) => b.is_current)
    if (current) {
      setActiveBranch(activeProject.id, current.name)
      // Fetch merge-base SHA for experiment branches (used by DiffViewer compare toggle)
      if (current.name.startsWith('experiment/')) {
        try {
          const mbRes = await fetch(
            `/api/branch/${activeProject.id}/merge-base?folder=${encodeURIComponent(activeProject.path)}&branch=${encodeURIComponent(current.name)}`
          )
          if (mbRes.ok) {
            const mbData = await mbRes.json()
            setMergeBaseSha(mbData.merge_base_sha ?? null)
          }
        } catch { /* ignore */ }
      } else {
        setMergeBaseSha(null)
      }
    } else {
      setMergeBaseSha(null)
    }
  }, [activeProject, setActiveBranch])

  // Fetch on project change
  useEffect(() => {
    setSelectedDiff(null)
    setActiveView('default')
    if (!activeProjectId) {
      setChangedFiles([])
      setHasCommits(false)
      setHistory([])
      setMergeBaseSha(null)
      setAllBranchEntries([])
      return
    }
    setIsProjectLoading(true)
    fetchBranch().then(() => Promise.all([fetchWatchStatus(), fetchHistory()])).finally(() => {
      setIsProjectLoading(false)
    })
  }, [activeProjectId]) // eslint-disable-line react-hooks/exhaustive-deps

  // Re-fetch history whenever the active branch changes for the current project
  const currentActiveBranch = activeBranch[activeProjectId ?? '']
  useEffect(() => {
    if (!activeProjectId || isProjectLoading) return
    fetchHistory()
  }, [currentActiveBranch]) // eslint-disable-line react-hooks/exhaustive-deps

  // Re-fetch watch status when the SSE badge_update fires for the active project
  useEffect(() => {
    if (!activeProjectId || isProjectLoading) return
    fetchWatchStatus()
  }, [activeProjectChangedCount]) // eslint-disable-line react-hooks/exhaustive-deps

  async function handleBranchSwitch() {
    await fetchBranch()
    // fetchHistory is triggered automatically by the currentActiveBranch effect above
  }

  async function handleSaved() {
    await fetchWatchStatus()
    await fetchHistory()
  }

  async function handleDiscarded() {
    await fetchWatchStatus()
  }

  async function handleUndo() {
    await fetchWatchStatus()
    await fetchHistory()
  }

  function renderMainContent() {
    if (activeView === 'remote') {
      return <RemotePanel onPushComplete={() => {
        setLastPushTimestamp(Date.now())
        fetchHistory()
      }} />
    }
    if (activeView === 'settings') {
      return <SettingsPanel />
    }
    if (showIdentityCard && onIdentitySaved) {
      return (
        <div className="flex h-full items-center justify-center">
          <GitIdentityCard onSaved={onIdentitySaved} />
        </div>
      )
    }
    if (!activeProjectId || !activeProject) {
      return (
        <div className="flex h-full items-center justify-center text-sm text-muted-foreground">
          Select a project from the left panel
        </div>
      )
    }
    if (isProjectLoading) {
      return <div className="flex h-full" />
    }
    // State machine: changedFiles > 0 → ChangesPanel (+ HistoryPanel below if commits exist); hasCommits + selectedDiff → DiffViewer; hasCommits → HistoryPanel; else → EmptyState
    if (changedFiles.length > 0) {
      const changesPane = (
        <ChangesPanel
          projectId={activeProject.id}
          projectPath={activeProject.path}
          changedFiles={changedFiles}
          hasAnyCommits={hasCommits}
          onSaved={handleSaved}
          onDiscarded={handleDiscarded}
          onBranchSwitch={handleBranchSwitch}
        />
      )
      if (!hasCommits) return changesPane
      return (
        <div className="flex flex-col h-full">
          <div className="flex-shrink-0 border-b pb-2">{changesPane}</div>
          <div className="flex-1 overflow-auto pt-2">
            <HistoryPanel
              entries={history}
              projectId={activeProject.id}
              projectPath={activeProject.path}
              onSelectEntry={(entry, file) => setSelectedDiff({ sha: entry.sha, file })}
              onUndo={handleUndo}
              lastPushTimestamp={lastPushTimestamp}
              onNavigate={(view) => setActiveView(view)}
              onPushComplete={() => fetchHistory()}
              onBranchSwitch={handleBranchSwitch}
              activeBranch={activeBranch[activeProject.id]}
              allBranchEntries={allBranchEntries}
            />
          </div>
        </div>
      )
    }
    if (hasCommits && selectedDiff) {
      const currentBranchName = activeBranch[activeProject.id] ?? null
      return (
        <DiffViewer
          sha={selectedDiff.sha}
          file={selectedDiff.file}
          folder={activeProject.path}
          commitMessage={history.find(e => e.sha === selectedDiff.sha)?.message ?? ''}
          onBack={() => setSelectedDiff(null)}
          isExperimentBranch={currentBranchName?.startsWith('experiment/') ?? false}
          compareTo={mergeBaseSha}
        />
      )
    }
    if (hasCommits) {
      return (
        <HistoryPanel
          entries={history}
          projectId={activeProject.id}
          projectPath={activeProject.path}
          onSelectEntry={(entry, file) => setSelectedDiff({ sha: entry.sha, file })}
          onUndo={handleUndo}
          lastPushTimestamp={lastPushTimestamp}
          onNavigate={(view) => setActiveView(view)}
          onPushComplete={() => fetchHistory()}
          onBranchSwitch={handleBranchSwitch}
          activeBranch={activeBranch[activeProject.id]}
          allBranchEntries={allBranchEntries}
        />
      )
    }
    return <EmptyState projectName={activeProject.name} />
  }

  return (
    <div className="flex h-screen overflow-hidden">
      <aside className="w-[220px] flex-shrink-0 border-r bg-muted/40 flex flex-col p-2">
        <Sidebar
          onAddFolder={onAddFolder}
          onOpenSettings={() => setActiveView('settings')}
          onOpenRemote={() => setActiveView('remote')}
        />
      </aside>
      <main className="flex-1 overflow-auto p-6">
        {renderMainContent()}
      </main>
    </div>
  )
}
