import { useEffect, useRef, useState } from 'react'
import { fmtFull, parseAmount } from '../lib/format'

interface NumberCellProps {
  value: number
  isSet: boolean // a rep explicitly entered this (vs derived/zero)
  signed?: boolean
  emphasis?: boolean
  onSave: (value: number | null) => Promise<void>
}

/** Click-to-edit numeric cell. Enter/blur saves, Esc cancels, empty clears. */
export function EditableNumberCell({ value, isSet, signed, emphasis, onSave }: NumberCellProps) {
  const [editing, setEditing] = useState(false)
  const [text, setText] = useState('')
  const [saving, setSaving] = useState(false)
  const inputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    if (editing) inputRef.current?.select()
  }, [editing])

  const start = () => {
    setText(value === 0 && !isSet ? '' : String(Math.round(value)))
    setEditing(true)
  }

  const commit = async () => {
    const parsed = parseAmount(text)
    setEditing(false)
    if (parsed !== null && Number.isNaN(parsed)) return
    const unchanged =
      (parsed === null && !isSet) || (parsed !== null && Math.round(parsed) === Math.round(value) && isSet)
    if (unchanged) return
    setSaving(true)
    try {
      await onSave(parsed)
    } finally {
      setSaving(false)
    }
  }

  if (editing) {
    return (
      <input
        ref={inputRef}
        className="tnum w-full rounded border border-brand bg-surface px-2 py-1 text-right text-sm outline-none"
        value={text}
        onChange={(e) => setText(e.target.value)}
        onBlur={commit}
        onKeyDown={(e) => {
          if (e.key === 'Enter') commit()
          if (e.key === 'Escape') setEditing(false)
        }}
        placeholder="0 · supports 1.2M / 500K"
      />
    )
  }

  const toneClass = signed
    ? value < 0
      ? 'text-neg'
      : value > 0
        ? 'text-pos'
        : 'text-muted'
    : emphasis
      ? 'font-semibold text-ink'
      : 'text-ink'

  return (
    <button
      onClick={start}
      disabled={saving}
      className={`tnum block w-full cursor-text rounded px-2 py-1 text-right text-sm hover:bg-editwash ${toneClass} ${
        saving ? 'opacity-40' : ''
      } ${isSet && signed ? 'font-medium' : ''}`}
      title="Click to edit"
    >
      {signed && value > 0 ? '+' : ''}
      {value === 0 && !isSet ? '—' : fmtFull(value)}
    </button>
  )
}

interface CommentCellProps {
  value: string | null
  onSave: (value: string | null) => Promise<void>
}

export function CommentCell({ value, onSave }: CommentCellProps) {
  const [editing, setEditing] = useState(false)
  const [text, setText] = useState('')
  const [saving, setSaving] = useState(false)
  const ref = useRef<HTMLTextAreaElement>(null)

  useEffect(() => {
    if (editing) ref.current?.focus()
  }, [editing])

  const commit = async () => {
    setEditing(false)
    const next = text.trim() === '' ? null : text.trim()
    if (next === (value ?? null)) return
    setSaving(true)
    try {
      await onSave(next)
    } finally {
      setSaving(false)
    }
  }

  if (editing) {
    return (
      <textarea
        ref={ref}
        rows={2}
        className="w-full resize-none rounded border border-brand bg-surface px-2 py-1 text-xs outline-none"
        value={text}
        onChange={(e) => setText(e.target.value)}
        onBlur={commit}
        onKeyDown={(e) => {
          if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) commit()
          if (e.key === 'Escape') setEditing(false)
        }}
        placeholder="Why is your number different?"
      />
    )
  }

  return (
    <button
      onClick={() => {
        setText(value ?? '')
        setEditing(true)
      }}
      disabled={saving}
      className={`block w-full cursor-text rounded px-2 py-1 text-left text-xs hover:bg-editwash ${
        value ? 'text-ink2' : 'text-muted'
      } ${saving ? 'opacity-40' : ''}`}
      title={value ?? 'Click to add a comment'}
    >
      <span className="line-clamp-2">{value || 'Add comment…'}</span>
    </button>
  )
}
