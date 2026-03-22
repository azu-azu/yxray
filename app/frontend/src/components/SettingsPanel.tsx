import { useState, useEffect } from 'react'
import { Switch } from '@/components/ui/switch'
import { Label } from '@/components/ui/label'

export function SettingsPanel() {
  const [launchOnStartup, setLaunchOnStartup] = useState(false)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    fetch('/api/settings')
      .then(r => r.json())
      .then(d => {
        setLaunchOnStartup(d.launch_on_startup ?? false)
        setLoading(false)
      })
      .catch(() => setLoading(false))
  }, [])

  async function handleToggle(checked: boolean) {
    setLaunchOnStartup(checked)  // optimistic update
    try {
      await fetch('/api/settings', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ launch_on_startup: checked }),
      })
    } catch {
      // silent fail — tray reflects real state on next poll
    }
  }

  if (loading) return <div className="p-6 text-sm text-muted-foreground">Loading settings…</div>

  return (
    <div className="p-6 space-y-6 max-w-md">
      <h2 className="text-lg font-semibold">Settings</h2>
      <div className="flex items-center justify-between">
        <div className="space-y-0.5">
          <Label htmlFor="launch-on-startup" className="text-sm font-medium">Launch on startup</Label>
          <p className="text-xs text-muted-foreground">
            Start Alteryx Git Companion automatically when Windows boots
          </p>
        </div>
        <Switch
          id="launch-on-startup"
          checked={launchOnStartup}
          onCheckedChange={handleToggle}
        />
      </div>
    </div>
  )
}
