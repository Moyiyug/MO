import { cn } from '@/lib/utils'
import type {
  OrnamentDensity,
  OrnamentPlacement,
  OrnamentTone,
  OrnamentVariant,
} from './ornamentTypes'

interface OrnamentLayerProps {
  variant?: OrnamentVariant
  placement?: OrnamentPlacement
  density?: OrnamentDensity
  tone?: OrnamentTone
  className?: string
}

const PLACEMENT_CLASS: Record<OrnamentPlacement, string> = {
  'top-right': 'items-start justify-end',
  'top-left': 'items-start justify-start',
  'bottom-right': 'items-end justify-end',
  center: 'items-center justify-center',
}

const TONE_CLASS: Record<OrnamentTone, string> = {
  blue: 'text-blue-700/35',
  slate: 'text-slate-600/20',
  amber: 'text-amber-700/30',
  green: 'text-emerald-700/28',
}

const DENSITY_CLASS: Record<OrnamentDensity, string> = {
  low: 'opacity-45',
  medium: 'opacity-60',
  high: 'opacity-75',
}

// ─── SVG Glyphs (no text, no ids — pure line art) ──────────────────────

function BlueprintGlyph() {
  return (
    <>
      <path
        d="M18 92 C54 42 90 126 134 66 S210 52 222 28"
        stroke="currentColor"
        strokeWidth="1.2"
      />
      <path d="M36 24 H198 M54 118 H220" stroke="currentColor" strokeWidth="0.8" opacity="0.55" />
      <circle cx="62" cy="78" r="4" stroke="currentColor" strokeWidth="1" />
      <circle cx="146" cy="64" r="6" stroke="currentColor" strokeWidth="1" />
      <path d="M146 64 L198 40" stroke="currentColor" strokeWidth="0.8" opacity="0.6" />
    </>
  )
}

function ConstellationGlyph() {
  return (
    <>
      <circle cx="34" cy="48" r="3.5" stroke="currentColor" strokeWidth="1" />
      <circle cx="98" cy="28" r="2.5" stroke="currentColor" strokeWidth="0.9" />
      <circle cx="162" cy="72" r="4" stroke="currentColor" strokeWidth="1" />
      <circle cx="198" cy="36" r="3" stroke="currentColor" strokeWidth="0.9" />
      <circle cx="124" cy="98" r="2.5" stroke="currentColor" strokeWidth="0.85" />
      <circle cx="72" cy="110" r="3" stroke="currentColor" strokeWidth="0.9" />
      <path d="M34 48 L98 28 L162 72 L198 36" stroke="currentColor" strokeWidth="0.7" opacity="0.5" />
      <path d="M98 28 L124 98" stroke="currentColor" strokeWidth="0.6" opacity="0.4" />
      <path d="M162 72 L124 98 L72 110" stroke="currentColor" strokeWidth="0.7" opacity="0.5" />
    </>
  )
}

function ManuscriptGlyph() {
  return (
    <>
      <path d="M22 32 H172 M22 52 H188 M22 72 H166 M22 92 H196" stroke="currentColor" strokeWidth="0.9" opacity="0.5" />
      <path d="M22 112 H148" stroke="currentColor" strokeWidth="0.7" opacity="0.35" />
      <rect x="184" y="18" width="38" height="52" rx="2" stroke="currentColor" strokeWidth="1" opacity="0.6" />
      <path d="M192 28 H212 M192 38 H214 M192 48 H206" stroke="currentColor" strokeWidth="0.7" opacity="0.42" />
    </>
  )
}

function HandoffGlyph() {
  return (
    <>
      <path
        d="M28 66 C52 36 84 106 112 80"
        stroke="currentColor"
        strokeWidth="1.3"
        opacity="0.55"
      />
      <path
        d="M118 62 C132 38 160 52 176 34"
        stroke="currentColor"
        strokeWidth="1.2"
        opacity="0.55"
      />
      <circle cx="28" cy="66" r="6" stroke="currentColor" strokeWidth="1.1" opacity="0.55" />
      <circle cx="176" cy="34" r="7" stroke="currentColor" strokeWidth="1.1" opacity="0.55" />
      <circle cx="112" cy="80" r="5" stroke="currentColor" strokeWidth="1" opacity="0.5" />
      <path d="M118 62 L112 80" stroke="currentColor" strokeWidth="0.7" opacity="0.45" />
    </>
  )
}

function RouteGlyph() {
  return (
    <>
      <path d="M20 90 L72 90 L108 36 L174 36 L218 78" stroke="currentColor" strokeWidth="1.3" opacity="0.55" />
      <circle cx="20" cy="90" r="5" stroke="currentColor" strokeWidth="1.1" opacity="0.55" />
      <circle cx="72" cy="90" r="4.5" stroke="currentColor" strokeWidth="1" opacity="0.5" />
      <circle cx="108" cy="36" r="4.5" stroke="currentColor" strokeWidth="1" opacity="0.5" />
      <circle cx="174" cy="36" r="4.5" stroke="currentColor" strokeWidth="1" opacity="0.5" />
      <circle cx="218" cy="78" r="5" stroke="currentColor" strokeWidth="1.1" opacity="0.55" />
      <path d="M20 112 L72 112 L108 96" stroke="currentColor" strokeWidth="0.7" opacity="0.3" strokeDasharray="4 4" />
    </>
  )
}

// ─── Component ────────────────────────────────────────────────────────

export function OrnamentLayer({
  variant = 'blueprint',
  placement = 'top-right',
  density = 'low',
  tone = 'blue',
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
        className="h-28 w-48 max-w-[48%] sm:h-36 sm:w-64"
        fill="none"
      >
        {variant === 'blueprint' && <BlueprintGlyph />}
        {variant === 'constellation' && <ConstellationGlyph />}
        {variant === 'manuscript' && <ManuscriptGlyph />}
        {variant === 'handoff' && <HandoffGlyph />}
        {variant === 'route' && <RouteGlyph />}
      </svg>
    </div>
  )
}
