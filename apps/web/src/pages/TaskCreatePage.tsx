import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import * as Collapsible from '@radix-ui/react-collapsible'
import { ChevronDown, History, Sparkles } from 'lucide-react'
import { toast } from 'sonner'

import { useCreateTask, useGeneratePlan } from '@/api/tasks'
import { StatusGuide } from '@/components/common/StatusGuide'
import { PageLayout, PrimaryWorkArea } from '@/components/common/InfoHierarchy'
import { PageCommandBar } from '@/components/common/PageCommandBar'
import { MetricChip, PageOrnamentFrame, VisualGuideCard } from '@/components/common/visual'
import { Button } from '@/components/ui/button'
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { DEFAULT_PERMISSIONS } from '@/types/task'
import type { OutputLanguage, TaskPermissions } from '@/types'
import {
  parseRepoUrls,
  validateRepoUrlList,
} from '@/lib/repoValidation'
import { PAGE_GUIDE_COPY, CTA_COPY } from '@/lib/uiCopy'

const GOAL_EXAMPLES = [
  '对比 LangChain 与 LlamaIndex 的工程成熟度与可复现性',
  '调研主流 RAG 框架在私有知识库场景中的选型建议',
  '分析一个论文仓库的复现风险、依赖边界和下一步实验计划',
]

/** P-001 TaskCreate — 创建调研任务 */
export function TaskCreatePage() {
  const navigate = useNavigate()
  const createTask = useCreateTask()
  const generatePlan = useGeneratePlan()

  const [goal, setGoal] = useState('')
  const [repoText, setRepoText] = useState('')
  const [paperText, setPaperText] = useState('')
  const [template, setTemplate] = useState('')
  const [outputLanguage, setOutputLanguage] = useState<OutputLanguage>('zh')
  const [permissions, setPermissions] =
    useState<TaskPermissions>(DEFAULT_PERMISSIONS)
  const [formError, setFormError] = useState<string | null>(null)

  const togglePermission = (key: keyof TaskPermissions) => {
    if (key === 'max_runtime_minutes' || key === 'has_gpu') return
    setPermissions((p) => ({ ...p, [key]: !p[key] }))
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setFormError(null)

    const repo_urls = parseRepoUrls(repoText)
    const repoErr = validateRepoUrlList(repo_urls)
    if (repoErr) {
      setFormError(repoErr)
      return
    }
    if (!goal.trim()) {
      setFormError('请填写研究目标')
      return
    }

    const paper_urls = parseRepoUrls(paperText)

    try {
      const created = await createTask.mutateAsync({
        goal: goal.trim(),
        repo_urls,
        paper_urls,
        output_language: outputLanguage,
        template: template.trim() || null,
        permissions,
      })

      await generatePlan.mutateAsync(created.task_id)
      toast.success('任务已创建，计划生成中')
      navigate(`/tasks/${created.task_id}/plan`)
    } catch (err) {
      const msg = err instanceof Error ? err.message : '创建失败'
      setFormError(msg)
      toast.error(msg)
    }
  }

  const isSubmitting = createTask.isPending || generatePlan.isPending
  const guide = PAGE_GUIDE_COPY.taskCreate
  const requestSubmit = () => {
    const form = document.getElementById('task-create-form') as HTMLFormElement | null
    form?.requestSubmit()
  }
  const loadExample = () => {
    setGoal(GOAL_EXAMPLES[0])
    setRepoText('')
    setPaperText('')
    setFormError(null)
    toast.success('示例目标已填入，仓库仍可留空由系统发现。')
  }
  const permissionSummary = [
    permissions.allow_web_search && '联网调研',
    permissions.allow_repo_clone && '克隆仓库',
    permissions.allow_smoke_test && '冒烟测试',
    permissions.allow_dependency_install && '依赖安装',
  ].filter((item): item is string => Boolean(item))

  return (
    <PageOrnamentFrame preset="task" className="min-h-[calc(100svh-3rem)]">
    <div className="mo-page-shell max-w-6xl pt-8 lg:pt-12">
      <StatusGuide
        title={guide.title}
        whatNow={guide.whatNow}
        blockReason={formError ?? undefined}
        ornament="hand-left"
        ornamentLabel={false}
        primaryAction={
          !formError
            ? {
                label: isSubmitting ? '提交中…' : guide.primaryAction,
                onClick: requestSubmit,
                disabled: isSubmitting,
              }
            : undefined
        }
      />

      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_18rem]">
        <PageLayout className="min-w-0">
          <PrimaryWorkArea>
            <Card className="overflow-hidden border-blue-100/80 shadow-xl shadow-slate-900/10">
            <CardHeader className="border-b border-[var(--mo-line)] bg-background/64">
              <div className="flex items-start gap-3">
                <div className="rounded-md bg-blue-600 p-2 text-white">
                  <Sparkles className="h-4 w-4" aria-hidden />
                </div>
                <div>
                  <CardTitle>你想调研什么？</CardTitle>
                  <CardDescription className="mt-1">
                    先写研究目标。仓库可以留空，MO 会在计划阶段推荐候选仓库，执行前仍需要你确认。
                  </CardDescription>
                </div>
              </div>
            </CardHeader>
            <CardContent className="pt-6">
              <form id="task-create-form" onSubmit={handleSubmit} className="flex flex-col gap-6">
                <div className="space-y-2">
                  <Label htmlFor="goal">研究目标</Label>
                  <Textarea
                    id="goal"
                    value={goal}
                    onChange={(e) => setGoal(e.target.value)}
                    placeholder="例如：对比两个 RL 框架的可复现性与工程成熟度"
                    rows={4}
                    required
                    className="text-base"
                  />
                  <div className="flex flex-wrap gap-2 pt-1">
                    {GOAL_EXAMPLES.map((example) => (
                      <button
                        key={example}
                        type="button"
                        onClick={() => setGoal(example)}
                        className="rounded-full border bg-background px-3 py-1 text-xs text-muted-foreground transition-colors hover:border-blue-300 hover:text-blue-700"
                      >
                        {example}
                      </button>
                    ))}
                  </div>
                </div>

                <div className="space-y-2">
                  <Label htmlFor="repos">
                    仓库 URL（可选，0-5 个，每行一个）
                  </Label>
                  <Textarea
                    id="repos"
                    value={repoText}
                    onChange={(e) => setRepoText(e.target.value)}
                    placeholder="https://github.com/owner/repo"
                    rows={4}
                  />
                  <p className="text-xs text-muted-foreground">
                    {guide.repoUrlHelp}
                  </p>
                </div>

                <div className="space-y-2">
                  <Label htmlFor="papers">论文/文档 URL（可选）</Label>
                  <Textarea
                    id="papers"
                    value={paperText}
                    onChange={(e) => setPaperText(e.target.value)}
                    placeholder="每行一个 URL"
                    rows={2}
                  />
                </div>

                <Collapsible.Root className="rounded-lg border bg-muted/25">
                  <Collapsible.Trigger asChild>
                    <Button
                      type="button"
                      variant="ghost"
                      className="flex w-full justify-between px-4"
                    >
                      高级设置
                      <ChevronDown className="h-4 w-4" aria-hidden />
                    </Button>
                  </Collapsible.Trigger>
                  <Collapsible.Content className="border-t p-4">
                    <div className="grid gap-4 md:grid-cols-2">
                      <div className="space-y-1">
                        <Label htmlFor="template-adv" className="text-xs">报告模板</Label>
                        <Input
                          id="template-adv"
                          value={template}
                          onChange={(e) => setTemplate(e.target.value)}
                          placeholder="default"
                        />
                      </div>
                      <div className="space-y-1">
                        <Label htmlFor="lang-adv" className="text-xs">输出语言</Label>
                        <select
                          id="lang-adv"
                          className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 text-sm"
                          value={outputLanguage}
                          onChange={(e) =>
                            setOutputLanguage(e.target.value as OutputLanguage)
                          }
                        >
                          <option value="zh">中文</option>
                          <option value="en">English</option>
                        </select>
                      </div>
                    </div>

                    <div className="mt-4 border-t pt-4">
                      <p className="mb-3 text-xs text-muted-foreground">
                        默认保守：联网调研、冒烟测试、依赖安装均为关闭。高风险操作后续仍会单独审批。
                      </p>
                      <div className="grid gap-2 sm:grid-cols-2">
                        {(
                          [
                            ['allow_web_search', '允许联网调研'],
                            ['allow_repo_clone', '允许克隆仓库'],
                            ['allow_smoke_test', '允许冒烟测试'],
                            ['allow_dependency_install', '允许安装依赖'],
                          ] as const
                        ).map(([key, label]) => (
                          <label key={key} className="flex items-center gap-2 text-sm">
                            <input
                              type="checkbox"
                              checked={permissions[key]}
                              onChange={() => togglePermission(key)}
                              className="h-4 w-4 rounded border-input"
                            />
                            {label}
                          </label>
                        ))}
                      </div>
                    </div>
                  </Collapsible.Content>
                </Collapsible.Root>
              </form>

              <PageCommandBar
                position="inline"
                className="mt-6 border-blue-100 bg-blue-50/60 shadow-none"
                title="辅助操作"
                description="创建任务请使用页面顶部主按钮；提交后只生成计划，执行调研仍需要你批准。"
                secondary={[
                  { label: '加载示例', onClick: loadExample, icon: <Sparkles className="h-4 w-4" aria-hidden /> },
                  { label: CTA_COPY.backToHistory, href: '/history', icon: <History className="h-4 w-4" aria-hidden /> },
                ]}
              />
            </CardContent>
          </Card>
        </PrimaryWorkArea>
      </PageLayout>

        <aside className="space-y-3 lg:pt-8">
          <VisualGuideCard
            eyebrow="research setup"
            title="先定义研究问题"
            description="MO 会先生成计划，不会直接执行仓库代码。你可以在下一步确认候选仓库、权限和风险。"
            ornament="halo"
            steps={[
              '写清研究目标和候选范围',
              '审阅系统生成的调研计划',
              '批准后再执行仓库读取和分析',
            ]}
          />

          <div className="rounded-lg border bg-card/78 p-3 text-sm shadow-sm">
            <p className="font-medium">权限摘要</p>
            <p className="mt-1 text-xs text-muted-foreground">
              默认保守；高风险动作后续仍会单独审批。
            </p>
            <div className="mt-3 flex flex-wrap gap-2">
              {permissionSummary.length > 0 ? (
                permissionSummary.map((item) => (
                  <MetricChip key={item} label={item} tone="amber" />
                ))
              ) : (
                <MetricChip label="默认保守" tone="green" />
              )}
              <MetricChip label={`${permissions.max_runtime_minutes} min`} tone="slate" />
            </div>
          </div>
        </aside>
      </div>

      {formError && (
        <p className="text-sm text-destructive" role="alert">
          {formError}
        </p>
      )}
    </div>
    </PageOrnamentFrame>
  )
}
