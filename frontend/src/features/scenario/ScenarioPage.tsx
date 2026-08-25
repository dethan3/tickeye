import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { type FormEvent, useState } from 'react'
import type {
  AssetClass,
  ScenarioComparisonResponse,
  ScenarioOperationType,
  ScenarioSideSchema,
} from '../../api/generated'
import { ApiError } from '../../api/request'
import { getPortfolio } from '../../api/portfolio'
import {
  addScenarioOperation,
  createScenario,
  getScenarioComparison,
  getScenarios,
} from '../../api/scenario'
import './ScenarioPage.css'

const operationLabels: Record<ScenarioOperationType, string> = {
  no_action: '不操作（NO_ACTION）',
  buy: '买入金额',
  sell: '卖出金额',
  set_amount: '调整到指定金额',
  set_target_weight: '调整到目标权重',
}

const assetLabels: Record<AssetClass, string> = {
  equity: '权益',
  fixed_income: '固收',
  mixed: '混合',
  cash: '现金',
  commodity: '商品',
  other: '其他',
}

const confidenceLabels = { low: '低', medium: '中', high: '高' }
const policyLabels = { unknown: '无法判断', within: '边界内', watch: '接近边界', breached: '已越界' }

function percent(value: string | null): string {
  return value === null ? '无法计算' : `${(Number(value) * 100).toFixed(2)}%`
}

function money(value: string | null): string {
  if (value === null) return '无法计算'
  return new Intl.NumberFormat('zh-CN', {
    style: 'currency', currency: 'CNY', maximumFractionDigits: 2,
  }).format(Number(value))
}

function cashWeight(side: ScenarioSideSchema): string | null {
  return side.analysis.asset_class_exposures.find((item) => item.key === 'cash')?.weight ?? '0'
}

function errorMessage(error: Error): string {
  return error instanceof ApiError && error.details[0]?.message
    ? error.details[0].message
    : error.message
}

function SideCard({ label, side }: { label: string; side: ScenarioSideSchema }) {
  const maximum = side.analysis.instrument_exposures[0]
  return <article className="scenario-side">
    <div className="scenario-side-heading"><span>{label}</span><strong>{policyLabels[side.policy.state]}</strong></div>
    <dl>
      <div><dt>组合已知市值</dt><dd>{money(side.analysis.coverage.known_portfolio_value)}</dd></div>
      <div><dt>最大单一标的</dt><dd>{maximum ? `${maximum.label} · ${percent(maximum.weight)}` : '—'}</dd></div>
      <div><dt>现金比例</dt><dd>{percent(cashWeight(side))}</dd></div>
      <div><dt>年化波动率</dt><dd>{percent(side.analysis.metrics.annualized_volatility)}</dd></div>
      <div><dt>下行波动率</dt><dd>{percent(side.analysis.metrics.downside_volatility)}</dd></div>
      <div><dt>模拟最大回撤</dt><dd>{percent(side.analysis.metrics.max_drawdown)}</dd></div>
      <div><dt>手工压力后市值</dt><dd>{money(side.stressed_value)}</dd></div>
      <div><dt>数据状态</dt><dd>{side.analysis.status === 'unknown' ? '信息不足' : '可比较'}</dd></div>
    </dl>
  </article>
}

export default function ScenarioPage() {
  const queryClient = useQueryClient()
  const scenarios = useQuery({ queryKey: ['scenarios'], queryFn: ({ signal }) => getScenarios(signal) })
  const portfolio = useQuery({ queryKey: ['portfolio'], queryFn: ({ signal }) => getPortfolio(signal) })
  const [selectedId, setSelectedId] = useState<number | null>(null)
  const [name, setName] = useState('')
  const [stressClass, setStressClass] = useState<AssetClass>('equity')
  const [stressDecline, setStressDecline] = useState('')
  const [operationType, setOperationType] = useState<ScenarioOperationType>('buy')
  const [instrumentId, setInstrumentId] = useState('')
  const [amount, setAmount] = useState('')
  const [targetWeight, setTargetWeight] = useState('')
  const [cost, setCost] = useState('')

  const activeId = selectedId ?? scenarios.data?.data.items[0]?.scenario_id ?? null

  const comparison = useQuery({
    queryKey: ['scenario', activeId, 'comparison'],
    queryFn: ({ signal }) => getScenarioComparison(activeId as number, signal),
    enabled: activeId !== null,
  })

  const create = useMutation({
    mutationFn: createScenario,
    onSuccess: (response) => {
      const id = response.data.scenario_id
      setSelectedId(id)
      queryClient.setQueryData<ScenarioComparisonResponse>(['scenario', id, 'comparison'], response)
      void queryClient.invalidateQueries({ queryKey: ['scenarios'] })
      setName('')
      setStressDecline('')
    },
  })

  const addOperation = useMutation({
    mutationFn: ({ id, payload }: { id: number; payload: Parameters<typeof addScenarioOperation>[1] }) =>
      addScenarioOperation(id, payload),
    onSuccess: (response) => {
      queryClient.setQueryData<ScenarioComparisonResponse>(
        ['scenario', response.data.scenario_id, 'comparison'], response,
      )
      void queryClient.invalidateQueries({ queryKey: ['scenarios'] })
      setAmount('')
      setTargetWeight('')
      setCost('')
    },
  })

  if (scenarios.isPending || portfolio.isPending) {
    return <main className="scenario-main"><p>正在读取风险方案…</p></main>
  }
  if (scenarios.isError || portfolio.isError) {
    return <main className="scenario-main"><div className="page-error"><h1>无法读取风险方案</h1></div></main>
  }

  const active = comparison.data?.data
  const instruments = Array.from(new Map([
    ...portfolio.data.data.positions
      .filter((item) => item.instrument_type !== 'cash')
      .map((item) => [item.instrument_id, { instrument_id: item.instrument_id, name: item.name, code: item.code }] as const),
    ...(active?.before.analysis.positions ?? [])
      .filter((item) => item.instrument_type !== 'cash')
      .map((item) => [item.instrument_id, { instrument_id: item.instrument_id, name: item.name, code: item.code }] as const),
  ]).values())
  const instrumentById = new Map(
    instruments.map((item) => [item.instrument_id, `${item.name} (${item.code})`]),
  )
  const needsInstrument = operationType !== 'no_action'
  const needsWeight = operationType === 'set_target_weight'
  const needsAmount = !needsWeight && operationType !== 'no_action'

  function submitCreate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    create.mutate({
      name,
      stress_assumptions: stressDecline
        ? [{ asset_class: stressClass, shock: String(-Number(stressDecline) / 100) }]
        : [],
    })
  }

  function submitOperation(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (activeId === null) return
    addOperation.mutate({
      id: activeId,
      payload: {
        operation_type: operationType,
        instrument_id: needsInstrument ? Number(instrumentId) : null,
        amount: needsAmount ? amount : null,
        target_weight: needsWeight ? String(Number(targetWeight) / 100) : null,
        estimated_cost: operationType === 'no_action' ? '0' : (cost || '0'),
      },
    })
  }

  return <main className="scenario-main">
    <div className="scenario-heading">
      <div><p className="eyebrow">操作前后风险比较</p><h1>风险方案模拟</h1><p>在实际持仓的临时副本上比较调整前后的风险。这里不模拟成交或收益，也不会修改你的实际持仓。</p></div>
      <span>{scenarios.data.coverage.scenario_count} 个风险方案</span>
    </div>

    <div className="scenario-layout">
      <aside className="scenario-sidebar">
        <section className="scenario-panel">
          <h2>已有风险方案</h2>
          {scenarios.data.data.items.length === 0 ? <p className="scenario-empty">还没有风险方案。</p> : <div className="scenario-list">
            {scenarios.data.data.items.map((item) => <button className={activeId === item.scenario_id ? 'active' : ''} type="button" key={item.scenario_id} onClick={() => setSelectedId(item.scenario_id)}><strong>{item.name}</strong><span>{item.operation_count} 个模拟调整 · 基于持仓版本 {item.base_portfolio_revision}{item.candidate_instrument_id ? ' · 含观察候选' : ''}</span></button>)}
          </div>}
        </section>

        <section className="scenario-panel">
          <h2>新建风险方案</h2>
          <form className="scenario-form" onSubmit={submitCreate}>
            <label>方案名称<input required maxLength={100} value={name} onChange={(event) => setName(event.target.value)} placeholder="例如：降低权益集中度" /></label>
            <label>可选压力对象<select value={stressClass} onChange={(event) => setStressClass(event.target.value as AssetClass)}>{Object.entries(assetLabels).map(([value, label]) => <option value={value} key={value}>{label}</option>)}</select></label>
            <label>假设下跌（%）<input min="0.01" max="99.99" step="0.01" type="number" value={stressDecline} onChange={(event) => setStressDecline(event.target.value)} placeholder="不填则不施加压力" /></label>
            <button className="primary-button" disabled={create.isPending} type="submit">{create.isPending ? '正在建立组合副本…' : '创建风险方案'}</button>
          </form>
          {create.isError && <p className="scenario-error" role="alert">{errorMessage(create.error)}</p>}
        </section>
      </aside>

      <div className="scenario-workspace">
        {activeId === null ? <section className="scenario-panel scenario-empty">创建风险方案后，可在同一数据窗口下比较调整前后的风险。</section> : comparison.isPending ? <p>正在读取比较结果…</p> : comparison.isError ? <div className="page-error"><h2>无法读取比较结果</h2></div> : active && <>
          <section className="scenario-panel scenario-overview">
            <div><p className="section-kicker">FROZEN EXPERIMENT</p><h2>{active.name}</h2><p>共同窗口 {active.comparison_window.start ?? '—'} 至 {active.comparison_window.end ?? '—'} · {active.comparison_window.observations} 个观测日 · 规则版本 {active.policy_revision}</p></div>
            <div><span>判断信息置信度</span><strong>{confidenceLabels[active.summary.confidence]}</strong><small>总估计成本 {money(active.total_estimated_cost)}</small></div>
          </section>

          <section className="scenario-panel">
            <h2>追加模拟调整</h2>
            <form className="scenario-operation-form" onSubmit={submitOperation}>
              <label>操作<select value={operationType} onChange={(event) => setOperationType(event.target.value as ScenarioOperationType)}>{Object.entries(operationLabels).map(([value, label]) => <option value={value} key={value}>{label}</option>)}</select></label>
              {needsInstrument && <label>标的<select required value={instrumentId} onChange={(event) => setInstrumentId(event.target.value)}><option value="">请选择</option>{instruments.map((item) => <option value={item.instrument_id} key={item.instrument_id}>{item.name} ({item.code})</option>)}</select></label>}
              {needsAmount && <label>金额（元）<input required min="0" step="0.01" type="number" value={amount} onChange={(event) => setAmount(event.target.value)} /></label>}
              {needsWeight && <label>目标权重（%）<input required min="0" max="100" step="0.01" type="number" value={targetWeight} onChange={(event) => setTargetWeight(event.target.value)} /></label>}
              {operationType !== 'no_action' && <label>估计交易成本（元）<input min="0" step="0.01" type="number" value={cost} onChange={(event) => setCost(event.target.value)} /></label>}
              <button className="primary-button" disabled={addOperation.isPending} type="submit">{addOperation.isPending ? '正在比较…' : '应用调整并比较风险'}</button>
            </form>
            {addOperation.isError && <p className="scenario-error" role="alert">{errorMessage(addOperation.error)}</p>}
            {active.operations.length > 0 && <ol className="scenario-operations">{active.operations.map((item) => <li key={item.sequence}><strong>{operationLabels[item.operation_type]}</strong><span>{item.instrument_id !== null ? (instrumentById.get(item.instrument_id) ?? `未知标的（ID ${item.instrument_id}）`) : '不操作基线'}{item.amount !== null ? ` · ${money(item.amount)}` : ''}{item.target_weight !== null ? ` · ${percent(item.target_weight)}` : ''} · 成本 {money(item.estimated_cost)}</span></li>)}</ol>}
          </section>

          <section className="scenario-comparison"><SideCard label="保持不变 / 调整前" side={active.before} /><SideCard label="模拟调整 / 调整后" side={active.after} /></section>

          <section className="scenario-judgment">
            <article className="scenario-panel"><h2>改善项</h2>{active.summary.improvements.length ? <ul>{active.summary.improvements.map((item) => <li key={item}>{item}</li>)}</ul> : <p>没有确认的改善项。</p>}</article>
            <article className="scenario-panel"><h2>恶化项</h2>{active.summary.worsenings.length ? <ul>{active.summary.worsenings.map((item) => <li key={item}>{item}</li>)}</ul> : <p>没有确认的恶化项。</p>}</article>
            <article className="scenario-panel scenario-objections"><h2>主要反对理由</h2><ul>{active.summary.objections.map((item) => <li key={item}>{item}</li>)}</ul></article>
          </section>
          <section className="scenario-warnings">{active.warnings.map((item) => <p key={item}>{item}</p>)}</section>
        </>}
      </div>
    </div>
  </main>
}
