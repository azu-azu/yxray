import { useEffect, useState } from 'react'
import { useProjectStore } from '@/store/useProjectStore'
import { useWatchEvents } from '@/hooks/useWatchEvents'
import WelcomeScreen from '@/components/WelcomeScreen'
import AppShell from '@/components/AppShell'
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog'
import './index.css'

export default function App() {
  const { projects, isLoading, setProjects, addProject, setActiveProject } = useProjectStore()

  useWatchEvents()

  const [showIdentityCard, setShowIdentityCard] = useState(false)
  const [showGitInitConfirm, setShowGitInitConfirm] = useState(false)
  const [pendingPath, setPendingPath] = useState<string | null>(null)
  const [addProjectError, setAddProjectError] = useState<string | null>(null)

  useEffect(() => {
    fetch('/api/projects')
      .then((r) => r.json())
      .then((data) => setProjects(data))
      .catch(() => setProjects([]))  // on error, treat as empty → show welcome screen
  }, [])

  async function handleAddFolder() {
    // Step 1: Open folder picker via backend
    const pickerRes = await fetch('/api/folder-picker', { method: 'POST' })
    const { path, cancelled } = await pickerRes.json()
    if (cancelled || !path) return

    // Step 2: Pre-check — does this folder already have git history?
    const checkRes = await fetch(`/api/projects/check?path=${encodeURIComponent(path)}`)
    const { is_git_repo } = await checkRes.json()

    if (!is_git_repo) {
      // Step 3a: No git history — show confirmation dialog BEFORE any git operation
      setPendingPath(path)
      setShowGitInitConfirm(true)
      // Flow continues in handleConfirmGitInit() below
      return
    }

    // Step 3b: Already has git history — add silently, no dialog
    await doAddProject(path)
  }

  async function handleConfirmGitInit() {
    // Called when user clicks "Set Up" in the confirmation dialog
    setShowGitInitConfirm(false)
    if (!pendingPath) return
    await doAddProject(pendingPath)
    setPendingPath(null)
  }

  function handleCancelGitInit() {
    setShowGitInitConfirm(false)
    setPendingPath(null)
  }

  async function doAddProject(path: string) {
    setAddProjectError(null)
    // POST /api/projects — backend runs git init if needed (already user-approved via dialog)
    const addRes = await fetch('/api/projects', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ path }),
    })
    if (!addRes.ok) {
      const data = await addRes.json().catch(() => ({}))
      setAddProjectError(
        addRes.status === 409
          ? 'This folder is already registered.'
          : (data.detail ?? 'Could not add project. Try again.')
      )
      return
    }
    const project = await addRes.json()
    addProject(project)
    setActiveProject(project.id)

    // Check git identity
    const identityRes = await fetch('/api/git/identity')
    const identity = await identityRes.json()
    if (!identity.name || !identity.email) {
      setShowIdentityCard(true)
    }
  }

  if (isLoading) return null  // prevents welcome screen flash on reload

  return (
    <>
      {addProjectError && (
        <div className="fixed top-4 left-1/2 -translate-x-1/2 z-50 bg-red-50 border border-red-200 text-red-700 text-sm px-4 py-2 rounded shadow-md">
          {addProjectError}
          <button className="ml-3 text-red-400 hover:text-red-600" onClick={() => setAddProjectError(null)}>&#x2715;</button>
        </div>
      )}
      {projects.length === 0 ? (
        <WelcomeScreen onAddFolder={handleAddFolder} />
      ) : (
        <AppShell
          onAddFolder={handleAddFolder}
          showIdentityCard={showIdentityCard}
          onIdentitySaved={() => setShowIdentityCard(false)}
        />
      )}

      <AlertDialog open={showGitInitConfirm} onOpenChange={setShowGitInitConfirm}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Set up version control?</AlertDialogTitle>
            <AlertDialogDescription>
              This folder isn't a git repo yet. We'll set it up for version control. Continue?
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel onClick={handleCancelGitInit}>Cancel</AlertDialogCancel>
            <AlertDialogAction onClick={handleConfirmGitInit}>Set Up</AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  )
}
