import type { OrnamentVariant } from './ornamentTypes'

// ─── Existing Glyphs (extracted from OrnamentLayer) ───────────────────

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

// ─── New Reference Glyphs (per PRD section 5.1) ──────────────────────

function HandLeftGlyph() {
  return (
    <>
      <path
        d="M24 92 C44 70 62 68 82 78 C96 84 110 82 126 70"
        stroke="currentColor"
        strokeWidth="1.2"
        strokeLinecap="round"
      />
      <path
        d="M80 78 C76 62 78 48 86 34 M94 78 C94 58 100 42 112 28 M108 78 C116 60 126 48 140 38"
        stroke="currentColor"
        strokeWidth="0.9"
        strokeLinecap="round"
        opacity="0.65"
      />
      <path
        d="M126 70 C144 58 158 48 178 42"
        stroke="currentColor"
        strokeWidth="1"
        strokeLinecap="round"
        opacity="0.45"
      />
    </>
  )
}

function HaloGlyph() {
  return (
    <>
      <ellipse
        cx="120"
        cy="58"
        rx="52"
        ry="14"
        stroke="currentColor"
        strokeWidth="1.1"
      />
      <ellipse
        cx="120"
        cy="58"
        rx="38"
        ry="8"
        stroke="currentColor"
        strokeWidth="0.7"
        opacity="0.42"
      />
      <path
        d="M74 94 C102 78 138 78 166 94"
        stroke="currentColor"
        strokeWidth="0.9"
        opacity="0.35"
        strokeLinecap="round"
      />
    </>
  )
}

function WingGlyph() {
  return (
    <>
      <path
        d="M42 92 C76 42 122 44 150 86 C128 76 104 82 86 110"
        stroke="currentColor"
        strokeWidth="1.1"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <path
        d="M72 82 C92 62 112 58 134 72 M78 98 C104 82 122 82 142 92"
        stroke="currentColor"
        strokeWidth="0.8"
        opacity="0.5"
        strokeLinecap="round"
      />
    </>
  )
}

function SparkFieldGlyph() {
  return (
    <>
      <circle cx="42" cy="44" r="2.5" stroke="currentColor" strokeWidth="0.9" />
      <circle cx="98" cy="28" r="1.8" stroke="currentColor" strokeWidth="0.8" />
      <circle cx="166" cy="70" r="2.8" stroke="currentColor" strokeWidth="0.9" />
      <circle cx="204" cy="32" r="1.6" stroke="currentColor" strokeWidth="0.7" opacity="0.7" />
      <circle cx="28" cy="96" r="2" stroke="currentColor" strokeWidth="0.8" opacity="0.65" />
      <path d="M42 44 C70 26 118 42 166 70" stroke="currentColor" strokeWidth="0.7" opacity="0.45" />
      <path d="M186 38 l8 0 M190 34 l0 8" stroke="currentColor" strokeWidth="0.8" opacity="0.6" />
      <path d="M204 32 L218 26 M214 24 L216 22" stroke="currentColor" strokeWidth="0.6" opacity="0.4" />
    </>
  )
}

function ResearchFlowGlyph() {
  return (
    <>
      {/* manuscript-style horizontal lines */}
      <path d="M18 36 H130 M18 54 H154 M18 72 H138" stroke="currentColor" strokeWidth="0.8" opacity="0.4" />
      {/* constellation-style nodes */}
      <circle cx="156" cy="54" r="3" stroke="currentColor" strokeWidth="0.9" opacity="0.55" />
      <circle cx="190" cy="36" r="2.5" stroke="currentColor" strokeWidth="0.85" opacity="0.5" />
      <circle cx="216" cy="68" r="3.5" stroke="currentColor" strokeWidth="0.9" opacity="0.55" />
      <circle cx="172" cy="92" r="2.8" stroke="currentColor" strokeWidth="0.85" opacity="0.5" />
      <circle cx="132" cy="104" r="2.2" stroke="currentColor" strokeWidth="0.8" opacity="0.45" />
      {/* route-style connecting paths */}
      <path d="M154 54 L190 36 L216 68" stroke="currentColor" strokeWidth="0.7" opacity="0.45" />
      <path d="M154 54 L172 92 L132 104" stroke="currentColor" strokeWidth="0.6" opacity="0.35" />
      {/* trajectory line */}
      <path d="M18 108 C80 88 140 100 220 44" stroke="currentColor" strokeWidth="0.7" opacity="0.3" strokeDasharray="5 6" />
    </>
  )
}

// ─── Glyph Dispatcher ─────────────────────────────────────────────────

export function OrnamentGlyph({ variant }: { variant: OrnamentVariant }) {
  switch (variant) {
    case 'blueprint':
      return <BlueprintGlyph />
    case 'constellation':
      return <ConstellationGlyph />
    case 'manuscript':
      return <ManuscriptGlyph />
    case 'handoff':
      return <HandoffGlyph />
    case 'route':
      return <RouteGlyph />
    case 'hand-left':
      return <HandLeftGlyph />
    case 'hand-right':
      return (
        <g transform="translate(240 0) scale(-1 1)">
          <HandLeftGlyph />
        </g>
      )
    case 'halo':
      return <HaloGlyph />
    case 'wing':
      return <WingGlyph />
    case 'angel':
      return (
        <>
          <HaloGlyph />
          <WingGlyph />
        </>
      )
    case 'spark-field':
      return <SparkFieldGlyph />
    case 'research-flow':
      return <ResearchFlowGlyph />
    default:
      return null
  }
}
