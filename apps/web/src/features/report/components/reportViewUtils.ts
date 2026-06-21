import type { ReportResponse, ReportSection } from '@/types/report'

export type ReportViewMode =
  | 'reader-summary'
  | 'reader-full'
  | 'reader-section'
  | 'data-overview'
  | 'data-section'
  | 'evidence'

export function getReportViewMode(
  pathname: string,
  sectionKey?: string,
): ReportViewMode {
  if (pathname.endsWith('/report/evidence')) return 'evidence'
  if (pathname.endsWith('/report/data')) return 'data-overview'
  if (pathname.endsWith('/data') && sectionKey) return 'data-section'
  if (pathname.endsWith('/report/full')) return 'reader-full'
  if (sectionKey) return 'reader-section'
  return 'reader-summary'
}

export function sectionPath(taskId: string, sectionKey: string) {
  return `/tasks/${taskId}/report/sections/${sectionKey}`
}

export function sectionDataPath(taskId: string, sectionKey: string) {
  return `/tasks/${taskId}/report/sections/${sectionKey}/data`
}

export function getStructuredMarkdown(section: ReportSection): string | undefined {
  return section.structured_markdown ?? section.metadata?.structured_markdown
}

export function getPolishStatus(section: ReportSection): string {
  return String(
    section.polish_status ?? section.metadata?.polish_status ?? 'unknown',
  )
}

export function collectReportEvidenceIds(report: ReportResponse): string[] {
  const ids = report.sections.flatMap((section) => [
    ...(section.evidence_ids ?? []),
    ...section.claims.flatMap((claim) => claim.evidence_ids),
  ])
  return [...new Set(ids)]
}
