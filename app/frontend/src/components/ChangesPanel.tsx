import { useState, useEffect } from 'react'
import { Button } from '@/components/ui/button'
import { Checkbox } from '@/components/ui/checkbox'
import { Textarea } from '@/components/ui/textarea'
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
import { Card, CardContent } from '@/components/ui/card'
import { cn } from '@/lib/utils'
import { BranchChip } from '@/components/BranchChip'

interface ChangesPanelProps {
  projectId: string
  projectPath: string
  changedFiles: string[]
  hasAnyCommits: boolean
  onSaved: () => Promise<void>
  onDiscarded: () => Promise<void>
  onBranchSwitch: () => void
}

export function ChangesPanel({
  projectId,
  projectPath,
  changedFiles,
  hasAnyCommits,
  onSaved,
  onDiscarded,
  onBranchSwitch,
}: ChangesPanelProps) {
  const [checkedFiles, setCheckedFiles] = useState<string[]>(changedFiles)
  const [commitMessage, setCommitMessage] = useState('')
  const [isSaving, setIsSaving] = useState(false)
  const [confirmDiscard, setConfirmDiscard] = useState(false)

  // Keep checkedFiles in sync when the file list changes (e.g. after a partial commit)
  useEffect(() => {
    setCheckedFiles(changedFiles)
  }, [changedFiles])

  function toggleFile(file: string, checked: boolean) {
    setCheckedFiles((prev) =>
      checked ? [...prev, file] : prev.filter((f) => f !== file)
    )
  }

  async function handleSave() {
    if (checkedFiles.length === 0 || isSaving) return
    setIsSaving(true)
    try {
      const res = await fetch('/api/save/commit', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          project_id: projectId,
          folder: projectPath,
          files: checkedFiles,
          message: commitMessage,
        }),
      })
      if (res.ok) {
        await onSaved()
      }
    } finally {
      setIsSaving(false)
    }
  }

  async function handleDiscardConfirm() {
    try {
      await fetch('/api/save/discard', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          project_id: projectId,
          folder: projectPath,
          files: checkedFiles,
        }),
      })
    } finally {
      setConfirmDiscard(false)
      onDiscarded()
    }
  }

  const displayFiles =
    !hasAnyCommits && changedFiles.length > 5
      ? changedFiles.slice(0, 5)
      : changedFiles

  const hiddenCount =
    !hasAnyCommits && changedFiles.length > 5 ? changedFiles.length - 5 : 0

  const textareaPlaceholder = hasAnyCommits
    ? 'What changed? e.g. Updated filter logic'
    : 'e.g. Initial version of project workflows'

  return (
    <div className="flex flex-col gap-4 p-4">
      {/* Branch chip */}
      <div className="mb-2">
        <BranchChip
          projectId={projectId}
          projectPath={projectPath}
          changedFiles={changedFiles}
          onBranchSwitch={onBranchSwitch}
        />
      </div>

      {!hasAnyCommits && (
        <Card className="border-amber-400 bg-amber-50 dark:bg-amber-950">
          <CardContent className="pt-4">
            <p className="text-sm text-amber-800 dark:text-amber-200">
              <strong>First version save</strong> &mdash; This will save{' '}
              {checkedFiles.length} workflow{checkedFiles.length !== 1 ? 's' : ''} as your starting
              point.
            </p>
          </CardContent>
        </Card>
      )}

      <div className="flex flex-col gap-2">
        <h3 className="text-sm font-medium">Changed files</h3>
        <div className={cn('flex flex-col gap-1.5')}>
          {displayFiles.map((file) => {
            const basename = file.split('/').pop() ?? file
            return (
              <div key={file} className="flex items-center gap-2">
                <Checkbox
                  id={`file-${file}`}
                  checked={checkedFiles.includes(file)}
                  onCheckedChange={(checked) =>
                    toggleFile(file, checked === true)
                  }
                />
                <label
                  htmlFor={`file-${file}`}
                  className="text-sm cursor-pointer select-none"
                >
                  {basename}
                </label>
              </div>
            )
          })}
          {hiddenCount > 0 && (
            <p className="text-xs text-muted-foreground">
              ...and {hiddenCount} more
            </p>
          )}
        </div>
      </div>

      <Textarea
        placeholder={textareaPlaceholder}
        value={commitMessage}
        onChange={(e) => setCommitMessage(e.target.value)}
        rows={3}
        className="resize-none"
      />

      <div className="flex items-center gap-2">
        <Button
          onClick={handleSave}
          disabled={checkedFiles.length === 0 || isSaving}
          className="flex-1"
        >
          {isSaving ? 'Saving...' : 'Save Version'}
        </Button>
        <Button
          variant="outline"
          onClick={() => setConfirmDiscard(true)}
          disabled={checkedFiles.length === 0}
        >
          Discard
        </Button>
      </div>

      <AlertDialog
        open={confirmDiscard}
        onOpenChange={(open) => !open && setConfirmDiscard(false)}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Discard changes?</AlertDialogTitle>
            <AlertDialogDescription>
              Discard changes to these {checkedFiles.length} workflow(s)? They&apos;ll
              be moved to .acd-backup &mdash; you can recover them from there.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel onClick={() => setConfirmDiscard(false)}>
              Cancel
            </AlertDialogCancel>
            <AlertDialogAction onClick={handleDiscardConfirm}>
              Discard
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

    </div>
  )
}
