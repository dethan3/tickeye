import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { type FormEvent, useRef, useState } from 'react'
import {
  confirmPortfolioCsv,
  getPortfolio,
  previewPortfolioCsv,
  replacePositions,
} from '../../api/portfolio'
import { ApiError } from '../../api/request'
import type {
  AssetClass,
  InstrumentType,
  PortfolioResponse,
  PositionInputSchemaInput,
  PositionSchema,
} from '../../api/generated'
import './PortfolioPage.css'

type PositionForm = {
  id: number | null
  accountName: string
  institution: string
  code: string
  name: string
  instrumentType: InstrumentType
  market: string
  assetClass: AssetClass
  region: string
  quantity: string
  manualValue: string
  cost: string
  asOf: string
}

type SavePositionsRequest = {
  expectedRevision: number
  positions: PositionInputSchemaInput[]
  successMessage: string
}

const instrumentLabels: Record<InstrumentType, string> = {
  fund: '基金',
  etf: 'ETF',
  qdii_fund: 'QDII 基金',
  cash: '现金',
}

const assetClassLabels: Record<AssetClass, string> = {
  equity: '权益',
  fixed_income: '固收',
  mixed: '混合',
  cash: '现金',
  commodity: '商品',
  other: '其他',
}

function localToday(): string {
  const now = new Date()
  const local = new Date(now.getTime() - now.getTimezoneOffset() * 60_000)
  return local.toISOString().slice(0, 10)
}

function emptyForm(): PositionForm {
  return {
    id: null,
    accountName: '',
    institution: '',
    code: '',
    name: '',
    instrumentType: 'fund',
    market: 'CN',
    assetClass: 'equity',
    region: '中国',
    quantity: '',
    manualValue: '',
    cost: '',
    asOf: localToday(),
  }
}

function formFromPosition(position: PositionSchema): PositionForm {
  return {
    id: position.id,
    accountName: position.account_name,
    institution: position.institution ?? '',
    code: position.code,
    name: position.name,
    instrumentType: position.instrument_type,
    market: position.market,
    assetClass: position.asset_class,
    region: position.region,
    quantity: position.quantity ?? '',
    manualValue: position.manual_value ?? '',
    cost: position.cost ?? '',
    asOf: position.as_of,
  }
}

function inputFromForm(form: PositionForm): PositionInputSchemaInput {
  return {
    id: form.id,
    account_name: form.accountName,
    institution: form.institution || null,
    account_currency: 'CNY',
    code: form.code,
    name: form.name,
    instrument_type: form.instrumentType,
    market: form.market,
    instrument_currency: 'CNY',
    asset_class: form.assetClass,
    region: form.region,
    quantity: form.quantity || null,
    manual_value: form.manualValue || null,
    cost: form.cost || null,
    as_of: form.asOf,
  }
}

function inputFromPosition(position: PositionSchema): PositionInputSchemaInput {
  return {
    id: position.id,
    account_name: position.account_name,
    institution: position.institution,
    account_currency: position.account_currency,
    code: position.code,
    name: position.name,
    instrument_type: position.instrument_type,
    market: position.market,
    instrument_currency: position.instrument_currency,
    asset_class: position.asset_class,
    region: position.region,
    quantity: position.quantity,
    manual_value: position.manual_value,
    cost: position.cost,
    as_of: position.as_of,
  }
}

function errorMessage(error: Error | null): string | null {
  if (error === null) return null
  if (error instanceof ApiError && error.details.length > 0) {
    return error.details.map((detail) => detail.message).join('；')
  }
  return error.message
}

export default function PortfolioPage() {
  const queryClient = useQueryClient()
  const portfolio = useQuery({
    queryKey: ['portfolio'],
    queryFn: ({ signal }) => getPortfolio(signal),
  })
  const [form, setForm] = useState<PositionForm>(emptyForm)
  const [formError, setFormError] = useState<string | null>(null)
  const [pendingDelete, setPendingDelete] = useState<number | null>(null)
  const [csvContent, setCsvContent] = useState('')
  const [csvName, setCsvName] = useState('')
  const [actionMessage, setActionMessage] = useState<string | null>(null)
  const editorRef = useRef<HTMLElement>(null)
  const accountInputRef = useRef<HTMLInputElement>(null)

  const savePositions = useMutation({
    mutationFn: ({
      expectedRevision,
      positions,
    }: SavePositionsRequest) => replacePositions(expectedRevision, positions),
    onSuccess: (response, request) => {
      queryClient.setQueryData<PortfolioResponse>(['portfolio'], response)
      setForm(emptyForm())
      setFormError(null)
      setPendingDelete(null)
      setActionMessage(request.successMessage)
    },
  })

  const csvPreview = useMutation({
    mutationFn: previewPortfolioCsv,
  })
  const csvConfirm = useMutation({
    mutationFn: ({ token, revision }: { token: string; revision: number }) =>
      confirmPortfolioCsv(csvContent, token, revision),
    onSuccess: (response) => {
      queryClient.setQueryData<PortfolioResponse>(['portfolio'], response.portfolio)
      setCsvContent('')
      setCsvName('')
      csvPreview.reset()
      setActionMessage(
        `CSV 已导入 ${response.portfolio.coverage.position_count} 条持仓。下一步可以刷新行情并生成风险快照。`,
      )
    },
  })

  if (portfolio.isPending) {
    return <main className="portfolio-main"><p>正在读取本地持仓…</p></main>
  }
  if (portfolio.isError) {
    return (
      <main className="portfolio-main">
        <div className="page-error">
          <h1>无法读取持仓</h1>
          <p>{portfolio.error.message}</p>
          <button type="button" onClick={() => void portfolio.refetch()}>重新读取</button>
        </div>
      </main>
    )
  }

  const current = portfolio.data
  const positions = current.data.positions

  function openEditor(nextForm: PositionForm, message: string) {
    setForm(nextForm)
    setFormError(null)
    setPendingDelete(null)
    setActionMessage(message)
    editorRef.current?.scrollIntoView?.({ behavior: 'smooth', block: 'start' })
    accountInputRef.current?.focus()
  }

  function startNewPosition() {
    openEditor(emptyForm(), '新增持仓表单已准备好，请从账户名称开始填写。')
  }

  function submitPosition(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!form.quantity && !form.manualValue) {
      setFormError('数量和手工市值至少填写一项。')
      return
    }
    const next = positions
      .filter((item) => item.id !== form.id)
      .map(inputFromPosition)
    next.push(inputFromForm(form))
    savePositions.mutate({
      expectedRevision: current.data.revision,
      positions: next,
      successMessage: form.id
        ? '持仓已更新并生成新快照。下一步可以刷新行情或重新计算风险。'
        : '持仓已新增并生成快照。继续补全其他持仓，或前往数据质量页刷新行情。',
    })
  }

  function confirmDelete(positionId: number) {
    const next = positions
      .filter((item) => item.id !== positionId)
      .map(inputFromPosition)
    savePositions.mutate({
      expectedRevision: current.data.revision,
      positions: next,
      successMessage: '持仓已删除并生成新快照。已有风险结果会标记为过期。',
    })
  }

  async function selectCsvFile(file: File | undefined) {
    if (file === undefined) return
    const content = await file.text()
    setCsvName(file.name)
    setCsvContent(content)
    csvPreview.reset()
    csvConfirm.reset()
  }

  return (
    <main className="portfolio-main">
      <div className="portfolio-heading">
        <div>
          <p className="eyebrow">资产事实</p>
          <h1>我的持仓</h1>
          <p>先准确记录现在拥有什么；这些事实将成为后续风险判断的基础。</p>
        </div>
        <div className="revision-badge">版本 {current.data.revision}</div>
      </div>

      <section className="portfolio-summary" aria-label="持仓摘要">
        <div><span>账户</span><strong>{current.coverage.account_count}</strong></div>
        <div><span>持仓</span><strong>{current.coverage.position_count}</strong></div>
        <div><span>最新日期</span><strong>{current.as_of ?? '尚无数据'}</strong></div>
      </section>

      {actionMessage && <p className="portfolio-action-message" role="status">{actionMessage}</p>}

      <section className="portfolio-section">
        <div className="section-heading">
          <div><p className="section-kicker">CURRENT POSITIONS</p><h2>当前持仓</h2></div>
          <button className="secondary-button" type="button" onClick={startNewPosition}>
            新增持仓
          </button>
        </div>

        {positions.length === 0 ? (
          <div className="empty-state">
            <h3>还没有持仓数据</h3>
            <p>风险分析目前只能返回“信息不足”。建议至少录入现金和一个投资标的，也可以使用 CSV 一次导入。</p>
            <button className="primary-button" type="button" onClick={startNewPosition}>填写第一条持仓</button>
          </div>
        ) : (
          <div className="position-table-wrap">
            <table className="position-table">
              <thead><tr><th>标的</th><th>账户</th><th>数量</th><th>手工市值</th><th>日期</th><th><span className="sr-only">操作</span></th></tr></thead>
              <tbody>
                {positions.map((position) => (
                  <tr key={position.id}>
                    <td><strong>{position.name}</strong><span>{position.code} · {instrumentLabels[position.instrument_type]}</span></td>
                    <td>{position.account_name}</td>
                    <td>{position.quantity ?? '—'}</td>
                    <td>{position.manual_value ? `¥ ${position.manual_value}` : '—'}</td>
                    <td>{position.as_of}</td>
                    <td className="row-actions">
                      <button type="button" onClick={() => openEditor(formFromPosition(position), `正在编辑 ${position.name}，保存后会生成新的持仓快照。`)}>编辑</button>
                      {pendingDelete === position.id ? (
                        <><button className="danger-link" type="button" onClick={() => confirmDelete(position.id)}>确认删除</button><button type="button" onClick={() => setPendingDelete(null)}>取消</button></>
                      ) : <button type="button" onClick={() => setPendingDelete(position.id)}>删除</button>}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      <section className="portfolio-section editor-section" ref={editorRef}>
        <div className="section-heading"><div><p className="section-kicker">MANUAL ENTRY</p><h2>{form.id ? '编辑持仓' : '手工添加'}</h2></div></div>
        <form className="position-form" onSubmit={submitPosition}>
          <label>账户名称<input ref={accountInputRef} required value={form.accountName} onChange={(e) => setForm({ ...form, accountName: e.target.value })} placeholder="例如：长期账户" /></label>
          <label>机构（可选）<input value={form.institution} onChange={(e) => setForm({ ...form, institution: e.target.value })} placeholder="例如：手工录入" /></label>
          <label>标的代码<input required value={form.code} onChange={(e) => setForm({ ...form, code: e.target.value })} placeholder="例如：510300" /></label>
          <label>标的名称<input required value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} placeholder="例如：沪深300ETF" /></label>
          <label>标的类型<select value={form.instrumentType} onChange={(e) => setForm({ ...form, instrumentType: e.target.value as InstrumentType })}>{Object.entries(instrumentLabels).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label>
          <label>资产类别<select value={form.assetClass} onChange={(e) => setForm({ ...form, assetClass: e.target.value as AssetClass })}>{Object.entries(assetClassLabels).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label>
          <label>市场<input required value={form.market} onChange={(e) => setForm({ ...form, market: e.target.value })} placeholder="CN" /></label>
          <label>地区<input required value={form.region} onChange={(e) => setForm({ ...form, region: e.target.value })} placeholder="中国" /></label>
          <label>数量<input min="0" step="any" type="number" value={form.quantity} onChange={(e) => setForm({ ...form, quantity: e.target.value })} /></label>
          <label>手工市值（元）<input min="0" step="0.01" type="number" value={form.manualValue} onChange={(e) => setForm({ ...form, manualValue: e.target.value })} /></label>
          <label>成本（可选）<input min="0" step="0.01" type="number" value={form.cost} onChange={(e) => setForm({ ...form, cost: e.target.value })} /></label>
          <label>持仓日期<input required type="date" max={localToday()} value={form.asOf} onChange={(e) => setForm({ ...form, asOf: e.target.value })} /></label>
          <div className="form-actions">
            <button className="primary-button" type="submit" disabled={savePositions.isPending}>{savePositions.isPending ? '正在保存…' : '保存并创建快照'}</button>
            {form.id && <button className="secondary-button" type="button" onClick={() => setForm(emptyForm())}>取消编辑</button>}
          </div>
          {(formError || savePositions.error) && <p className="form-error" role="alert">{formError ?? errorMessage(savePositions.error)}</p>}
        </form>
      </section>

      <section className="portfolio-section csv-section">
        <div className="section-heading"><div><p className="section-kicker">STRICT IMPORT</p><h2>CSV 预览导入</h2></div></div>
        <p className="section-description">确认导入会用 CSV 中的完整列表替换当前持仓。系统会先检查字段、日期、重复行和未知标的，不会静默跳过错误。</p>
        <label className="file-picker"><span>{csvName || '选择 CSV 文件'}</span><input type="file" accept=".csv,text/csv" onChange={(event) => void selectCsvFile(event.target.files?.[0])} /></label>
        <p className="csv-columns">必需列：account、code、market、as_of。新标的还需 name、type、currency、asset_class、region，并填写 quantity 或 manual_value。</p>
        <button className="secondary-button" type="button" disabled={!csvContent || csvPreview.isPending} onClick={() => csvPreview.mutate(csvContent)}>{csvPreview.isPending ? '正在校验…' : '预览并校验'}</button>

        {csvPreview.data && (
          <div className={`preview-result ${csvPreview.data.data.valid ? 'preview-result--ok' : 'preview-result--error'}`}>
            <h3>{csvPreview.data.data.valid ? `可导入 ${csvPreview.data.data.positions.length} 条持仓` : '需要修正后再导入'}</h3>
            {csvPreview.data.data.duplicate_import && <p>这个 CSV 批次已经确认导入过。</p>}
            {csvPreview.data.data.issues.length > 0 && <ul>{csvPreview.data.data.issues.map((issue, index) => <li key={`${issue.code}-${index}`}>{issue.row ? `第 ${issue.row} 行：` : ''}{issue.message}</li>)}</ul>}
            {csvPreview.data.data.valid && (
              <button className="primary-button" type="button" disabled={csvConfirm.isPending} onClick={() => csvConfirm.mutate({ token: csvPreview.data.data.preview_token, revision: current.data.revision })}>{csvConfirm.isPending ? '正在导入…' : '确认替换当前持仓'}</button>
            )}
          </div>
        )}
        {(csvPreview.error || csvConfirm.error) && <p className="form-error" role="alert">{errorMessage(csvPreview.error ?? csvConfirm.error)}</p>}
      </section>
    </main>
  )
}
