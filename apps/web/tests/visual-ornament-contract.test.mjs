/**
 * Visual Ornament Contract Tests
 *
 * Verifies that the ornament visual system enforces:
 * - aria-hidden on decorative elements
 * - pointer-events: none on ornament layers
 * - z-index layering (ornament < content)
 * - No business text inside SVG
 * - Proper component exports
 */

import assert from 'node:assert/strict'
import { readFileSync, existsSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import { describe, it } from 'node:test'

const __dirname = dirname(fileURLToPath(import.meta.url))
const SRC = resolve(__dirname, '..', 'src')

function readSource(...segments) {
  const file = resolve(SRC, ...segments)
  assert.ok(existsSync(file), `File must exist: ${file}`)
  return readFileSync(file, 'utf8')
}

describe('Ornament component exports', () => {
  it('visual/index.ts exports OrnamentLayer and VisualGuideCard', () => {
    const index = readSource('components', 'common', 'visual', 'index.ts')
    assert.match(index, /export \{ OrnamentLayer \} from '\.\/OrnamentLayer'/)
    assert.match(index, /export \{ VisualGuideCard \} from '\.\/VisualGuideCard'/)
    assert.match(index, /export type \{/)
  })

  it('OrnamentLayer.tsx exists and is a named export', () => {
    const src = readSource('components', 'common', 'visual', 'OrnamentLayer.tsx')
    assert.match(src, /export function OrnamentLayer/)
  })

  it('VisualGuideCard.tsx exists and is a named export', () => {
    const src = readSource('components', 'common', 'visual', 'VisualGuideCard.tsx')
    assert.match(src, /export function VisualGuideCard/)
  })

  it('ornamentTypes.ts defines all type unions', () => {
    const src = readSource('components', 'common', 'visual', 'ornamentTypes.ts')
    assert.match(src, /OrnamentVariant/)
    assert.match(src, /'blueprint'/)
    assert.match(src, /'constellation'/)
    assert.match(src, /'manuscript'/)
    assert.match(src, /'handoff'/)
    assert.match(src, /'route'/)
    assert.match(src, /'none'/)
    assert.match(src, /OrnamentPlacement/)
    assert.match(src, /OrnamentDensity/)
    assert.match(src, /OrnamentTone/)
  })
})

describe('OrnamentLayer accessibility and layering', () => {
  it('renders aria-hidden="true"', () => {
    const src = readSource('components', 'common', 'visual', 'OrnamentLayer.tsx')
    assert.match(src, /aria-hidden="true"/)
  })

  it('uses mo-ornament-layer CSS class', () => {
    const src = readSource('components', 'common', 'visual', 'OrnamentLayer.tsx')
    assert.match(src, /mo-ornament-layer/)
  })

  it('returns null for variant="none"', () => {
    const src = readSource('components', 'common', 'visual', 'OrnamentLayer.tsx')
    assert.match(src, /variant === 'none'/)
    assert.match(src, /return null/)
  })

  it('does NOT contain <text> SVG elements (no business text in SVG)', () => {
    const src = readSource('components', 'common', 'visual', 'OrnamentLayer.tsx')
    assert.doesNotMatch(src, /<text[\s>]/)
  })

  it('does NOT contain SVG id attributes (avoid duplicate id conflicts)', () => {
    const src = readSource('components', 'common', 'visual', 'OrnamentLayer.tsx')
    // SVGs should not use id="..." which can conflict when multiple instances render
    assert.doesNotMatch(src, /\sid="[^"]+"/)
  })

  it('uses pointer-events-none via mo-ornament-layer CSS', () => {
    const css = readSource('index.css')
    assert.match(css, /\.mo-ornament-layer\s*\{[^}]*pointer-events:\s*none/)
  })
})

describe('CSS contract', () => {
  const css = readSource('index.css')

  it('defines .mo-ornament-host with isolation: isolate', () => {
    assert.match(css, /\.mo-ornament-host\s*\{/)
    assert.match(css, /\.mo-ornament-host\s*\{[^}]*isolation:\s*isolate/)
  })

  it('defines .mo-ornament-layer with z-index: 0 and pointer-events: none', () => {
    assert.match(css, /\.mo-ornament-layer\s*\{[^}]*z-index:\s*0/)
    assert.match(css, /\.mo-ornament-layer\s*\{[^}]*pointer-events:\s*none/)
    assert.match(css, /\.mo-ornament-layer\s*\{[^}]*user-select:\s*none/)
  })

  it('defines .mo-ornament-content with z-index: 10 (above ornament)', () => {
    assert.match(css, /\.mo-ornament-content\s*\{[^}]*z-index:\s*10/)
    assert.match(css, /\.mo-ornament-content\s*\{[^}]*min-width:\s*0/)
  })

  it('defines .mo-ornament-safe-tr', () => {
    assert.match(css, /\.mo-ornament-safe-tr\s*\{/)
  })

  it('has ornament CSS tokens', () => {
    assert.match(css, /--mo-ornament-blue:/)
    assert.match(css, /--mo-ornament-blue-strong:/)
    assert.match(css, /--mo-ornament-muted:/)
    assert.match(css, /--mo-ornament-amber:/)
    assert.match(css, /--mo-ornament-green:/)
  })

  it('has small-screen noise reduction for ornament layer', () => {
    assert.match(css, /@media\s*\(max-width:\s*640px\)\s*\{[^}]*\.mo-ornament-layer/)
  })

  it('mo-blueprint-panel::before/after have z-index: 0 (not 1)', () => {
    assert.match(css, /\.mo-blueprint-panel::before,\s*\.mo-blueprint-panel::after\s*\{[^}]*z-index:\s*0/)
  })

  it('mo-blueprint-panel > * have z-index: 1', () => {
    assert.match(css, /\.mo-blueprint-panel\s*>\s*\*\s*\{[^}]*z-index:\s*1/)
  })

  it('mo-dossier-ornament has user-select: none', () => {
    assert.match(css, /\.mo-dossier-ornament\s*\{[^}]*user-select:\s*none/)
  })

  it('mo-dossier-ornament pseudo-elements have pointer-events: none', () => {
    // Check that both ::before and ::after in mo-dossier-ornament have pointer-events
    const beforeMatch = css.match(/\.mo-dossier-ornament::before\s*\{[^}]*\}/g)
    const afterMatch = css.match(/\.mo-dossier-ornament::after\s*\{[^}]*\}/g)
    assert.ok(beforeMatch, 'mo-dossier-ornament::before must exist')
    assert.ok(afterMatch, 'mo-dossier-ornament::after must exist')
    const hasPointerEvents = (block) => /pointer-events:\s*none/.test(block)
    assert.ok(beforeMatch.some(hasPointerEvents), 'mo-dossier-ornament::before must have pointer-events: none')
    assert.ok(afterMatch.some(hasPointerEvents), 'mo-dossier-ornament::after must have pointer-events: none')
  })
})

describe('StatusGuide ornament integration', () => {
  it('uses mo-ornament-content class', () => {
    const src = readSource('components', 'common', 'StatusGuide.tsx')
    assert.match(src, /mo-ornament-content/)
  })

  it('imports OrnamentLayer', () => {
    const src = readSource('components', 'common', 'StatusGuide.tsx')
    assert.match(src, /import.*OrnamentLayer/)
  })

  it('imports OrnamentVariant type', () => {
    const src = readSource('components', 'common', 'StatusGuide.tsx')
    assert.match(src, /OrnamentVariant/)
  })

  it('supports ornament prop (OrnamentVariant | false)', () => {
    const src = readSource('components', 'common', 'StatusGuide.tsx')
    assert.match(src, /ornament\?:\s*OrnamentVariant\s*\|\s*false/)
  })

  it('supports ornamentLabel prop that defaults to false', () => {
    const src = readSource('components', 'common', 'StatusGuide.tsx')
    assert.match(src, /ornamentLabel\?:\s*string\s*\|\s*false/)
  })

  it('renders OrnamentLayer when ornament !== false', () => {
    const src = readSource('components', 'common', 'StatusGuide.tsx')
    assert.match(src, /ornament !== false/)
    assert.match(src, /<OrnamentLayer/)
  })

  it('ornamentLabel div has aria-hidden="true" when shown', () => {
    const src = readSource('components', 'common', 'StatusGuide.tsx')
    // The ornamentLabel block contains both the conditional and aria-hidden
    assert.match(src, /{ornamentLabel &&/)
    // The div inside the ornamentLabel block has aria-hidden
    assert.match(src, /aria-hidden="true"/)
  })
})

describe('BlueprintPanel ornament fixes', () => {
  it('uses mo-ornament-host and mo-ornament-content classes', () => {
    const src = readSource('components', 'common', 'visual', 'BlueprintPanel.tsx')
    assert.match(src, /mo-ornament-host/)
    assert.match(src, /mo-ornament-content/)
  })

  it('has decorativeLabel prop (default true)', () => {
    const src = readSource('components', 'common', 'visual', 'BlueprintPanel.tsx')
    assert.match(src, /decorativeLabel\?:\s*boolean/)
  })

  it('label/index has z-0 (below content)', () => {
    const src = readSource('components', 'common', 'visual', 'BlueprintPanel.tsx')
    assert.match(src, /z-0/)
  })
})

describe('Overflow fixes', () => {
  it('MetricChip has max-w-full', () => {
    const src = readSource('components', 'common', 'visual', 'MetricChip.tsx')
    assert.match(src, /max-w-full/)
  })

  it('EvidenceMarker label has min-w-0 truncate', () => {
    const src = readSource('components', 'common', 'visual', 'EvidenceMarker.tsx')
    assert.match(src, /min-w-0 truncate/)
  })

  it('SectionRail description has break-words', () => {
    const src = readSource('components', 'common', 'visual', 'SectionRail.tsx')
    assert.match(src, /break-words/)
  })
})

describe('Page-level ornament integration', () => {
  it('TaskCreatePage uses VisualGuideCard', () => {
    const src = readSource('pages', 'TaskCreatePage.tsx')
    assert.match(src, /VisualGuideCard/)
  })

  it('Pages set ornamentLabel={false} (no decorative dossier text)', () => {
    const pages = [
      'TaskCreatePage.tsx',
      'PlanReviewPage.tsx',
      'WorkflowPage.tsx',
      'ComparisonPage.tsx',
      'HistoryPage.tsx',
      'ReportPage.tsx',
    ]
    for (const page of pages) {
      const src = readSource('pages', page)
      assert.match(
        src,
        /ornamentLabel=\{false\}/,
        `${page} should set ornamentLabel={false}`,
      )
    }
  })

  it('Pages set explicit ornament variants matching page semantics', () => {
    const tasks = readSource('pages', 'TaskCreatePage.tsx')
    assert.match(tasks, /ornament="hand-left"/)

    const plan = readSource('pages', 'PlanReviewPage.tsx')
    assert.match(plan, /ornament="research-flow"/)

    const workflow = readSource('pages', 'WorkflowPage.tsx')
    assert.match(workflow, /ornament="research-flow"/)

    const comparison = readSource('pages', 'ComparisonPage.tsx')
    assert.match(comparison, /ornament="hand-right"/)

    const history = readSource('pages', 'HistoryPage.tsx')
    assert.match(history, /ornament="manuscript"/)
  })

  it('ReportPage computes ornament based on viewMode', () => {
    const src = readSource('pages', 'ReportPage.tsx')
    assert.match(src, /reportOrnament/)
    assert.match(src, /'manuscript'/)
    assert.match(src, /'spark-field'/)
    // evidence view now uses manuscript as well (cleaner reading experience)
  })
})
