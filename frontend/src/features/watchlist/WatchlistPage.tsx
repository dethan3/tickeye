import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { type FormEvent, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import type {
  AssetClass,
  DataQualityResponse,
  InstrumentType,
  WatchlistItemInput,
  WatchlistItemSchema,
  WatchlistResponse,
} from '../../api/generated'
import { getDataQuality, refreshMarketData } from '../../api/marketData'
import { ApiError } from '../../api/request'
import { createScenario } from '../../api/scenario'
import {
  addWatchlistItem,
  createWatchlist,
  deleteWatchlist,
  getWatchlists,
  removeWatchlistItem,
  updateWatchlistItem,
} from '../../api/watchlist'
import './WatchlistPage.css'

const instrumentLabels: Partial<Record<InstrumentType, string>> = {
  fund: '公募基金',
  qdii_fund: 'QDII 基金',
  etf: 'ETF',
}

const assetLabels: Record<AssetClass, string> = {
  equity: '权益', fixed_income: '固收', mixed: '混合', cash: '现金',
  commodity: '商品', other: '其他',
}

const qualityLabels = {
  good: '行情可用', partial: '部分数据', stale: '行情陈旧', missing: '缺少行情',
  refresh_failed: '刷新失败', short_history: '样本不足', not_applicable: '无需行情',
}

function errorMessage(error: Error): string {
  return error instanceof ApiError && error.details[0]?.message
    ? error.details[0].message
    : error.message
}

function tags(value: string): string[] {
  return value.split(/[,，]/).map((item) => item.trim()).filter(Boolean)
}

function ItemCard({
  item,
  watchlistId,
  qualityStatus,
  onResponse,
}: {
  item: WatchlistItemSchema
  watchlistId: number
  qualityStatus?: keyof typeof qualityLabels
  onResponse: (response: WatchlistResponse) => void
}) {
  const queryClient = useQueryClient()
  const navigate = useNavigate()
  const [editing, setEditing] = useState(false)
  const [reason, setReason] = useState(item.reason ?? '')
  const [tagText, setTagText] = useState(item.tags.join('，'))

  const update = useMutation({
    mutationFn: () => updateWatchlistItem(watchlistId, item.item_id, {
      reason: reason || null,
      tags: tags(tagText),
    }),
    onSuccess: (response) => { onResponse(response); setEditing(false) },
  })
  const remove = useMutation({
    mutationFn: () => removeWatchlistItem(watchlistId, item.item_id),
    onSuccess: onResponse,
  })
  const refresh = useMutation({
    mutationFn: () => refreshMarketData([item.instrument_id]),
    onSuccess: (response) => {
      queryClient.setQueryData<DataQualityResponse>(
        ['market-data', 'quality'], response.data.quality,
      )
    },
  })
  const scenario = useMutation({
    mutationFn: () => createScenario({
      name: `${item.name} 风险调整模拟`,
      candidate_instrument_id: item.instrument_id,
      stress_assumptions: [],
    }),
    onSuccess: (response) => {
      queryClient.setQueryData(
        ['scenario', response.data.scenario_id, 'comparison'], response,
      )
      void queryClient.invalidateQueries({ queryKey: ['scenarios'] })
      navigate('/scenarios')
    },
  })

  const mutationError = update.error ?? remove.error ?? refresh.error ?? scenario.error
  return <article className="watch-item">
    <div className="watch-item-heading">
      <div><strong>{item.name}</strong><span>{item.code} · {item.market} · {assetLabels[item.asset_class]}</span></div>
      <div className="watch-badges">
        {item.held && <span className="held">已持有</span>}
        <span>{qualityStatus ? qualityLabels[qualityStatus] : '质量读取中'}</span>
      </div>
    </div>
    {editing ? <div className="watch-edit">
      <label>观察理由<textarea maxLength={1000} value={reason} onChange={(event) => setReason(event.target.value)} /></label>
      <label>标签（逗号分隔）<input value={tagText} onChange={(event) => setTagText(event.target.value)} /></label>
      <div><button type="button" onClick={() => update.mutate()} disabled={update.isPending}>保存</button><button type="button" onClick={() => setEditing(false)}>取消</button></div>
    </div> : <>
      <p className="watch-reason">{item.reason ?? '尚未填写观察理由。'}</p>
      {item.tags.length > 0 && <div className="watch-tags">{item.tags.map((tag) => <span key={tag}>{tag}</span>)}</div>}
    </>}
    <div className="watch-actions">
      <button type="button" onClick={() => refresh.mutate()} disabled={refresh.isPending}>{refresh.isPending ? '刷新中…' : '刷新行情'}</button>
      <button className="primary-button" type="button" onClick={() => scenario.mutate()} disabled={scenario.isPending}>{scenario.isPending ? '正在建立副本…' : '模拟调整风险'}</button>
      <button type="button" onClick={() => setEditing(true)}>编辑</button>
      <button className="danger-button" type="button" onClick={() => remove.mutate()} disabled={remove.isPending}>移除</button>
    </div>
    {mutationError && <p className="watch-error" role="alert">{errorMessage(mutationError)}</p>}
    <small>风险方案只使用当前组合的临时副本，不会修改实际持仓；是否交易仍由你判断。</small>
  </article>
}

const emptyDraft: WatchlistItemInput = {
  code: '', name: '', instrument_type: 'fund', market: 'CN', currency: 'CNY',
  asset_class: 'equity', region: '中国', reason: null, tags: [],
}

export default function WatchlistPage() {
  const queryClient = useQueryClient()
  const watchlists = useQuery({ queryKey: ['watchlists'], queryFn: ({ signal }) => getWatchlists(signal) })
  const quality = useQuery({ queryKey: ['market-data', 'quality'], queryFn: ({ signal }) => getDataQuality(signal) })
  const [selectedId, setSelectedId] = useState<number | null>(null)
  const [groupName, setGroupName] = useState('')
  const [draft, setDraft] = useState<WatchlistItemInput>(emptyDraft)
  const [draftTags, setDraftTags] = useState('')
  const selectedExists = watchlists.data?.data.items.some(
    (item) => item.watchlist_id === selectedId,
  )
  const activeId = selectedExists
    ? selectedId
    : watchlists.data?.data.items[0]?.watchlist_id ?? null

  function accept(response: WatchlistResponse) {
    queryClient.setQueryData(['watchlists'], response)
    void queryClient.invalidateQueries({ queryKey: ['market-data', 'quality'] })
  }

  const createGroup = useMutation({
    mutationFn: () => createWatchlist({ name: groupName }),
    onSuccess: (response) => {
      accept(response)
      const created = response.data.items.find((item) => item.name === groupName.trim())
      if (created) setSelectedId(created.watchlist_id)
      setGroupName('')
    },
  })
  const deleteGroup = useMutation({
    mutationFn: (id: number) => deleteWatchlist(id),
    onSuccess: (response) => { accept(response); setSelectedId(null) },
  })
  const addItem = useMutation({
    mutationFn: ({ id, item }: { id: number; item: WatchlistItemInput }) => addWatchlistItem(id, item),
    onSuccess: (response) => { accept(response); setDraft(emptyDraft); setDraftTags('') },
  })

  if (watchlists.isPending) return <main className="watch-main"><p>正在读取观察列表…</p></main>
  if (watchlists.isError) return <main className="watch-main"><div className="page-error"><h1>无法读取观察列表</h1><p>{watchlists.error.message}</p><button type="button" onClick={() => void watchlists.refetch()}>重新读取</button></div></main>

  const active = watchlists.data.data.items.find((item) => item.watchlist_id === activeId)
  const qualityByInstrument = new Map(quality.data?.data.items.map((item) => [item.instrument_id, item.status]))

  function submitGroup(event: FormEvent) {
    event.preventDefault()
    createGroup.mutate()
  }
  function submitItem(event: FormEvent) {
    event.preventDefault()
    if (activeId === null) return
    addItem.mutate({ id: activeId, item: { ...draft, tags: tags(draftTags) } })
  }

  return <main className="watch-main">
    <div className="watch-heading"><div><p className="eyebrow">USER-CURATED CANDIDATES</p><h1>观察列表</h1><p>记录你想持续关注的标的、理由和标签。这里没有平台推荐、机会排名或买入结论。</p></div><span>{watchlists.data.coverage.item_count} 个观察标的</span></div>
    {watchlists.data.warnings.map((warning) => <p className="watch-notice" key={warning}>{warning}</p>)}
    <div className="watch-layout">
      <aside className="watch-sidebar">
        <form className="watch-group-form" onSubmit={submitGroup}><label>新分组<input required maxLength={100} value={groupName} onChange={(event) => setGroupName(event.target.value)} placeholder="例如：等待回调" /></label><button className="primary-button" disabled={createGroup.isPending} type="submit">创建</button></form>
        {createGroup.isError && <p className="watch-error" role="alert">{errorMessage(createGroup.error)}</p>}
        <div className="watch-group-list">{watchlists.data.data.items.map((group) => <button className={group.watchlist_id === activeId ? 'active' : ''} type="button" key={group.watchlist_id} onClick={() => setSelectedId(group.watchlist_id)}><strong>{group.name}</strong><span>{group.items.length} 个标的</span></button>)}</div>
      </aside>
      <div className="watch-workspace">
        {!active ? <section className="watch-empty"><h2>先创建一个观察分组</h2><p>观察列表和实际持仓彼此隔离，加入候选不会改变你的风险快照。</p></section> : <>
          <section className="watch-panel watch-group-heading"><div><p className="section-kicker">WATCHLIST</p><h2>{active.name}</h2></div><button className="danger-button" type="button" disabled={deleteGroup.isPending} onClick={() => deleteGroup.mutate(active.watchlist_id)}>删除分组</button></section>
          <section className="watch-panel"><h2>添加观察标的</h2><form className="watch-item-form" onSubmit={submitItem}>
            <label>代码<input required value={draft.code} onChange={(event) => setDraft({ ...draft, code: event.target.value })} placeholder="例如 159915" /></label>
            <label>名称<input required value={draft.name} onChange={(event) => setDraft({ ...draft, name: event.target.value })} /></label>
            <label>类型<select value={draft.instrument_type} onChange={(event) => setDraft({ ...draft, instrument_type: event.target.value as InstrumentType })}>{Object.entries(instrumentLabels).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label>
            <label>资产类别<select value={draft.asset_class} onChange={(event) => setDraft({ ...draft, asset_class: event.target.value as AssetClass })}>{Object.entries(assetLabels).filter(([value]) => value !== 'cash').map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label>
            <label>市场<input required value={draft.market} onChange={(event) => setDraft({ ...draft, market: event.target.value })} /></label>
            <label>地区<input required value={draft.region} onChange={(event) => setDraft({ ...draft, region: event.target.value })} /></label>
            <label className="wide">观察理由<textarea maxLength={1000} value={draft.reason ?? ''} onChange={(event) => setDraft({ ...draft, reason: event.target.value || null })} placeholder="你为什么关注它？什么信息会改变你的判断？" /></label>
            <label className="wide">标签<input value={draftTags} onChange={(event) => setDraftTags(event.target.value)} placeholder="候选，成长，等待回调" /></label>
            <button className="primary-button wide" disabled={addItem.isPending} type="submit">{addItem.isPending ? '正在添加…' : '加入当前分组'}</button>
          </form>{addItem.isError && <p className="watch-error" role="alert">{errorMessage(addItem.error)}</p>}</section>
          {active.items.length === 0 ? <section className="watch-empty"><h2>当前分组还是空的</h2><p>添加由你选定的候选标的，行情质量会同时纳入检查。</p></section> : <section className="watch-items">{active.items.map((item) => <ItemCard item={item} watchlistId={active.watchlist_id} qualityStatus={qualityByInstrument.get(item.instrument_id)} onResponse={accept} key={item.item_id} />)}</section>}
        </>}
      </div>
    </div>
  </main>
}
