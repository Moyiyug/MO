import { Link } from 'react-router-dom'

import { SupportingPanel } from '@/components/common/InfoHierarchy'
import { cn } from '@/lib/utils'
import { REPORT_VIEW_COPY } from '@/lib/uiCopy'
import type { ReportResponse } from '@/types/report'

import type { ReportViewMode } from './reportViewUtils'
import { sectionDataPath, sectionPath } from './reportViewUtils'

interface ReportNavigationPanelProps {
  taskId: string
  report: ReportResponse
  viewMode: ReportViewMode
  sectionKey?: string
}

export function ReportNavigationPanel({
  taskId,
  report,
  viewMode,
  sectionKey,
}: ReportNavigationPanelProps) {
  const navClass = (active: boolean) =>
    cn(
      'block rounded-md px-2 py-1.5 text-sm hover:bg-muted',
      active ? 'bg-primary/10 text-primary' : 'text-muted-foreground hover:text-foreground',
    )

  return (
    <SupportingPanel title="报告导航">
      <div className="space-y-2">
        <Link
          to={`/tasks/${taskId}/report`}
          className={navClass(viewMode === 'reader-summary')}
        >
          {REPORT_VIEW_COPY.readerSummary.label}
        </Link>
        <Link
          to={`/tasks/${taskId}/report/full`}
          className={navClass(viewMode === 'reader-full')}
        >
          {REPORT_VIEW_COPY.readerFull.label}
        </Link>
        <Link
          to={`/tasks/${taskId}/report/data`}
          className={navClass(viewMode === 'data-overview')}
        >
          {REPORT_VIEW_COPY.dataOverview.label}
        </Link>
        <Link
          to={`/tasks/${taskId}/report/evidence`}
          className={navClass(viewMode === 'evidence')}
        >
          {REPORT_VIEW_COPY.evidence.label}
        </Link>

        <div className="border-t pt-2">
          {report.sections.map((section, index) => {
            const readerActive =
              viewMode === 'reader-section' && section.key === sectionKey
            const dataActive =
              viewMode === 'data-section' && section.key === sectionKey
            return (
              <div key={section.key} className="space-y-1">
                <Link
                  to={sectionPath(taskId, section.key)}
                  className={cn(
                    'block rounded-md px-2 py-1.5 text-sm text-muted-foreground hover:bg-muted hover:text-foreground',
                    readerActive && 'bg-primary/10 text-primary',
                  )}
                >
                  {index + 1}. {section.title}
                </Link>
                {(viewMode === 'data-overview' || viewMode === 'data-section') && (
                  <Link
                    to={sectionDataPath(taskId, section.key)}
                    className={cn(
                      'ml-4 block rounded px-2 py-1 text-xs text-muted-foreground hover:bg-muted hover:text-primary',
                      dataActive && 'bg-primary/10 text-primary',
                    )}
                  >
                    数据
                  </Link>
                )}
              </div>
            )
          })}
        </div>
      </div>
    </SupportingPanel>
  )
}
