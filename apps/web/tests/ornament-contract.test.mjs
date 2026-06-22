import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { test } from 'node:test'

function read(path) {
  return readFileSync(new URL(`../${path}`, import.meta.url), 'utf8')
}

// ─── Ornament type contract ──────────────────────────────────────────

test('ornamentTypes includes all reference glyph variants', () => {
  const text = read('src/components/common/visual/ornamentTypes.ts')
  for (const key of ['hand-left', 'hand-right', 'halo', 'wing', 'angel', 'spark-field', 'research-flow']) {
    assert.match(text, new RegExp(`'${key}'`), `Missing variant: ${key}`)
  }
})

test('ornamentTypes includes OrnamentMotion type', () => {
  const text = read('src/components/common/visual/ornamentTypes.ts')
  assert.match(text, /OrnamentMotion/)
  for (const key of ['none', 'float', 'draw', 'pulse', 'drift']) {
    assert.match(text, new RegExp(`'${key}'`), `Missing motion: ${key}`)
  }
})

// ─── Visual barrel exports ───────────────────────────────────────────

test('visual/index.ts exports OrnamentLayer', () => {
  const text = read('src/components/common/visual/index.ts')
  assert.match(text, /OrnamentLayer/)
})

test('visual/index.ts exports PageOrnamentFrame', () => {
  const text = read('src/components/common/visual/index.ts')
  assert.match(text, /PageOrnamentFrame/)
})

test('visual/index.ts exports WaitingGuide', () => {
  const text = read('src/components/common/visual/index.ts')
  assert.match(text, /WaitingGuide/)
})

// ─── CSS contract ────────────────────────────────────────────────────

test('index.css contains ornament layer contract', () => {
  const css = read('src/index.css')
  assert.match(css, /\.mo-ornament-layer/)
  assert.match(css, /\.mo-ornament-content/)
})

test('index.css contains prefers-reduced-motion', () => {
  const css = read('src/index.css')
  assert.match(css, /prefers-reduced-motion/)
})

test('index.css contains ornament motion keyframes', () => {
  const css = read('src/index.css')
  assert.match(css, /mo-ornament-float/)
  assert.match(css, /mo-ornament-drift/)
  assert.match(css, /mo-ornament-pulse/)
  assert.match(css, /mo-ornament-draw/)
})

test('index.css contains page ornament frame classes', () => {
  const css = read('src/index.css')
  assert.match(css, /\.mo-page-ornament-frame/)
  assert.match(css, /\.mo-page-ornament-bg/)
  assert.match(css, /\.mo-page-ornament-content/)
})

// ─── Accessibility contract ──────────────────────────────────────────

test('OrnamentLayer.tsx contains aria-hidden', () => {
  const text = read('src/components/common/visual/OrnamentLayer.tsx')
  assert.match(text, /aria-hidden="true"/)
})

test('OrnamentLayer.tsx contains pointer-events protection', () => {
  const text = read('src/components/common/visual/OrnamentLayer.tsx')
  // The mo-ornament-layer CSS class provides pointer-events: none
  assert.match(text, /mo-ornament-layer/)
})

// ─── PageOrnamentFrame contract ──────────────────────────────────────

test('PageOrnamentFrame contains presets for all pages', () => {
  const text = read('src/components/common/visual/PageOrnamentFrame.tsx')
  for (const preset of ['task', 'plan', 'workflow', 'comparison', 'report', 'default']) {
    assert.match(text, new RegExp(preset), `Missing preset: ${preset}`)
  }
})

test('PageOrnamentFrame uses aria-hidden on background layer', () => {
  const text = read('src/components/common/visual/PageOrnamentFrame.tsx')
  assert.match(text, /aria-hidden="true"/)
})

// ─── WaitingGuide contract ───────────────────────────────────────────

test('WaitingGuide contains variants', () => {
  const text = read('src/components/common/visual/WaitingGuide.tsx')
  for (const variant of ['planning', 'executing', 'reporting', 'loading']) {
    assert.match(text, new RegExp(`'${variant}'`), `Missing variant: ${variant}`)
  }
})
