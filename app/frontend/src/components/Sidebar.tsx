import { useState } from 'react'
import { Plus, Settings, Cloud } from 'lucide-react'
import { Button } from '@/components/ui/button'
import {
  ContextMenu,
  ContextMenuContent,
  ContextMenuItem,
  ContextMenuTrigger,
} from '@/components/ui/context-menu'
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
import { useProjectStore, type Project } from '@/store/useProjectStore'
import { cn } from '@/lib/utils'

interface SidebarProps {
  onAddFolder?: () => void
  onOpenSettings?: () => void
  onOpenRemote?: () => void
}

export default function Sidebar({ onAddFolder, onOpenSettings, onOpenRemote }: SidebarProps) {
  const { projects, activeProjectId, setActiveProject, removeProject } = useProjectStore()
  const [confirmRemove, setConfirmRemove] = useState<Project | null>(null)

  async function handleRemoveConfirm() {
    if (!confirmRemove) return
    try {
      await fetch(`/api/projects/${confirmRemove.id}`, { method: 'DELETE' })
    } catch {
      // best effort — remove from store regardless
    }
    removeProject(confirmRemove.id)
    setConfirmRemove(null)
  }

  return (
    <>
      <div className="flex items-center justify-between px-1 pb-2">
        <h2 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
          Projects
        </h2>
        <Button size="icon" variant="ghost" className="h-6 w-6" onClick={onAddFolder}>
          <Plus className="h-4 w-4" />
          <span className="sr-only">Add project</span>
        </Button>
      </div>

      <nav className="flex flex-col gap-0.5 overflow-y-auto">
        {projects.map((project) => (
          <ContextMenu key={project.id}>
            <ContextMenuTrigger asChild>
              <button
                className={cn(
                  'w-full flex items-center px-3 py-2 rounded-md text-sm hover:bg-accent transition-colors',
                  activeProjectId === project.id && 'bg-accent font-medium',
                )}
                onClick={() => setActiveProject(project.id)}
              >
                <span className="truncate">{project.name}</span>
                {project.changedCount != null && project.changedCount > 0 && (
                  <span className="ml-auto shrink-0 text-xs font-semibold bg-amber-500 text-white rounded-full px-1.5 py-0.5 min-w-[1.25rem] text-center">
                    {project.changedCount}
                  </span>
                )}
              </button>
            </ContextMenuTrigger>
            <ContextMenuContent>
              <ContextMenuItem
                className="text-destructive"
                onSelect={() => setConfirmRemove(project)}
              >
                Remove project
              </ContextMenuItem>
            </ContextMenuContent>
          </ContextMenu>
        ))}
      </nav>

      <div className="mt-auto pt-2 border-t flex gap-1">
        <Button
          size="icon"
          variant="ghost"
          className="h-7 w-7"
          onClick={onOpenRemote}
          title="Remote Backup"
        >
          <Cloud className="h-4 w-4" />
          <span className="sr-only">Remote Backup</span>
        </Button>
        <Button
          size="icon"
          variant="ghost"
          className="h-7 w-7"
          onClick={onOpenSettings}
          title="Settings"
        >
          <Settings className="h-4 w-4" />
          <span className="sr-only">Settings</span>
        </Button>
      </div>

      <AlertDialog open={confirmRemove !== null} onOpenChange={(open) => !open && setConfirmRemove(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Remove {confirmRemove?.name}?</AlertDialogTitle>
            <AlertDialogDescription>
              This removes the folder from your project list. Your files and version history are not
              deleted.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel onClick={() => setConfirmRemove(null)}>Cancel</AlertDialogCancel>
            <AlertDialogAction onClick={handleRemoveConfirm}>Remove</AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  )
}
