import { useQuery } from '@tanstack/react-query'
import { getEvents } from '../../api/policy'
import './PolicyPage.css'

const eventLabels: Record<string, string> = {
  detected: '首次发现',
  state_changed: '状态变化',
  recovered: '恢复到边界内',
}

export default function EventPage() {
  const events = useQuery({ queryKey: ['events'], queryFn: ({ signal }) => getEvents(signal) })
  if (events.isPending) return <main className="policy-main"><p>正在读取风险事件…</p></main>
  if (events.isError) return <main className="policy-main"><div className="page-error"><h1>无法读取风险事件</h1></div></main>
  return <main className="policy-main">
    <div className="policy-heading"><div><p className="eyebrow">状态变化记录</p><h1>风险事件</h1><p>相同状态不会重复产生事件；这里只记录首次发现、真实变化和恢复。</p></div></div>
    {events.data.data.items.length === 0 ? <section className="policy-panel policy-empty">尚无风险事件。设置规则并重新计算后，重要状态变化会出现在这里。</section> : <section className="event-list">
      {events.data.data.items.map((event) => <article key={event.event_id} className={`event-card event-card--${event.to_state}`}>
        <div><span>{eventLabels[event.event_type] ?? event.event_type}</span><time>{new Date(event.occurred_at).toLocaleString('zh-CN')}</time></div>
        <h2>{event.finding.title}</h2><p>{event.finding.message}</p>
        <small>{event.from_state ?? '无历史状态'} → {event.to_state}</small>
      </article>)}
    </section>}
  </main>
}
