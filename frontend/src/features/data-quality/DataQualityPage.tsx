import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import type {
  DataQualityItemSchema,
  DataQualityResponse,
  DataQualityStatus,
  MarketValueType,
} from '../../api/generated'
import { getDataQuality, refreshMarketData } from '../../api/marketData'
import './DataQualityPage.css'

const statusLabels: Record<DataQualityStatus, string> = {
  good: '可用',
  partial: '部分数据',
  stale: '数据陈旧',
  missing: '尚无数据',
  refresh_failed: '刷新失败',
  short_history: '样本不足',
  not_applicable: '无需行情',
}

const valueTypeLabels: Record<MarketValueType, string> = {
  cumulative_nav: '累计净值',
  unit_nav: '单位净值',
  adjusted_close: '前复权收盘价',
  index_close: '指数收盘点位',
}

const limitationLabels: Record<string, string> = {
  qfq_history_can_be_revised: '前复权历史会随分红送配重新计算',
  unit_nav_only: '数据源未提供累计净值，本次使用单位净值',
  invalid_stored_limitations: '历史限制说明无法解析',
}

function formatTimestamp(value: string | null): string {
  if (value === null) return '从未刷新'
  return new Intl.DateTimeFormat('zh-CN', {
    dateStyle: 'medium',
    timeStyle: 'short',
  }).format(new Date(value))
}

function freshnessText(item: DataQualityItemSchema): string {
  if (item.freshness_days === null) return '—'
  if (item.freshness_days === 0) return '今天'
  return `${item.freshness_days} 天前`
}

function qualityExplanation(item: DataQualityItemSchema): string {
  switch (item.status) {
    case 'good':
      return '数据量与新鲜度满足当前分析要求。'
    case 'partial':
      return '本次数据中存在被拒绝的异常记录，分析时需注意覆盖率。'
    case 'stale':
      return `最后数据已超过 ${item.freshness_limit_days ?? '允许'} 天的新鲜度阈值。`
    case 'missing':
      return '还没有成功取得这个标的的市场数据。'
    case 'refresh_failed':
      return item.failure_message ?? '最近一次刷新失败，仍保留此前的有效数据。'
    case 'short_history':
      return `当前只有 ${item.sample_count} 个样本，少于首版分析要求的 120 个。`
    case 'not_applicable':
      return '现金类资产不需要市场行情。'
  }
}

function QualityRow({ item }: { item: DataQualityItemSchema }) {
  const rejectedPercent =
    item.rejected_rate === null ? null : `${(Number(item.rejected_rate) * 100).toFixed(2)}%`

  return (
    <article className="quality-item">
      <div className="quality-identity">
        <div>
          <strong>{item.name}</strong>
          <span>{item.code}</span>
        </div>
        <span className={`quality-status quality-status--${item.status}`}>
          {statusLabels[item.status]}
        </span>
      </div>

      <p className="quality-explanation">{qualityExplanation(item)}</p>

      <dl className="quality-facts">
        <div>
          <dt>最新数据</dt>
          <dd>{item.last_observation_date ?? '—'}</dd>
        </div>
        <div>
          <dt>新鲜度</dt>
          <dd>{freshnessText(item)}</dd>
        </div>
        <div>
          <dt>样本数</dt>
          <dd>{item.sample_count}</dd>
        </div>
        <div>
          <dt>拒绝率</dt>
          <dd>{rejectedPercent ?? '—'}</dd>
        </div>
        <div>
          <dt>值与口径</dt>
          <dd>
            {item.latest_value ?? '—'}
            {item.value_type === null ? '' : ` · ${valueTypeLabels[item.value_type]}`}
          </dd>
        </div>
        <div>
          <dt>数据来源</dt>
          <dd>{item.source ?? '—'}</dd>
        </div>
      </dl>

      <div className="quality-footnote">
        <span>最近刷新：{formatTimestamp(item.last_refresh_at)}</span>
        {item.failure_code !== null && <span>错误代码：{item.failure_code}</span>}
      </div>
      {item.limitations.length > 0 && (
        <ul className="quality-limitations" aria-label={`${item.name} 数据限制`}>
          {item.limitations.map((limitation) => (
            <li key={limitation}>{limitationLabels[limitation] ?? limitation}</li>
          ))}
        </ul>
      )}
    </article>
  )
}

export default function DataQualityPage() {
  const queryClient = useQueryClient()
  const quality = useQuery({
    queryKey: ['market-data', 'quality'],
    queryFn: ({ signal }) => getDataQuality(signal),
  })
  const refresh = useMutation({
    mutationFn: () => refreshMarketData(),
    onSuccess: (response) => {
      queryClient.setQueryData<DataQualityResponse>(
        ['market-data', 'quality'],
        response.data.quality,
      )
    },
  })

  if (quality.isPending) {
    return <main className="quality-main"><p>正在检查本地市场数据…</p></main>
  }
  if (quality.isError) {
    return (
      <main className="quality-main">
        <div className="page-error">
          <h1>无法检查数据质量</h1>
          <p>{quality.error.message}</p>
          <button type="button" onClick={() => void quality.refetch()}>重新读取</button>
        </div>
      </main>
    )
  }

  const report = quality.data
  const refreshSummary = refresh.data?.data.results
  const succeeded = refreshSummary?.filter((item) => item.status === 'success').length ?? 0
  const failed = refreshSummary?.filter((item) => item.status === 'error').length ?? 0

  return (
    <main className="quality-main">
      <div className="quality-heading">
        <div>
          <p className="eyebrow">数据可信度</p>
          <h1>数据质量</h1>
          <p>风险判断之前，先确认数据是否存在、是否新鲜、是否足够完整。</p>
        </div>
        <button
          className="primary-button"
          type="button"
          disabled={refresh.isPending || report.coverage.tracked_count === 0}
          onClick={() => refresh.mutate()}
        >
          {refresh.isPending ? '正在刷新…' : '刷新全部行情'}
        </button>
      </div>

      <section className="quality-summary" aria-label="数据质量摘要">
        <div><span>跟踪标的</span><strong>{report.coverage.tracked_count}</strong></div>
        <div><span>已有数据</span><strong>{report.coverage.available_count}</strong></div>
        <div><span>需要关注</span><strong>{report.coverage.problem_count}</strong></div>
        <div><span>数据截至</span><strong>{report.as_of ?? '尚无数据'}</strong></div>
      </section>

      {refresh.isError && (
        <p className="quality-message quality-message--error" role="alert">
          刷新请求未完成：{refresh.error.message}
        </p>
      )}
      {refresh.isSuccess && (
        <p className="quality-message" role="status">
          刷新完成：{succeeded} 个成功，{failed} 个失败。失败不会删除已有数据。
        </p>
      )}
      {report.warnings.map((warning) => (
        <p className="quality-message quality-message--warning" key={warning}>{warning}</p>
      ))}

      {report.data.items.length === 0 ? (
        <section className="quality-empty">
          <h2>还没有需要检查的标的</h2>
          <p>先录入当前持仓或添加观察标的，系统才知道应该为哪些资产准备市场数据。</p>
          <Link to="/portfolio">录入持仓</Link> · <Link to="/watchlists">添加观察标的</Link>
        </section>
      ) : (
        <section className="quality-list" aria-label="各标的数据质量">
          {report.data.items.map((item) => (
            <QualityRow item={item} key={item.instrument_id} />
          ))}
        </section>
      )}
    </main>
  )
}
