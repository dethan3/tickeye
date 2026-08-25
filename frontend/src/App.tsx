import { Link, NavLink, Route, Routes } from 'react-router-dom'
import DataQualityPage from './features/data-quality/DataQualityPage'
import PortfolioPage from './features/portfolio/PortfolioPage'
import EventPage from './features/risk/EventPage'
import PolicyPage from './features/risk/PolicyPage'
import RiskPage from './features/risk/RiskPage'
import ScenarioPage from './features/scenario/ScenarioPage'
import WatchlistPage from './features/watchlist/WatchlistPage'
import './App.css'

function App() {
  return (
    <div className="app-shell">
      <header className="topbar">
        <Link className="brand" to="/" aria-label="TickEye 首页">
          <span className="brand-mark" aria-hidden="true">T</span>
          <span>TickEye</span>
        </Link>
        <nav aria-label="主要导航">
          <NavLink to="/" end>概览</NavLink>
          <NavLink to="/portfolio">持仓</NavLink>
          <NavLink to="/watchlists">观察</NavLink>
          <NavLink to="/data-quality">数据质量</NavLink>
          <NavLink to="/policies">规则</NavLink>
          <NavLink to="/scenarios">方案模拟</NavLink>
          <NavLink to="/events">事件</NavLink>
        </nav>
        <span className="local-badge">本地运行</span>
      </header>

      <Routes>
        <Route path="/" element={<RiskPage />} />
        <Route path="/portfolio" element={<PortfolioPage />} />
        <Route path="/watchlists" element={<WatchlistPage />} />
        <Route path="/data-quality" element={<DataQualityPage />} />
        <Route path="/policies" element={<PolicyPage />} />
        <Route path="/scenarios" element={<ScenarioPage />} />
        <Route path="/events" element={<EventPage />} />
        <Route path="*" element={<RiskPage />} />
      </Routes>

      <footer>
        <span>TickEye 提供风险信息与判断依据，不代替用户作出投资决策。</span>
        <a href="/api/v1/export" download>导出用户数据</a>
      </footer>
    </div>
  )
}

export default App
