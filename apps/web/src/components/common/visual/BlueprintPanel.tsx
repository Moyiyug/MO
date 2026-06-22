import type { ReactNode } from 'react'
import { motion } from 'motion/react'

import { cn } from '@/lib/utils'
import { useMotionSafe } from './useMotionSafe'

interface BlueprintPanelProps {
  children: ReactNode
  label?: string
  index?: string | number
  accent?: 'blue' | 'amber' | 'green' | 'red' | 'slate'
  className?: string
  contentClassName?: string
  as?: 'section' | 'div' | 'article'
  /** 将 label/index 视为纯装饰（aria-hidden，更低透明度），默认 true */
  decorativeLabel?: boolean
}

const ACCENT_CLASS: Record<NonNullable<BlueprintPanelProps['accent']>, string> = {
  blue: 'before:border-blue-500/70 after:border-blue-500/70',
  amber: 'before:border-amber-500/70 after:border-amber-500/70',
  green: 'before:border-emerald-500/70 after:border-emerald-500/70',
  red: 'before:border-red-500/70 after:border-red-500/70',
  slate: 'before:border-slate-400/70 after:border-slate-400/70',
}

export function BlueprintPanel({
  children,
  label,
  index,
  accent = 'blue',
  className,
  contentClassName,
  as = 'section',
  decorativeLabel = true,
}: BlueprintPanelProps) {
  const motionSafe = useMotionSafe()
  const MotionTag =
    as === 'article' ? motion.article : as === 'div' ? motion.div : motion.section

  const hasChrome = label || index !== undefined

  return (
    <MotionTag
      initial={motionSafe.initial}
      animate={motionSafe.animate}
      transition={motionSafe.transition}
      className={cn(
        'mo-ornament-host mo-blueprint-panel mo-card-hover',
        ACCENT_CLASS[accent],
        className,
      )}
    >
      {hasChrome && (
        <div
          aria-hidden={decorativeLabel ? true : undefined}
          className={cn(
            'pointer-events-none absolute right-3 top-2 z-0 flex items-center gap-2 text-[10px] uppercase tracking-[0.24em]',
            decorativeLabel
              ? 'text-muted-foreground/45'
              : 'text-muted-foreground/70',
            'sm:flex',
          )}
        >
          {label && <span>{label}</span>}
          {index !== undefined && (
            <span className="rounded-full border border-[var(--mo-line)] bg-background/70 px-1.5 py-0.5 font-mono">
              {String(index).padStart(2, '0')}
            </span>
          )}
        </div>
      )}
      <div
        className={cn(
          'mo-ornament-content',
          hasChrome && 'sm:pt-4',
          contentClassName,
        )}
      >
        {children}
      </div>
    </MotionTag>
  )
}
