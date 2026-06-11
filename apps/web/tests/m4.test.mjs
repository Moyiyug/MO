import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import { test } from 'node:test'
import { createJiti } from 'jiti'

const jiti = createJiti(import.meta.url)

test('workflow graph uses backend SSE status map as display status', async () => {
  const { buildStepGraph } = await jiti.import(
    '../src/features/workflow/buildGraph.ts',
  )
  const steps = [
    {
      id: 'step_repo',
      title: 'Repo ingest',
      description: 'Inspect repo',
      tool: 'repo_ingest',
      risk_level: 'low',
      requires_approval: false,
      expected_outputs: ['repo_card'],
      depends_on: [],
      user_editable: true,
      status: 'pending',
    },
    {
      id: 'step_report',
      title: 'Report',
      description: 'Write report',
      tool: 'report_writer',
      risk_level: 'medium',
      requires_approval: true,
      expected_outputs: ['report'],
      depends_on: ['step_repo'],
      user_editable: true,
      status: 'pending',
    },
  ]

  const graph = buildStepGraph(steps, {
    step_repo: 'completed',
    step_report: 'waiting_user',
  })

  assert.equal(graph.nodes[0].data.displayStatus, 'completed')
  assert.equal(graph.nodes[1].data.displayStatus, 'waiting_user')
  assert.equal(graph.edges[0].animated, false)
})

test('workflow store preserves event evidence ids and monotonic cursor', async () => {
  const { useWorkflowStore } = await jiti.import(
    '../src/stores/workflowStore.ts',
  )

  useWorkflowStore.getState().reset('task-m4')
  useWorkflowStore.getState().applyEvent({
    task_id: 'task-m4',
    seq: 3,
    node: 'step_repo',
    status: 'running',
    evidence_ids: ['ev-1'],
    logs: [],
  })
  useWorkflowStore.getState().applyEvent({
    task_id: 'task-m4',
    seq: 2,
    node: 'step_report',
    status: 'waiting_user',
    evidence_ids: ['ev-2'],
    logs: ['awaiting approval'],
  })

  const state = useWorkflowStore.getState()
  assert.equal(state.lastSeq, 3)
  assert.equal(state.nodeStatuses.step_report, 'waiting_user')
  assert.deepEqual(state.eventsByNode.step_report.evidence_ids, ['ev-2'])
})

test('WorkflowPage exposes M4 evidence details and guarded SSE cleanup', async () => {
  const source = await readFile(
    new URL('../src/pages/WorkflowPage.tsx', import.meta.url),
    'utf8',
  )

  assert.match(source, /证据 ID/)
  assert.match(source, /暂无证据 ID/)
  assert.match(source, /let disposed = false/)
  assert.match(source, /clearReconnectTimer/)
  assert.match(source, /event\.status === 'skipped'/)
})
