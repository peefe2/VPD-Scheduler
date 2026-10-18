import type { ButtonHTMLAttributes, ReactNode } from 'react'
import { Link } from 'react-router-dom'
import type { Tone } from '../lib/labels'
import { Icon } from './Icon'
import s from './ui.module.css'

export function Card({
  title,
  sub,
  action,
  children,
  className,
}: {
  title?: ReactNode
  sub?: ReactNode
  action?: ReactNode
  children: ReactNode
  className?: string
}) {
  return (
    <section className={[s.card, className].filter(Boolean).join(' ')}>
      {(title || action) && (
        <header className={s.cardHead}>
          <div>
            {title && <h2 className={s.cardTitle}>{title}</h2>}
            {sub && <p className={s.cardSub}>{sub}</p>}
          </div>
          {action}
        </header>
      )}
      {children}
    </section>
  )
}

export function Badge({ tone = 'neutral', dot, children }: { tone?: Tone; dot?: boolean; children: ReactNode }) {
  return (
    <span className={s.badge} data-tone={tone}>
      {dot && <span className={s.dot} aria-hidden="true" />}
      {children}
    </span>
  )
}

type Variant = 'primary' | 'secondary' | 'ghost'

export function Button({
  variant = 'primary',
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: Variant }) {
  return <button className={s.button} data-variant={variant} {...props} />
}

export function ButtonLink({ to, variant = 'primary', children }: { to: string; variant?: Variant; children: ReactNode }) {
  return (
    <Link to={to} className={s.button} data-variant={variant}>
      {children}
    </Link>
  )
}

export function IconButton({ label, ...props }: ButtonHTMLAttributes<HTMLButtonElement> & { label: string }) {
  return <button className={s.iconButton} data-variant="secondary" aria-label={label} title={label} {...props} />
}

export function Field({
  label,
  htmlFor,
  hint,
  children,
}: {
  label: ReactNode
  htmlFor: string
  hint?: ReactNode
  children: ReactNode
}) {
  return (
    <div className={s.field}>
      <label className={s.label} htmlFor={htmlFor}>
        {label}
      </label>
      {children}
      {hint && <p className={s.hint}>{hint}</p>}
    </div>
  )
}


export function PageHeader({ title, sub, actions }: { title: ReactNode; sub?: ReactNode; actions?: ReactNode }) {
  return (
    <div className={s.pageHeader}>
      <div>
        <h1 className={s.pageTitle}>{title}</h1>
        {sub && <p className={s.pageSub}>{sub}</p>}
      </div>
      {actions}
    </div>
  )
}

export function Stat({ label, value, unit, foot }: { label: ReactNode; value: ReactNode; unit?: string; foot?: ReactNode }) {
  return (
    <div className={s.stat}>
      <span className={s.statLabel}>{label}</span>
      <span className={s.statValue}>
        {value}
        {unit && <span className={s.statUnit}>{unit}</span>}
      </span>
      {foot && <span className={s.hint}>{foot}</span>}
    </div>
  )
}

export function Notice({ tone = 'neutral', children }: { tone?: 'neutral' | 'warn' | 'info' | 'brand'; children: ReactNode }) {
  return (
    <div className={s.notice} data-tone={tone} role={tone === 'warn' ? 'alert' : undefined}>
      <Icon name={tone === 'warn' ? 'alert' : 'info'} size={16} />
      <div>{children}</div>
    </div>
  )
}

export function Empty({ title, children, action }: { title: ReactNode; children?: ReactNode; action?: ReactNode }) {
  return (
    <div className={s.empty}>
      <p className={s.emptyTitle}>{title}</p>
      {children && <p>{children}</p>}
      {action}
    </div>
  )
}

export function Loading({ label = '불러오는 중' }: { label?: string }) {
  return (
    <div className={s.empty} role="status">
      <span className={s.spinner} aria-hidden="true" />
      <span>{label}</span>
    </div>
  )
}

export function ErrorState({ error }: { error: unknown }) {
  return (
    <Notice tone="warn">
      요청을 처리하지 못했습니다. {error instanceof Error ? error.message : String(error)}
    </Notice>
  )
}

export function Segmented<T extends string>({
  value,
  options,
  onChange,
  label,
}: {
  value: T
  options: { value: T; label: string }[]
  onChange: (v: T) => void
  label: string
}) {
  return (
    <div className={s.segmented} role="group" aria-label={label}>
      {options.map((o) => (
        <button key={o.value} type="button" aria-pressed={o.value === value} onClick={() => onChange(o.value)}>
          {o.label}
        </button>
      ))}
    </div>
  )
}
