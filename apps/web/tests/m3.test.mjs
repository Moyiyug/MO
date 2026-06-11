import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import { test } from 'node:test'
import { createJiti } from 'jiti'

const jiti = createJiti(import.meta.url)

test('repo URL validation mirrors the M3 frontend boundary', async () => {
  const { isValidRepoUrl, validateRepoUrlList } = await jiti.import(
    '../src/lib/repoValidation.ts',
  )

  assert.equal(isValidRepoUrl('https://github.com/owner/repo'), true)
  assert.equal(isValidRepoUrl('http://github.com/owner/repo'), false)
  assert.equal(isValidRepoUrl('https://example.com/owner/repo'), false)
  assert.equal(validateRepoUrlList([]), '至少填写 1 个仓库 URL')
  assert.equal(
    validateRepoUrlList([
      'https://github.com/o/r1',
      'https://github.com/o/r2',
      'https://github.com/o/r3',
      'https://github.com/o/r4',
      'https://github.com/o/r5',
      'https://github.com/o/r6',
    ]),
    '最多 5 个仓库 URL',
  )
})

test('rubric validation rejects weights whose sum is not approximately one', async () => {
  const { isRubricValid } = await jiti.import('../src/types/plan.ts')

  assert.equal(
    isRubricValid({
      reproducibility: 0.3,
      documentation: 0.2,
      research_value: 0.2,
      engineering_fit: 0.2,
      extensibility: 0.1,
    }),
    true,
  )
  assert.equal(isRubricValid({ reproducibility: 0.3 }), false)
})

test('workflow graph respects backend skipped step status', async () => {
  const { buildStepGraph, stepStatusToDisplayStatus } = await jiti.import(
    '../src/features/workflow/buildGraph.ts',
  )
  const skippedStep = {
    id: 'step_report',
    title: '报告生成',
    description: '生成报告',
    tool: 'report_writer',
    risk_level: 'medium',
    requires_approval: true,
    expected_outputs: ['markdown_report'],
    depends_on: [],
    user_editable: true,
    status: 'skipped',
  }
  const pendingStep = { ...skippedStep, id: 'step_repo', status: 'pending' }

  assert.equal(stepStatusToDisplayStatus(skippedStep), 'skipped')
  assert.equal(stepStatusToDisplayStatus(pendingStep), 'pending')

  const graph = buildStepGraph([skippedStep])
  assert.equal(graph.nodes[0].data.displayStatus, 'skipped')
})

test('report route stays within M3 empty-state boundary', async () => {
  const appSource = await readFile(new URL('../src/App.tsx', import.meta.url), 'utf8')
  const reportSource = await readFile(
    new URL('../src/pages/ReportPage.tsx', import.meta.url),
    'utf8',
  )

  assert.equal(appSource.includes('ReportPreviewDemo'), false)
  assert.equal(reportSource.includes('仓库 README 存在安装说明'), false)
  assert.equal(reportSource.includes('入口可能在'), false)
})

test('SafeMarkdown uses sanitize and no raw HTML escape hatch', async () => {
  const safeMarkdownSource = await readFile(
    new URL('../src/components/common/SafeMarkdown.tsx', import.meta.url),
    'utf8',
  )

  assert.match(safeMarkdownSource, /rehype-sanitize/)
  assert.match(safeMarkdownSource, /rehypePlugins=\{\[rehypeSanitize\]\}/)
  assert.equal(safeMarkdownSource.includes('dangerouslySetInnerHTML'), false)
})
