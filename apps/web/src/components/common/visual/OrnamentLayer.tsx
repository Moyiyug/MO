import { cn } from '@/lib/utils'
import type {
  OrnamentDensity,
  OrnamentMotion,
  OrnamentPlacement,
  OrnamentTone,
  OrnamentVariant,
} from './ornamentTypes'
import { OrnamentGlyph } from './ornamentGlyphs'

interface OrnamentLayerProps {
  variant?: OrnamentVariant
  placement?: OrnamentPlacement
  density?: OrnamentDensity
  tone?: OrnamentTone
  motion?: OrnamentMotion
  size?: 'sm' | 'md' | 'lg' | 'xl'
  className?: string
}

const PLACEMENT_CLASS: Record<OrnamentPlacement, string> = {
  'top-right': 'items-start justify-end',
  'top-left': 'items-start justify-start',
  'bottom-right': 'items-end justify-end',
  'bottom-left': 'items-end justify-start',
  center: 'items-center justify-center',
}

const TONE_CLASS: Record<OrnamentTone, string> = {
  blue: 'text-blue-700/35',
  slate: 'text-slate-600/20',
  amber: 'text-amber-700/30',
  green: 'text-emerald-700/28',
  violet: 'text-violet-700/28',
}

const DENSITY_CLASS: Record<OrnamentDensity, string> = {
  low: 'opacity-45',
  medium: 'opacity-60',
  high: 'opacity-75',
}

const MOTION_CLASS: Record<OrnamentMotion, string> = {
  none: '',
  float: 'mo-ornament-float',
  draw: 'mo-ornament-draw',
  pulse: 'mo-ornament-pulse',
  drift: 'mo-ornament-drift',
}

const SIZE_CLASS: Record<string, string> = {
  sm: 'h-20 w-36',
  md: 'h-28 w-48 max-w-[48%] sm:h-36 sm:w-64',
  lg: 'h-44 w-72 sm:h-56 sm:w-[28rem]',
  xl: 'h-64 w-[34rem] sm:h-80 sm:w-[42rem]',
}

export function OrnamentLayer({
  variant = 'blueprint',
  placement = 'top-right',
  density = 'low',
  tone = 'blue',
  motion = 'none',
  size = 'md',
  className,
}: OrnamentLayerProps) {
  if (variant === 'none') return null

  return (
    <div
      aria-hidden="true"
      className={cn(
        'mo-ornament-layer flex p-3 sm:p-4',
        PLACEMENT_CLASS[placement],
        TONE_CLASS[tone],
        DENSITY_CLASS[density],
        className,
      )}
    >
      <svg
        viewBox="0 0 240 140"
        className={cn(SIZE_CLASS[size], MOTION_CLASS[motion])}
        fill="none"
        strokeLinecap="round"
        strokeLinejoin="round"
        focusable="false"
      >
        <OrnamentGlyph variant={variant} />
      </svg>
    </div>
  )
}
