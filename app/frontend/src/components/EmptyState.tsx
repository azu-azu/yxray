import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'

interface EmptyStateProps {
  projectName?: string
}

export default function EmptyState({ projectName }: EmptyStateProps) {
  return (
    <div className="flex h-full items-center justify-center">
      <Card className="w-full max-w-md text-center">
        <CardHeader>
          <CardTitle>No saved versions yet</CardTitle>
          <CardDescription>
            Make a change to a workflow in Alteryx Designer, then come back here to save a version.
            {projectName ? ` (for ${projectName})` : ''}
          </CardDescription>
        </CardHeader>
        <CardContent />
      </Card>
    </div>
  )
}
