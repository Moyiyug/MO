import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import { test } from 'node:test'

test('Report B phase 3 routes expose reader data and evidence views', async () => {
  const app = await readFile(new URL('../src/App.tsx', import.meta.url), 'utf8')

  assert.match(app, /report\/data/)
  assert.match(app, /report\/evidence/)
  assert.match(app, /report\/sections\/:sectionKey\/data/)
})

test('report types keep explicit section metadata contract', async () => {
  const reportTypes = await readFile(
    new URL('../src/types/report.ts', import.meta.url),
    'utf8',
  )

  assert.match(reportTypes, /ReportSectionMetadata/)
  assert.match(reportTypes, /structured_markdown/)
  assert.match(reportTypes, /seed_narratives/)
  assert.match(reportTypes, /seed_structured_data/)
  assert.match(reportTypes, /polish_status/)
})

test('ReportPage delegates data facts away from the default reader page', async () => {
  const reportPage = await readFile(
    new URL('../src/pages/ReportPage.tsx', import.meta.url),
    'utf8',
  )

  assert.match(reportPage, /getReportViewMode/)
  assert.match(reportPage, /ReportReaderOverview/)
  assert.match(reportPage, /ReportDataOverview/)
  assert.match(reportPage, /ReportSectionDataView/)
  assert.match(reportPage, /ReportEvidenceView/)
  assert.equal(reportPage.includes('EvidenceSummary'), false)
})

test('data views read structured markdown and reader sections link to data', async () => {
  const sectionData = await readFile(
    new URL('../src/features/report/components/ReportSectionDataView.tsx', import.meta.url),
    'utf8',
  )
  const readerSection = await readFile(
    new URL('../src/features/report/components/ReportReaderSection.tsx', import.meta.url),
    'utf8',
  )
  const structuredMarkdown = await readFile(
    new URL('../src/features/report/components/ReportStructuredMarkdown.tsx', import.meta.url),
    'utf8',
  )
  const utils = await readFile(
    new URL('../src/features/report/components/reportViewUtils.ts', import.meta.url),
    'utf8',
  )

  assert.match(utils, /metadata\?\.structured_markdown/)
  assert.match(sectionData, /ReportStructuredMarkdown/)
  assert.match(structuredMarkdown, /SafeMarkdown/)
  assert.match(readerSection, /查看本章数据、结论与证据/)
})

test('evidence index is preserved in the optional evidence view', async () => {
  const evidenceView = await readFile(
    new URL('../src/features/report/components/ReportEvidenceView.tsx', import.meta.url),
    'utf8',
  )

  assert.match(evidenceView, /EvidenceSummary/)
  assert.match(evidenceView, /defaultExpanded/)
  assert.match(evidenceView, /证据附录/)
})
