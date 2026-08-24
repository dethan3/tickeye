import { useQuery } from '@tanstack/react-query'
import { Route, Routes } from 'react-router-dom'
import { getHealth } from './api/health'
import './App.css'

function StatusPanel() {
  const health = useQuery({
    queryKey: ['system', 'health'],
    queryFn: ({ signal }) => getHealth(signal),
    retry: false,
    staleTime: 30_000,
  })

  if (health.isPending) {
    return (
      <section className="status-card" aria-live="polite">
        <span className="status-dot status-dot--pending" aria-hidden="true" />
        <div>
          <p className="status-label">系统状态</p>
          <h2>正在连接本地服务…</h2>
        </div>
      </section>
    )
  }

  if (health.isError) {
    return (
      <section className="status-card status-card--error" aria-live="polite">
        <span className="status-dot status-dot--error" aria-hidden="true" />
        <div className="status-content">
          <p className="status-label">系统状态</p>
          <h2>本地服务暂时不可用</h2>
          <p className="status-detail">{health.error.message}</p>
          <button type="button" onClick={() => void health.refetch()}>
            重新连接
          </button>
        </div>
      </section>
    )
  }

  return (
    <section className="status-card" aria-live="polite">
      <span className="status-dot status-dot--ok" aria-hidden="true" />
      <div className="status-content">
        <p className="status-label">系统状态</p>
        <h2>系统已就绪</h2>
        <div className="status-meta">
          <span>API 正常</span>
          <span>数据库正常</span>
          <span>v{health.data.version}</span>
        </div>
      </div>
    </section>
  )
}

function HomePage() {
  return (
    <div className="app-shell">
      <header className="topbar">
        <a className="brand" href="/" aria-label="TickEye 首页">
          <span className="brand-mark" aria-hidden="true">T</span>
          <span>TickEye</span>
        </a>
        <span className="local-badge">本地运行</span>
      </header>

      <main>
        <section className="intro">
          <p className="eyebrow">个人投资风险控制台</p>
          <h1>你的钱，<br />现在安全吗？</h1>
          <p className="intro-copy">
            TickEye 将从持仓、关注标的和市场变化中整理风险信号，帮助你在行动前看清依据。
          </p>
        </section>
        <StatusPanel />
      </main>

      <footer>
        当前为 V2 工程基线，持仓与风险分析能力将在后续迭代接入。
      </footer>
    </div>
  )
}

function App() {
  return (
    <Routes>
      <Route path="*" element={<HomePage />} />
    </Routes>
  )
}

export default App
