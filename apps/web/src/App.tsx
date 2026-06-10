import { Navigate, Route, Routes } from 'react-router-dom'

import { AppLayout } from '@/components/layout/AppLayout'
import { PlanReviewPage } from '@/pages/PlanReviewPage'
import { ReportPage, ReportPreviewDemo } from '@/pages/ReportPage'
import { TaskCreatePage } from '@/pages/TaskCreatePage'
import { WorkflowPage } from '@/pages/WorkflowPage'

function ReportPageWithDemo() {
  return (
    <>
      <ReportPage />
      <ReportPreviewDemo />
    </>
  )
}

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<TaskCreatePage />} />
      <Route path="/tasks/:taskId" element={<AppLayout />}>
        <Route index element={<Navigate to="plan" replace />} />
        <Route path="plan" element={<PlanReviewPage />} />
        <Route path="workflow" element={<WorkflowPage />} />
        <Route path="report" element={<ReportPageWithDemo />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}
