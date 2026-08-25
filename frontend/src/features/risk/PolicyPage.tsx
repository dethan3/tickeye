import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { type FormEvent, useState } from 'react'
import type {
  AssetClass,
  PolicyResponse,
  PolicyRuleInput,
  PolicyRuleType,
} from '../../api/generated'
import { getPolicies, replacePolicies } from '../../api/policy'
import { getPortfolio } from '../../api/portfolio'
import './PolicyPage.css'

const ruleLabels: Record<PolicyRuleType, string> = {
  instrument_max_weight: '单一标的上限',
  asset_class_max_weight: '资产类别上限',
  cash_min_weight: '现金最低比例',
  asset_class_target_weight: '资产类别目标配置',
}

const assetLabels: Record<AssetClass, string> = {
  equity: '权益',
  fixed_income: '固收',
  mixed: '混合',
  cash: '现金',
  commodity: '商品',
  other: '其他',
}

function ratio(value: string): string {
  return `${(Number(value) * 100).toFixed(1)}%`
}

function toRatio(value: string): string {
  return String(Number(value) / 100)
}

export default function PolicyPage() {
  const queryClient = useQueryClient()
  const policies = useQuery({ queryKey: ['policies'], queryFn: ({ signal }) => getPolicies(signal) })
  const portfolio = useQuery({ queryKey: ['portfolio'], queryFn: ({ signal }) => getPortfolio(signal) })
  const [ruleType, setRuleType] = useState<PolicyRuleType>('instrument_max_weight')
  const [subjectKey, setSubjectKey] = useState('')
  const [threshold, setThreshold] = useState('')
  const [tolerance, setTolerance] = useState('')
  const [warningRatio, setWarningRatio] = useState('')

  const save = useMutation({
    mutationFn: ({ revision, rules }: { revision: number; rules: PolicyRuleInput[] }) =>
      replacePolicies(revision, rules),
    onSuccess: (response) => {
      queryClient.setQueryData<PolicyResponse>(['policies'], response)
      void queryClient.invalidateQueries({ queryKey: ['risk', 'current'] })
      void queryClient.invalidateQueries({ queryKey: ['events'] })
      setThreshold('')
      setTolerance('')
    },
  })

  if (policies.isPending || portfolio.isPending) {
    return <main className="policy-main"><p>正在读取风险规则…</p></main>
  }
  if (policies.isError || portfolio.isError) {
    return <main className="policy-main"><div className="page-error"><h1>无法读取风险规则</h1></div></main>
  }

  const current = policies.data
  const rules = current.data.rules
  const instruments = Array.from(
    new Map(portfolio.data.data.positions.map((item) => [item.instrument_id, item])).values(),
  )
  const needsSubject = ruleType !== 'cash_min_weight'
  const instrumentRule = ruleType === 'instrument_max_weight'
  const targetRule = ruleType === 'asset_class_target_weight'

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const resolvedSubject = ruleType === 'cash_min_weight' ? 'cash' : subjectKey
    if (!resolvedSubject || !threshold || !warningRatio || (targetRule && !tolerance)) return
    const next: PolicyRuleInput[] = [
      ...rules.map((item) => ({
        id: item.id,
        rule_type: item.rule_type,
        subject_key: item.subject_key,
        threshold: item.threshold,
        tolerance: item.tolerance,
        warning_ratio: item.warning_ratio,
        enabled: item.enabled,
      })),
      {
        id: null,
        rule_type: ruleType,
        subject_key: resolvedSubject,
        threshold: toRatio(threshold),
        tolerance: targetRule ? toRatio(tolerance) : null,
        warning_ratio: toRatio(warningRatio),
        enabled: true,
      },
    ]
    save.mutate({ revision: current.data.revision, rules: next })
  }

  function remove(ruleId: number) {
    const next = rules
      .filter((item) => item.id !== ruleId)
      .map((item) => ({
        id: item.id,
        rule_type: item.rule_type,
        subject_key: item.subject_key,
        threshold: item.threshold,
        tolerance: item.tolerance,
        warning_ratio: item.warning_ratio,
        enabled: item.enabled,
      }))
    save.mutate({ revision: current.data.revision, rules: next })
  }

  return (
    <main className="policy-main">
      <div className="policy-heading">
        <div><p className="eyebrow">用户明确边界</p><h1>风险规则</h1><p>这里没有系统默认阈值。每一条边界都由你设置，并保留版本与评估历史。</p></div>
        <span>规则版本 {current.data.revision}</span>
      </div>

      <section className="policy-panel">
        <p className="section-kicker">CURRENT RULES</p><h2>当前规则</h2>
        {rules.length === 0 ? <div className="policy-empty">尚未设置规则；系统不会把当前组合解释为“边界内”。</div> : (
          <div className="policy-rule-list">
            {rules.map((rule) => (
              <article key={rule.id}>
                <div><strong>{ruleLabels[rule.rule_type]}</strong><span>{rule.subject_label}</span></div>
                <div><span>目标/边界</span><strong>{ratio(rule.threshold)}</strong></div>
                {rule.tolerance !== null && <div><span>允许偏离</span><strong>±{ratio(rule.tolerance)}</strong></div>}
                <div><span>关注缓冲</span><strong>{ratio(rule.warning_ratio)}</strong></div>
                <button type="button" disabled={save.isPending} onClick={() => remove(rule.id)}>删除</button>
              </article>
            ))}
          </div>
        )}
      </section>

      <section className="policy-panel">
        <p className="section-kicker">ADD RULE</p><h2>新增规则</h2>
        <form className="policy-form" onSubmit={submit}>
          <label>规则类型<select value={ruleType} onChange={(event) => { setRuleType(event.target.value as PolicyRuleType); setSubjectKey('') }}>
            {Object.entries(ruleLabels).map(([value, label]) => <option value={value} key={value}>{label}</option>)}
          </select></label>
          {needsSubject && <label>检查对象<select required value={subjectKey} onChange={(event) => setSubjectKey(event.target.value)}><option value="">请选择</option>
            {instrumentRule
              ? instruments.filter((item) => item.instrument_type !== 'cash').map((item) => <option value={item.instrument_id} key={item.instrument_id}>{item.name} ({item.code})</option>)
              : Object.entries(assetLabels).map(([value, label]) => <option value={value} key={value}>{label}</option>)}
          </select></label>}
          <label>{targetRule ? '目标权重（%）' : '边界（%）'}<input required min="0" max="100" step="0.01" type="number" value={threshold} onChange={(event) => setThreshold(event.target.value)} /></label>
          {targetRule && <label>允许偏离（%）<input required min="0.01" max="100" step="0.01" type="number" value={tolerance} onChange={(event) => setTolerance(event.target.value)} /></label>}
          <label>关注缓冲（%）<input required min="0.01" max="99.99" step="0.01" type="number" value={warningRatio} onChange={(event) => setWarningRatio(event.target.value)} /></label>
          <div className="policy-form-actions"><button className="primary-button" disabled={save.isPending} type="submit">{save.isPending ? '保存并重新评估…' : '保存规则并重新评估'}</button></div>
        </form>
        {save.isError && <p className="policy-error" role="alert">{save.error.message}</p>}
      </section>
    </main>
  )
}
