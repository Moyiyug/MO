import { lazy, Suspense } from 'react'
import { Navigate, Route, Routes } from 'react-router-dom'
import { Loader2 } from 'lucide-react'

import { AppLayout } from '@/components/layout/AppLayout'

const TaskCreatePage = lazy(() =>
  import('@/pages/TaskCreatePage').then((m) => ({ default: m.TaskCreatePage })),
)
const HistoryPage = lazy(() =>
  import('@/pages/HistoryPage').then((m) => ({ default: m.HistoryPage })),
)
const PlanReviewPage = lazy(() =>
  import('@/pages/PlanReviewPage').then((m) => ({ default: m.PlanReviewPage })),
)
const WorkflowPage = lazy(() =>
  import('@/pages/WorkflowPage').then((m) => ({ default: m.WorkflowPage })),
)
const ComparisonPage = lazy(() =>
  import('@/pages/ComparisonPage').then((m) => ({ default: m.ComparisonPage })),
)
const ReportPage = lazy(() =>
  import('@/pages/ReportPage').then((m) => ({ default: m.ReportPage })),
)

function PageFallback() {
  return (
    <div
      className="flex flex-col items-center justify-center gap-3 py-16 text-muted-foreground"
      role="status"
      aria-live="polite"
    >
      <Loader2 className="h-8 w-8 animate-spin" aria-hidden />
      <span>加载中…</span>
    </div>
  )
}

export default function App() {
  return (
    <Suspense fallback={<PageFallback />}>
      <Routes>
        <Route path="/" element={<TaskCreatePage />} />
        <Route path="/history" element={<HistoryPage />} />
        <Route path="/tasks/:taskId" element={<AppLayout />}>
          <Route index element={<Navigate to="plan" replace />} />
          <Route path="plan" element={<PlanReviewPage />} />
          <Route path="workflow" element={<WorkflowPage />} />
          <Route path="comparison" element={<ComparisonPage />} />
          <Route path="report" element={<ReportPage />} />
          <Route path="report/full" element={<ReportPage />} />
          <Route path="report/data" element={<ReportPage />} />
          <Route path="report/evidence" element={<ReportPage />} />
          <Route path="report/sections/:sectionKey" element={<ReportPage />} />
          <Route path="report/sections/:sectionKey/data" element={<ReportPage />} />
        </Route>
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </Suspense>
  )
}
