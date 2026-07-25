import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { Check } from 'lucide-react'
import clsx from 'clsx'
import { remindersApi } from '../api/client'
import type { Reminder } from '../types'
import { Card } from '../components/Card'
import { formatDateOnly, isPastDateOnly } from '../lib/date'

type StatusFilter = 'pending' | 'overdue' | 'done'

export function RemindersPage() {
  const [status, setStatus] = useState<StatusFilter>('pending')
  const [reminders, setReminders] = useState<Reminder[]>([])

  function load() {
    remindersApi.listGlobal(status).then(setReminders)
  }

  useEffect(load, [status])

  async function toggle(r: Reminder) {
    await remindersApi.update(r.id, { is_done: !r.is_done })
    load()
  }

  const isOverdue = (r: Reminder) => !r.is_done && isPastDateOnly(r.due_date)

  return (
    <div className="mx-auto max-w-3xl space-y-6 p-8">
      <div>
        <h1 className="text-2xl font-semibold text-text">Lembretes</h1>
        <p className="text-sm text-muted">Follow-ups com seus contatos.</p>
      </div>

      <div className="flex gap-2">
        {(['pending', 'overdue', 'done'] as StatusFilter[]).map((s) => (
          <button
            key={s}
            onClick={() => setStatus(s)}
            className={clsx(
              'rounded-full px-3 py-1 text-xs font-medium',
              status === s ? 'bg-accent text-white' : 'bg-accent-soft text-accent',
            )}
          >
            {s === 'pending' ? 'Pendentes' : s === 'overdue' ? 'Atrasados' : 'Concluídos'}
          </button>
        ))}
      </div>

      <Card>
        <ul className="space-y-2">
          {reminders.map((r) => (
            <li key={r.id} className="flex items-center gap-3 rounded-lg border border-border px-3 py-2">
              <button
                onClick={() => toggle(r)}
                className={clsx(
                  'flex h-5 w-5 items-center justify-center rounded-full border',
                  r.is_done ? 'border-accent bg-accent text-white' : 'border-border',
                )}
              >
                {r.is_done && <Check size={12} />}
              </button>
              <Link to={`/contacts/${r.contact_id}`} className="flex-1">
                <div className={clsx('text-sm', r.is_done ? 'text-muted line-through' : 'text-text')}>
                  {r.note || 'Follow-up'}
                </div>
              </Link>
              <span className={clsx('text-xs', isOverdue(r) ? 'font-medium text-red-500' : 'text-muted')}>
                {formatDateOnly(r.due_date)}
              </span>
            </li>
          ))}
          {reminders.length === 0 && <p className="text-sm text-muted">Nada por aqui.</p>}
        </ul>
      </Card>
    </div>
  )
}
