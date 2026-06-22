import type { ReactNode } from 'react'
import { OrnamentLayer } from './OrnamentLayer'
import type { OrnamentMotion, OrnamentVariant } from './ornamentTypes'
import { cn } from '@/lib/utils'

interface PageOrnamentFrameProps {
  children: ReactNode
  preset?: 'task' | 'plan' | 'workflow' | 'comparison' | 'report' | 'default'
  className?: string
}

interface OrnamentSlot {
  variant: OrnamentVariant
  className: string
  motion: OrnamentMotion
}

const PRESET: Record<string, OrnamentSlot[]> = {
  task: [
    { variant: 'hand-left', className: 'left-[-7rem] top-16 hidden xl:flex', motion: 'float' },
    { variant: 'halo', className: 'right-[-5rem] top-24 hidden lg:flex', motion: 'pulse' },
    { variant: 'spark-field', className: 'right-8 bottom-10 hidden xl:flex', motion: 'drift' },
  ],
  plan: [
    { variant: 'research-flow', className: 'right-[-6rem] top-20 hidden xl:flex', motion: 'drift' },
    { variant: 'spark-field', className: 'left-[-5rem] bottom-20 hidden lg:flex', motion: 'float' },
  ],
  workflow: [
    { variant: 'constellation', className: 'right-[-7rem] top-16 hidden xl:flex', motion: 'drift' },
    { variant: 'research-flow', className: 'left-[-6rem] bottom-20 hidden xl:flex', motion: 'draw' },
  ],
  report: [
    { variant: 'manuscript', className: 'right-[-6rem] top-20 hidden xl:flex', motion: 'float' },
    { variant: 'wing', className: 'left-[-7rem] bottom-16 hidden xl:flex', motion: 'float' },
    { variant: 'halo', className: 'right-6 bottom-12 hidden lg:flex', motion: 'pulse' },
  ],
  comparison: [
    { variant: 'blueprint', className: 'right-[-6rem] top-20 hidden xl:flex', motion: 'drift' },
    { variant: 'hand-right', className: 'left-[-7rem] bottom-20 hidden xl:flex', motion: 'float' },
  ],
  default: [
    { variant: 'spark-field', className: 'right-[-5rem] top-24 hidden xl:flex', motion: 'float' },
  ],
}

export function PageOrnamentFrame({
  children,
  preset = 'default',
  className,
}: PageOrnamentFrameProps) {
  const ornaments = PRESET[preset] ?? PRESET.default

  return (
    <div className={cn('mo-page-ornament-frame', className)}>
      <div aria-hidden="true" className="mo-page-ornament-bg">
        {ornaments.map((item, index) => (
          <OrnamentLayer
            key={`${item.variant}-${index}`}
            variant={item.variant}
            placement="center"
            density="low"
            tone="blue"
            size="xl"
            motion={item.motion}
            className={cn('absolute opacity-25', item.className)}
          />
        ))}
      </div>
      <div className="mo-page-ornament-content">{children}</div>
    </div>
  )
}
