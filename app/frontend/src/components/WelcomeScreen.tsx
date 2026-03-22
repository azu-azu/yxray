import { FolderOpen } from 'lucide-react'
import { Button } from '@/components/ui/button'
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card'

interface WelcomeScreenProps {
  // onAddFolder wired in Plan 04
  onAddFolder?: () => void
}

export default function WelcomeScreen({ onAddFolder }: WelcomeScreenProps) {
  return (
    <div className="flex min-h-screen items-center justify-center">
      <Card className="w-full max-w-md p-8">
        <CardHeader className="items-center text-center pb-4">
          <FolderOpen className="mb-3 h-10 w-10 text-primary" />
          <CardTitle className="text-2xl">Alteryx Git Companion</CardTitle>
          <CardDescription className="mt-1 text-base">
            Git-based version control for Alteryx analysts — no command line required.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <ul className="mb-6 space-y-2 text-sm text-muted-foreground list-none">
            <li className="flex items-start gap-2">
              <span className="mt-0.5 text-primary">•</span>
              Save named versions of your workflows
            </li>
            <li className="flex items-start gap-2">
              <span className="mt-0.5 text-primary">•</span>
              Browse the full history of every change
            </li>
            <li className="flex items-start gap-2">
              <span className="mt-0.5 text-primary">•</span>
              Compare any two versions side by side
            </li>
            <li className="flex items-start gap-2">
              <span className="mt-0.5 text-primary">•</span>
              Back up to GitHub or GitLab with one click
            </li>
          </ul>
          <Button className="w-full" onClick={onAddFolder}>
            Add Your First Folder
          </Button>
        </CardContent>
      </Card>
    </div>
  )
}
