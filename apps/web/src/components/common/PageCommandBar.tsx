import type { ReactNode } from 'react'
import { motion, useReducedMotion } from 'motion/react'

import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'

export interface CommandAction {
  label: string
  onClick?: () => void
  href?: string
  disabled?: boolean
  destructive?: boolean
  icon?: ReactNode
}

export interface PageCommandBarProps {
  title?: string
  description?: string
  primary?: CommandAction
  secondary?: CommandAction[]
  position?: 'top' | 'inline'
  className?: string
}

function CommandButton({ action, variant }: { action: CommandAction; variant: 'primary' | 'secondary' }) {
  const buttonVariant = action.destructive
    ? 'destructive'
    : variant === 'primary'
      ? 'default'
      : 'outline'

  if (action.href) {
    return (
      <Button size="sm" variant={buttonVariant} disabled={action.disabled} asChild>
        <a href={action.href}>
          {action.icon}
          {action.label}
        </a>
      </Button>
    )
  }

  return (
    <Button
      size="sm"
      variant={buttonVariant}
      disabled={action.disabled}
      onClick={action.onClick}
    >
      {action.icon}
      {action.label}
    </Button>
  )
}

export function PageCommandBar({
  title,
  description,
  primary,
  secondary = [],
  position = 'inline',
  className,
}: PageCommandBarProps) {
  const reduceMotion = useReducedMotion()

  return (
    <motion.div
      initial={reduceMotion ? false : { opacity: 0, y: 12 }}
      animate={reduceMotion ? undefined : { opacity: 1, y: 0 }}
      transition={{ duration: 0.22, ease: 'easeOut' }}
      className={cn(
        'z-30 rounded-lg border bg-background/94 p-3 shadow-sm backdrop-blur supports-[backdrop-filter]:bg-background/82',
        position === 'top' && 'sticky top-20 shadow-md shadow-slate-900/10',
        position === 'inline' && 'relative',
        'flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between',
        className,
      )}
      role="region"
      aria-label="页面操作"
    >
      {(title || description) && (
        <div className="min-w-0">
          {title && <p className="text-sm font-medium">{title}</p>}
          {description && (
            <p className="mt-0.5 text-xs text-muted-foreground">{description}</p>
          )}
        </div>
      )}
      <div className="flex flex-wrap items-center gap-2 sm:justify-end">
        {secondary.map((action) => (
          <CommandButton key={action.label} action={action} variant="secondary" />
        ))}
        {primary && <CommandButton action={primary} variant="primary" />}
      </div>
    </motion.div>
  )
}
