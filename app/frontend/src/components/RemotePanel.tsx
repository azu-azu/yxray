import { useState, useEffect, useRef } from 'react'
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs'
import { Button } from '@/components/ui/button'
import { useProjectStore } from '@/store/useProjectStore'
import { Cloud } from 'lucide-react'

interface RemoteStatus {
  ahead: number
  behind: number
  github_connected: boolean
  gitlab_connected: boolean
  repo_url: string | null
}

interface GitHubFlow {
  userCode: string
  verificationUri: string
}

type PushState = 'idle' | 'pushing' | 'done' | 'error'
type PushErrorKind = 'generic' | 'auth_expired' | null
type PullState = 'idle' | 'pulling' | 'done' | 'up_to_date' | 'error'

export function RemotePanel({ onPushComplete }: { onPushComplete?: () => void } = {}) {
  const { projects, activeProjectId, activeBranch } = useProjectStore()
  const activeProject = projects.find((p) => p.id === activeProjectId)
  const currentBranch = activeBranch[activeProject?.id ?? ''] ?? 'main'
const [loading, setLoading] = useState(true)
  const [remoteStatus, setRemoteStatus] = useState<RemoteStatus | null>(null)
  const [statusError, setStatusError] = useState<string | null>(null)
  const [activeTab, setActiveTab] = useState<'github' | 'gitlab'>('github')

  // GitHub device flow state
  const [githubFlow, setGithubFlow] = useState<GitHubFlow | null>(null)
  const [githubFlowError, setGithubFlowError] = useState<string | null>(null)
  const [githubPolling, setGithubPolling] = useState(false)
  const [codeCopied, setCodeCopied] = useState(false)
  const pollIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null)

  // GitHub PAT fallback
  const [showGithubPat, setShowGithubPat] = useState(false)
  const [githubPatValue, setGithubPatValue] = useState('')
  const [githubPatError, setGithubPatError] = useState<string | null>(null)

  // GitLab PAT
  const [gitlabPatValue, setGitlabPatValue] = useState('')
  const [gitlabPatError, setGitlabPatError] = useState<string | null>(null)
  const [gitlabConnecting, setGitlabConnecting] = useState(false)

  // Push state
  const [githubPushState, setGithubPushState] = useState<PushState>('idle')
  const [githubPushError, setGithubPushError] = useState<PushErrorKind>(null)
  const [gitlabPushState, setGitlabPushState] = useState<PushState>('idle')
  const [gitlabPushError, setGitlabPushError] = useState<PushErrorKind>(null)

  // Pull state
  const [githubPullState, setGithubPullState] = useState<PullState>('idle')
  const [gitlabPullState, setGitlabPullState] = useState<PullState>('idle')
  const [githubPullError, setGithubPullError] = useState<string | null>(null)
  const [gitlabPullError, setGitlabPullError] = useState<string | null>(null)

  async function fetchStatus() {
    if (!activeProject) {
      setLoading(false)
      return
    }
    setLoading(true)
    setStatusError(null)
    try {
      const [githubRes, gitlabRes] = await Promise.all([
        fetch(
          `/api/remote/status?project_id=${encodeURIComponent(activeProject.id)}&folder=${encodeURIComponent(activeProject.path)}&provider=github`
        ),
        fetch(
          `/api/remote/status?project_id=${encodeURIComponent(activeProject.id)}&folder=${encodeURIComponent(activeProject.path)}&provider=gitlab`
        ),
      ])
      if (!githubRes.ok) throw new Error('Failed to fetch remote status')
      const githubData = await githubRes.json()
      const gitlabData = gitlabRes.ok ? await gitlabRes.json() : null
      setRemoteStatus({
        ...githubData,
      })
    } catch {
      setStatusError('Could not load remote status. Check your connection.')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchStatus()
    // Clean up polling on unmount or project change
    return () => {
      if (pollIntervalRef.current) {
        clearInterval(pollIntervalRef.current)
        pollIntervalRef.current = null
      }
    }
  }, [activeProjectId, currentBranch]) // eslint-disable-line react-hooks/exhaustive-deps

  function stopPolling() {
    if (pollIntervalRef.current) {
      clearInterval(pollIntervalRef.current)
      pollIntervalRef.current = null
    }
    setGithubPolling(false)
  }

  async function startGithubDeviceFlow() {
    setGithubFlowError(null)
    try {
      const res = await fetch('/api/remote/github/start', { method: 'POST' })
      if (!res.ok) throw new Error('start failed')
      const data = await res.json()
      setGithubFlow({ userCode: data.user_code, verificationUri: data.verification_uri })
      setGithubPolling(true)

      const intervalId = setInterval(async () => {
        try {
          const statusRes = await fetch('/api/remote/github/status')
          if (!statusRes.ok) return
          const statusData = await statusRes.json()
          if (statusData.connected) {
            stopPolling()
            setGithubFlow(null)
            await fetchStatus()
          }
        } catch {
          // ignore poll errors — keep polling
        }
      }, 3000)
      pollIntervalRef.current = intervalId
    } catch {
      setGithubFlowError('Could not connect to GitHub. Check your internet connection.')
    }
  }

  async function connectGithubPat() {
    setGithubPatError(null)
    try {
      const res = await fetch('/api/remote/github/connect', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ token: githubPatValue }),
      })
      if (!res.ok) throw new Error('connect failed')
      const data = await res.json()
      if (data.connected) {
        setShowGithubPat(false)
        setGithubPatValue('')
        setGithubFlow(null)
        stopPolling()
        await fetchStatus()
      } else {
        setGithubPatError('Token not accepted. Check the token and try again.')
      }
    } catch {
      setGithubPatError('Could not connect to GitHub. Check your internet connection.')
    }
  }

  async function connectGitlab() {
    setGitlabPatError(null)
    setGitlabConnecting(true)
    try {
      const res = await fetch('/api/remote/gitlab/connect', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ token: gitlabPatValue }),
      })
      const data = await res.json()
      if (data.connected) {
        setGitlabPatValue('')
        await fetchStatus()
      } else {
        setGitlabPatError(data.error ?? 'Token not accepted. Check the token and try again.')
      }
    } catch {
      setGitlabPatError('Could not connect to GitLab. Check your internet connection.')
    } finally {
      setGitlabConnecting(false)
    }
  }

  async function handlePush(provider: 'github' | 'gitlab') {
    if (!activeProject) return
    const setPushState = provider === 'github' ? setGithubPushState : setGitlabPushState
    const setPushError = provider === 'github' ? setGithubPushError : setGitlabPushError
    setPushState('pushing')
    setPushError(null)
    try {
      const res = await fetch('/api/remote/push', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          project_id: activeProject.id,
          folder: activeProject.path,
          provider,
        }),
      })
      const data = await res.json()
      if (data.success) {
        setPushState('done')
        await fetchStatus()
        setTimeout(() => setPushState('idle'), 3000)
        onPushComplete?.()
      } else {
        const errorMsg: string = data.error ?? ''
        if (errorMsg.toLowerCase().includes('auth') || errorMsg.toLowerCase().includes('401')) {
          setPushError('auth_expired')
        } else {
          setPushError('generic')
        }
        setPushState('error')
      }
    } catch {
      setPushError('generic')
      setPushState('error')
    }
  }

  async function handlePull(provider: 'github' | 'gitlab') {
    if (!activeProject) return
    const setPullState = provider === 'github' ? setGithubPullState : setGitlabPullState
    const setPullError = provider === 'github' ? setGithubPullError : setGitlabPullError
    setPullState('pulling')
    setPullError(null)
    try {
      const res = await fetch('/api/remote/pull', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          project_id: activeProject.id,
          folder: activeProject.path,
          provider,
        }),
      })
      const data = await res.json()
      if (data.success) {
        setPullState(data.already_up_to_date ? 'up_to_date' : 'done')
        await fetchStatus()
        setTimeout(() => setPullState('idle'), 3000)
      } else {
        setPullError(data.error ?? 'Pull failed.')
        setPullState('error')
      }
    } catch {
      setPullError('Pull failed. Check your connection.')
      setPullState('error')
    }
  }

  function copyCode(code: string) {
    navigator.clipboard.writeText(code)
    setCodeCopied(true)
    setTimeout(() => setCodeCopied(false), 2000)
  }

  function renderAheadBehind() {
    if (!remoteStatus || !remoteStatus.repo_url) return null
    return (
      <p className="text-xs text-muted-foreground mb-3">
        ↑ {remoteStatus.ahead} ahead · ↓ {remoteStatus.behind} behind
      </p>
    )
  }

  function renderPushButton(provider: 'github' | 'gitlab') {
    if (!remoteStatus) return null
    const pushState = provider === 'github' ? githubPushState : gitlabPushState
    const pushError = provider === 'github' ? githubPushError : gitlabPushError
    const pullState = provider === 'github' ? githubPullState : gitlabPullState
    const pullError = provider === 'github' ? githubPullError : gitlabPullError
    const repoUrl = remoteStatus.repo_url
    const projectSlug = activeProject?.name.toLowerCase().replace(/[^a-z0-9-]/g, '-') ?? 'my-workflows'

    return (
      <div className="space-y-2">
        {renderAheadBehind()}
        {!repoUrl && (
          <p className="text-xs text-muted-foreground mb-2">
            No remote repo yet. We'll create <strong>{projectSlug}</strong> (private) on {provider === 'github' ? 'GitHub' : 'GitLab'}.
          </p>
        )}
        <div className="flex gap-2">
          <Button
            size="sm"
            onClick={() => handlePush(provider)}
            disabled={pushState === 'pushing'}
          >
            {pushState === 'pushing'
              ? 'Pushing...'
              : pushState === 'done'
              ? 'Pushed!'
              : repoUrl
              ? `Push`
              : `Push and Create Repo`}
          </Button>
          {repoUrl && (
            <Button
              size="sm"
              variant="outline"
              onClick={() => handlePull(provider)}
              disabled={pullState === 'pulling'}
            >
              {pullState === 'pulling'
                ? 'Pulling...'
                : pullState === 'done'
                ? 'Pulled!'
                : pullState === 'up_to_date'
                ? 'Up to date'
                : 'Pull'}
            </Button>
          )}
        </div>
        {pushState === 'error' && pushError === 'auth_expired' && (
          <div className="flex items-center gap-2 mt-1">
            <p className="text-xs text-red-500">Authentication expired.</p>
            <button
              className="text-xs text-blue-500 underline underline-offset-2 hover:text-blue-600 transition-colors"
              onClick={() => {
                const setPushState = provider === 'github' ? setGithubPushState : setGitlabPushState
                const setPushError = provider === 'github' ? setGithubPushError : setGitlabPushError
                setPushState('idle')
                setPushError(null)
                setRemoteStatus((prev) => prev
                  ? { ...prev, github_connected: provider === 'github' ? false : prev.github_connected, gitlab_connected: provider === 'gitlab' ? false : prev.gitlab_connected }
                  : prev)
              }}
            >
              Reconnect
            </button>
          </div>
        )}
        {pushState === 'error' && pushError === 'generic' && (
          <p className="text-xs text-red-500 mt-1">Push failed. Check your connection and try again.</p>
        )}
        {pullState === 'error' && (
          <p className="text-xs text-red-500 mt-1">{pullError}</p>
        )}
      </div>
    )
  }

  async function disconnect(provider: 'github' | 'gitlab') {
    await fetch(`/api/remote/${provider}/disconnect`, { method: 'POST' })
    await fetchStatus()
  }

  function renderGithubTab() {
    const connected = remoteStatus?.github_connected ?? false

    if (connected) {
      return (
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <span className="inline-block w-2 h-2 rounded-full bg-green-500" />
              <span className="text-sm font-medium text-green-600">Connected</span>
            </div>
            <button
              className="text-xs text-muted-foreground underline underline-offset-2 hover:text-destructive transition-colors"
              onClick={() => disconnect('github')}
            >
              Disconnect
            </button>
          </div>
          {renderPushButton('github')}
        </div>
      )
    }

    return (
      <div className="space-y-4">
        {githubFlowError && (
          <p className="text-xs text-red-500">{githubFlowError}</p>
        )}
        {!githubFlow ? (
          <div className="space-y-3">
            <Button size="sm" onClick={startGithubDeviceFlow}>
              Connect GitHub
            </Button>
          </div>
        ) : (
          <div className="space-y-3">
            <p className="text-sm text-muted-foreground">Enter this code on GitHub:</p>
            <div className="inline-flex items-center gap-2 bg-muted rounded-md px-3 py-2">
              <code className="font-mono text-sm font-semibold tracking-widest">
                {githubFlow.userCode}
              </code>
            </div>
            <div className="flex gap-2">
              <Button size="sm" variant="outline" onClick={() => copyCode(githubFlow.userCode)}>
                {codeCopied ? 'Copied!' : 'Copy Code'}
              </Button>
              <Button
                size="sm"
                variant="outline"
                onClick={() => window.open(githubFlow.verificationUri, '_blank')}
              >
                Open github.com/login/device
              </Button>
            </div>
            {githubPolling && (
              <p className="text-xs text-muted-foreground flex items-center gap-1">
                <span className="inline-block w-3 h-3 border-2 border-current border-t-transparent rounded-full animate-spin" />
                Waiting for authorization...
              </p>
            )}
          </div>
        )}

        {!showGithubPat ? (
          <button
            className="text-xs text-muted-foreground underline underline-offset-2 hover:text-foreground transition-colors"
            onClick={() => setShowGithubPat(true)}
          >
            Use a token instead
          </button>
        ) : (
          <div className="space-y-2 border-t pt-3">
            <p className="text-xs font-medium">GitHub Personal Access Token</p>
            <input
              type="password"
              placeholder="ghp_xxxxxxxxxxxxxxxxxxxx"
              value={githubPatValue}
              onChange={(e) => setGithubPatValue(e.target.value)}
              className="w-full rounded-md border bg-background px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
            />
            {githubPatError && (
              <p className="text-xs text-red-500">{githubPatError}</p>
            )}
            <div className="flex gap-2">
              <Button size="sm" onClick={connectGithubPat} disabled={!githubPatValue}>
                Connect
              </Button>
              <Button size="sm" variant="ghost" onClick={() => { setShowGithubPat(false); setGithubPatValue(''); setGithubPatError(null) }}>
                Cancel
              </Button>
            </div>
          </div>
        )}
      </div>
    )
  }

  function renderGitlabTab() {
    const connected = remoteStatus?.gitlab_connected ?? false

    if (connected) {
      return (
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <span className="inline-block w-2 h-2 rounded-full bg-green-500" />
              <span className="text-sm font-medium text-green-600">Connected</span>
            </div>
            <button
              className="text-xs text-muted-foreground underline underline-offset-2 hover:text-destructive transition-colors"
              onClick={() => disconnect('gitlab')}
            >
              Disconnect
            </button>
          </div>
          {renderPushButton('gitlab')}
        </div>
      )
    }

    return (
      <div className="space-y-4">
        <ol className="text-sm text-muted-foreground space-y-2 list-none">
          <li>
            <span className="font-medium text-foreground">1.</span> Log in to GitLab in your browser.
          </li>
          <li>
            <span className="font-medium text-foreground">2.</span> Go to your token settings:{' '}
            <button
              className="text-blue-500 underline underline-offset-2 hover:text-blue-600 transition-colors"
              onClick={() => window.open('https://gitlab.com/-/user_settings/personal_access_tokens', '_blank')}
            >
              Open GitLab Settings
            </button>
          </li>
          <li>
            <span className="font-medium text-foreground">3.</span> Create a token with the{' '}
            <code className="bg-muted px-1 rounded text-xs">api</code> scope, copy it, and paste it below.
          </li>
        </ol>
        <div className="space-y-2">
          <input
            type="password"
            placeholder="glpat-xxxxxxxxxxxxxxxxxxxx"
            value={gitlabPatValue}
            onChange={(e) => setGitlabPatValue(e.target.value)}
            className="w-full rounded-md border bg-background px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
          />
          {gitlabPatError && (
            <p className="text-xs text-red-500">{gitlabPatError}</p>
          )}
          <Button
            size="sm"
            onClick={connectGitlab}
            disabled={!gitlabPatValue || gitlabConnecting}
          >
            {gitlabConnecting ? 'Connecting...' : 'Connect GitLab'}
          </Button>
        </div>
      </div>
    )
  }

  function renderDisconnectedCTA() {
    const bothDisconnected =
      !remoteStatus?.github_connected && !remoteStatus?.gitlab_connected

    if (!bothDisconnected) return null

    return (
      <div className="mb-6 p-4 rounded-lg border border-dashed space-y-3">
        <p className="text-sm text-muted-foreground">
          Back up your workflows. Connect GitHub or GitLab to push saved versions to the cloud.
        </p>
        <div className="flex gap-2">
          <Button size="sm" variant="outline" onClick={startGithubDeviceFlow}>
            Connect GitHub
          </Button>
          <Button size="sm" variant="outline" onClick={() => setActiveTab('gitlab')}>
            Connect GitLab
          </Button>
        </div>
      </div>
    )
  }

  if (loading) {
    return (
      <div className="p-6 text-sm text-muted-foreground">Loading...</div>
    )
  }

  return (
    <div className="p-6 space-y-4 max-w-lg">
      <div className="flex items-center gap-2">
        <Cloud className="h-5 w-5 text-muted-foreground" />
        <h2 className="text-lg font-semibold">Remote Backup</h2>
      </div>

      {statusError && (
        <p className="text-sm text-red-500">{statusError}</p>
      )}

      {!activeProject && (
        <p className="text-sm text-muted-foreground">Select a project to manage remote backup.</p>
      )}

      {activeProject && remoteStatus && (
        <>
          {renderDisconnectedCTA()}

          <Tabs value={activeTab} onValueChange={(v) => setActiveTab(v as 'github' | 'gitlab')}>
            <TabsList>
              <TabsTrigger value="github">GitHub</TabsTrigger>
              <TabsTrigger value="gitlab">GitLab</TabsTrigger>
            </TabsList>
            <TabsContent value="github" className="pt-4">
              {renderGithubTab()}
            </TabsContent>
            <TabsContent value="gitlab" className="pt-4">
              {renderGitlabTab()}
            </TabsContent>
          </Tabs>
        </>
      )}
    </div>
  )
}
