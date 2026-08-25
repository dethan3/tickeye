import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import type {
  RiskCalculationStatus,
  RiskResponse,
  RiskSnapshotData,
  ValuationSource,
} from '../../api/generated'
import { getEvents } from '../../api/policy'
import { getCurrentRisk, recalculateRisk } from '../../api/risk'
import './RiskPage.css'

const statusContent: Record<RiskCalculationStatus, { label: string; description: string }> = {
  available: {
    label: '历史风险可计算',
    description: '数据满足当前方法的最低要求。这里不代表组合处于安全状态。',
  },
  unknown: {
    label: '信息不足',
    description: '当前证据不足以可靠计算历史市场风险，系统不会补造结论。',
  },
  all_cash: {
    label: '全现金组合',
    description: '在现金日收益为 0 的假设下，历史市场波动为 0；这不涵盖通胀和信用风险。',
  },
}

const valuationLabels: Record<ValuationSource, string> = {
  market_data: '市场数据',
  manual_value: '手工市值',
  cash_balance: '现金余额',
  zero_quantity: '零数量',
  unavailable: '无法估值',
}

const limitationLabels: Record<string, string> = {
  qfq_history_can_be_revised: '前复权历史可能因分红送配重新计算',
  unit_nav_only: '该基金只取得单位净值，未包含完整分红影响',
  invalid_stored_limitations: '历史数据限制说明无法解析',
}

const policyStateLabels = {
  unknown: '无法判断',
  within: '边界内',
  watch: '接近边界',
  breached: '已越界',
}

const eventLabels: Record<string, string> = {
  detected: '首次发现',
  state_changed: '状态变化',
  recovered: '恢复到边界内',
}

type RiskNextStep = {
  tone: 'neutral' | 'attention' | 'critical'
  title: string
  description: string
  primary: { label: string; to: string } | 'recalculate'
  secondary: Array<{ label: string; to: string }>
}

function nextStepFor(snapshot: RiskSnapshotData): RiskNextStep {
  const { analysis, evaluation } = snapshot
  const { coverage } = analysis

  if (!snapshot.is_current) {
    return {
      tone: 'attention',
      title: '先更新已经过期的判断',
      description: '持仓或行情已经变化，以下结论仍属于旧快照。重新计算后再决定是否需要调整。',
      primary: 'recalculate',
      secondary: [{ label: '检查数据质量', to: '/data-quality' }],
    }
  }
  if (coverage.total_positions === 0) {
    return {
      tone: 'attention',
      title: '先建立真实持仓事实',
      description: '当前没有可分析的持仓。系统不会把观察列表当成你的资产，也不会据此生成风险结论。',
      primary: { label: '录入实际持仓', to: '/portfolio' },
      secondary: [{ label: '管理观察列表', to: '/watchlists' }],
    }
  }
  if (evaluation?.state === 'breached') {
    return {
      tone: 'critical',
      title: '先处理已经越过的风险边界',
      description: '至少一项用户设定的边界已经被突破。先查看原因，再用临时副本比较不同调整对整体风险的影响。',
      primary: { label: '模拟风险调整', to: '/scenarios' },
      secondary: [
        { label: '核对风险规则', to: '/policies' },
        { label: '查看变化事件', to: '/events' },
      ],
    }
  }
  if (
    analysis.status === 'unknown'
    || coverage.valued_positions < coverage.total_positions
  ) {
    return {
      tone: 'attention',
      title: '先补齐风险判断所需的数据',
      description: '部分持仓缺少可靠估值或历史样本，当前证据不足。先处理数据问题，不要把无法计算理解成低风险。',
      primary: { label: '检查并刷新数据', to: '/data-quality' },
      secondary: [{ label: '核对持仓信息', to: '/portfolio' }],
    }
  }
  if (evaluation?.state === 'watch') {
    return {
      tone: 'attention',
      title: '关注正在接近边界的项目',
      description: '当前尚未确认越界，但已经进入你设置的关注区间。可以先核对边界，再模拟潜在调整。',
      primary: { label: '查看风险规则', to: '/policies' },
      secondary: [{ label: '模拟风险调整', to: '/scenarios' }],
    }
  }
  if (evaluation === null || evaluation === undefined || evaluation.state === 'unknown') {
    return {
      tone: 'neutral',
      title: '历史风险已有数据，但尚无个人边界结论',
      description: '系统可以描述波动、回撤和集中度事实，但不会替你设定什么程度算越界。你可以按需声明自己的边界。',
      primary: { label: '按需设置风险边界', to: '/policies' },
      secondary: [{ label: '模拟候选调整', to: '/scenarios' }],
    }
  }
  return {
    tone: 'neutral',
    title: '当前规则未发现越界，继续检查结构变化',
    description: '边界内不等于绝对安全，也不代表未来不会变化。可以查看自己关注的标的，并在操作前比较风险影响。',
    primary: { label: '查看观察列表', to: '/watchlists' },
    secondary: [{ label: '模拟候选调整', to: '/scenarios' }],
  }
}

function percent(value: string | null): string {
  if (value === null) return '无法计算'
  return `${(Number(value) * 100).toFixed(2)}%`
}

function money(value: string | null): string {
  if (value === null) return '未知'
  return new Intl.NumberFormat('zh-CN', {
    style: 'currency',
    currency: 'CNY',
    maximumFractionDigits: 2,
  }).format(Number(value))
}

export default function RiskPage() {
  const queryClient = useQueryClient()
  const current = useQuery({
    queryKey: ['risk', 'current'],
    queryFn: ({ signal }) => getCurrentRisk(signal),
  })
  const events = useQuery({
    queryKey: ['events'],
    queryFn: ({ signal }) => getEvents(signal),
    enabled: current.data?.data !== null && current.data?.data !== undefined,
  })
  const recalculate = useMutation({
    mutationFn: recalculateRisk,
    onSuccess: (response) => {
      queryClient.setQueryData<RiskResponse>(['risk', 'current'], response)
      void queryClient.invalidateQueries({ queryKey: ['events'] })
    },
  })

  if (current.isPending) {
    return <main className="risk-main"><p>正在读取风险快照…</p></main>
  }
  if (current.isError) {
    return (
      <main className="risk-main">
        <div className="page-error">
          <h1>无法读取风险快照</h1>
          <p>{current.error.message}</p>
          <button type="button" onClick={() => void current.refetch()}>重新读取</button>
        </div>
      </main>
    )
  }

  if (current.data.data === null) {
    return (
      <main className="risk-main risk-empty-main">
        <section className="risk-intro">
          <p className="eyebrow">个人投资风险控制台</p>
          <h1>你的钱，<br />现在安全吗？</h1>
          <p>
            先录入持仓并刷新行情，然后生成第一份当前权重历史风险模拟。
            TickEye 不会把它描述成真实账户收益。
          </p>
          <div className="risk-empty-actions">
            <button
              className="primary-button"
              type="button"
              disabled={recalculate.isPending}
              onClick={() => recalculate.mutate()}
            >
              {recalculate.isPending ? '正在计算…' : '生成第一份风险快照'}
            </button>
            <Link to="/portfolio">先检查持仓</Link>
            <Link to="/data-quality">先检查数据</Link>
          </div>
          {recalculate.isError && <p className="risk-error">{recalculate.error.message}</p>}
        </section>
      </main>
    )
  }

  const snapshot = current.data.data
  const analysis = snapshot.analysis
  const status = statusContent[analysis.status]
  const metrics = analysis.metrics
  const evaluation = snapshot.evaluation
  const leadingInstrument = analysis.instrument_exposures[0]
  const leadingAssetClass = analysis.asset_class_exposures[0]
  const nextStep = nextStepFor(snapshot)

  return (
    <main className="risk-main">
      <div className="risk-heading">
        <div>
          <p className="eyebrow">当前权重历史风险模拟</p>
          <h1>风险概览</h1>
          <p>这是用当前权重回放历史的风险测量，不是账户收益，也不是未来预测。</p>
        </div>
        <button
          className="primary-button"
          type="button"
          disabled={recalculate.isPending}
          onClick={() => recalculate.mutate()}
        >
          {recalculate.isPending ? '正在重新计算…' : '重新计算'}
        </button>
      </div>

      {!snapshot.is_current && (
        <div className="risk-stale" role="alert">
          这份快照已经过期。持仓或市场数据发生了变化，请重新计算后再判断。
        </div>
      )}
      {recalculate.isError && (
        <div className="risk-stale" role="alert">重新计算失败：{recalculate.error.message}</div>
      )}

      <section className={`risk-next-step risk-next-step--${nextStep.tone}`}>
        <div>
          <p className="section-kicker">NEXT STEP</p>
          <h2>当前最应先处理</h2>
          <strong>{nextStep.title}</strong>
          <p>{nextStep.description}</p>
        </div>
        <div className="risk-next-actions">
          {nextStep.primary === 'recalculate' ? (
            <button
              className="primary-button"
              type="button"
              disabled={recalculate.isPending}
              onClick={() => recalculate.mutate()}
            >
              {recalculate.isPending ? '正在重新计算…' : '立即重新计算'}
            </button>
          ) : (
            <Link className="primary-button" to={nextStep.primary.to}>{nextStep.primary.label}</Link>
          )}
          {nextStep.secondary.map((item) => (
            <Link key={item.to} to={item.to}>{item.label}</Link>
          ))}
        </div>
      </section>

      <section className={`risk-state risk-state--${analysis.status}`}>
        <div>
          <span>计算状态</span>
          <strong>{status.label}</strong>
          <p>{status.description}</p>
        </div>
        <dl>
          <div><dt>持仓数据截至</dt><dd>{analysis.portfolio_as_of ?? '—'}</dd></div>
          <div><dt>市场数据截至</dt><dd>{analysis.market_data_as_of ?? '—'}</dd></div>
          <div><dt>共同观测日</dt><dd>{metrics.aligned_observations}</dd></div>
          <div><dt>方法版本</dt><dd>{analysis.methodology_version}</dd></div>
        </dl>
      </section>

      {evaluation !== null && evaluation !== undefined && (
        <section className={`risk-policy-state risk-policy-state--${evaluation.state}`}>
          <div><span>用户规则汇总状态</span><strong>{policyStateLabels[evaluation.state]}</strong></div>
          <div className="risk-policy-findings">
            {evaluation.findings.map((finding) => (
              <article key={finding.finding_key}>
                <span>{policyStateLabels[finding.state]}</span>
                <strong>{finding.title}</strong>
                <p>{finding.message}</p>
                {finding.current_value !== null && <small>当前值 {percent(finding.current_value)}</small>}
              </article>
            ))}
          </div>
        </section>
      )}

      <section className="risk-panel risk-recent-events">
        <div className="risk-panel-heading">
          <div><p className="section-kicker">RECENT CHANGES</p><h2>最近的重要变化</h2></div>
          <Link to="/events">查看完整记录</Link>
        </div>
        <p className="risk-panel-note">最多展示最近 3 条已记录的规则状态变化；这里不维护已读或未读状态。</p>
        {events.isPending ? (
          <p className="risk-events-empty">正在读取变化记录…</p>
        ) : events.isError ? (
          <p className="risk-events-error">变化记录暂时无法读取，不影响当前风险快照。</p>
        ) : events.data.data.items.length === 0 ? (
          <p className="risk-events-empty">尚无重要变化。只有首次发现、真实状态变化和恢复会被记录。</p>
        ) : (
          <div className="risk-event-list">
            {events.data.data.items.slice(0, 3).map((event) => (
              <article key={event.event_id} className={`risk-event risk-event--${event.to_state}`}>
                <div>
                  <span>{eventLabels[event.event_type] ?? event.event_type}</span>
                  <time>{new Date(event.occurred_at).toLocaleString('zh-CN')}</time>
                </div>
                <strong>{event.finding.title}</strong>
                <p>{event.finding.message}</p>
              </article>
            ))}
          </div>
        )}
      </section>

      <section className="risk-metrics" aria-label="历史风险指标">
        <div><span>年化波动率</span><strong>{percent(metrics.annualized_volatility)}</strong></div>
        <div><span>下行波动率</span><strong>{percent(metrics.downside_volatility)}</strong></div>
        <div><span>模拟最大回撤</span><strong>{percent(metrics.max_drawdown)}</strong></div>
        <div><span>当前模拟回撤</span><strong>{percent(metrics.current_drawdown)}</strong></div>
      </section>

      <div className="risk-grid">
        <section className="risk-panel">
          <p className="section-kicker">VALUATION & COVERAGE</p>
          <h2>估值与覆盖</h2>
          <dl className="risk-detail-list">
            <div><dt>已知组合市值</dt><dd>{money(analysis.coverage.known_portfolio_value)}</dd></div>
            <div><dt>估值持仓</dt><dd>{analysis.coverage.valued_positions} / {analysis.coverage.total_positions}</dd></div>
            <div><dt>持仓数量覆盖</dt><dd>{percent(analysis.coverage.valued_position_ratio)}</dd></div>
            <div><dt>历史模拟权重</dt><dd>{percent(analysis.coverage.historical_value_ratio)}</dd></div>
          </dl>
        </section>

        <section className="risk-panel">
          <p className="section-kicker">CONCENTRATION</p>
          <h2>集中度事实</h2>
          <dl className="risk-detail-list">
            <div><dt>最大单一标的</dt><dd>{leadingInstrument?.label ?? '—'}</dd></div>
            <div><dt>标的权重</dt><dd>{percent(leadingInstrument?.weight ?? null)}</dd></div>
            <div><dt>最大资产类别</dt><dd>{leadingAssetClass?.label ?? '—'}</dd></div>
            <div><dt>类别权重</dt><dd>{percent(leadingAssetClass?.weight ?? null)}</dd></div>
          </dl>
          <p className="risk-panel-note">集中度事实来自当前估值；是否越界只按用户在“规则”页面明确设置的边界判断。</p>
        </section>
      </div>

      {analysis.evidence.length > 0 && (
        <section className="risk-panel risk-evidence">
          <p className="section-kicker">EVIDENCE</p>
          <h2>证据与无法计算原因</h2>
          <ul>{analysis.evidence.map((item, index) => <li key={`${item.code}-${index}`}>{item.message}</li>)}</ul>
        </section>
      )}

      <section className="risk-panel">
        <p className="section-kicker">POSITION VALUATION</p>
        <h2>持仓估值依据</h2>
        <div className="risk-table-wrap">
          <table className="risk-table">
            <thead><tr><th>标的</th><th>估值</th><th>权重</th><th>依据</th><th>日期</th></tr></thead>
            <tbody>
              {analysis.positions.map((position) => (
                <tr key={position.position_id}>
                  <td><strong>{position.name}</strong><span>{position.code} · {position.account_name}</span></td>
                  <td>{money(position.value)}</td>
                  <td>{percent(position.weight)}</td>
                  <td>{valuationLabels[position.valuation_source]}</td>
                  <td>{position.value_as_of ?? '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      {analysis.correlations.length > 0 && (
        <section className="risk-panel">
          <p className="section-kicker">CORRELATION</p>
          <h2>标的相关性</h2>
          <div className="correlation-list">
            {analysis.correlations.map((item) => (
              <div key={`${item.left_code}-${item.right_code}`}>
                <span>{item.left_code} / {item.right_code}</span>
                <strong>{item.value ?? '无法定义'}</strong>
              </div>
            ))}
          </div>
        </section>
      )}

      <section className="risk-panel risk-methodology">
        <p className="section-kicker">METHODOLOGY</p>
        <h2>计算假设与限制</h2>
        <ul>
          {analysis.assumptions.map((item) => <li key={item}>{item}</li>)}
          {analysis.limitations.map((item) => (
            <li key={item}>{limitationLabels[item] ?? item}</li>
          ))}
        </ul>
      </section>
    </main>
  )
}
