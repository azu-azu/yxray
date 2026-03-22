import { useState } from 'react'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Button } from '@/components/ui/button'

interface GitIdentityCardProps {
  onSaved: () => void
}

export function GitIdentityCard({ onSaved }: GitIdentityCardProps) {
  const [name, setName] = useState('')
  const [email, setEmail] = useState('')
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function handleSave() {
    if (!name.trim() || !email.trim()) {
      setError('Both name and email are required.')
      return
    }
    setSaving(true)
    try {
      const res = await fetch('/api/git/identity', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: name.trim(), email: email.trim() }),
      })
      if (!res.ok) throw new Error('Failed to save identity')
      onSaved()
    } catch {
      setError('Could not save. Please try again.')
    } finally {
      setSaving(false)
    }
  }

  return (
    <Card className="max-w-md">
      <CardHeader>
        <CardTitle>Almost done</CardTitle>
        <CardDescription>
          Enter your name and email for version control attribution. This is saved globally on your computer.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="space-y-2">
          <label className="text-sm font-medium" htmlFor="git-name">Name</label>
          <Input id="git-name" value={name} onChange={(e) => setName(e.target.value)} placeholder="Your name" />
        </div>
        <div className="space-y-2">
          <label className="text-sm font-medium" htmlFor="git-email">Email</label>
          <Input id="git-email" type="email" value={email} onChange={(e) => setEmail(e.target.value)} placeholder="your@email.com" />
        </div>
        {error && <p className="text-sm text-destructive">{error}</p>}
        <Button onClick={handleSave} disabled={saving} className="w-full">
          {saving ? 'Saving...' : 'Save'}
        </Button>
      </CardContent>
    </Card>
  )
}
