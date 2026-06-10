import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { toast } from 'sonner'

import { useCreateTask, useGeneratePlan } from '@/api/tasks'
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

/** P-001 TaskCreate */
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

  return (
    <div className="mx-auto max-w-2xl">
      <Card>
        <CardHeader>
          <CardTitle>创建调研任务</CardTitle>
          <CardDescription>
            填写研究目标与仓库信息。提交后将进入 PlanMode 生成计划（P-001）。
          </CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit} className="flex flex-col gap-6">
            <div className="space-y-2">
              <Label htmlFor="goal">研究目标</Label>
              <Textarea
                id="goal"
                value={goal}
                onChange={(e) => setGoal(e.target.value)}
                placeholder="例如：对比两个 RL 框架的可复现性与工程成熟度"
                rows={3}
                required
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="repos">
                仓库 URL（1–5 个，每行一个）
              </Label>
              <Textarea
                id="repos"
                value={repoText}
                onChange={(e) => setRepoText(e.target.value)}
                placeholder="https://github.com/owner/repo"
                rows={4}
                required
              />
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

            <div className="space-y-2">
              <Label htmlFor="template">报告模板（可选）</Label>
              <Input
                id="template"
                value={template}
                onChange={(e) => setTemplate(e.target.value)}
                placeholder="default"
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="lang">输出语言</Label>
              <select
                id="lang"
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

            <fieldset className="space-y-3 rounded-lg border p-4">
              <legend className="px-1 text-sm font-medium">权限开关</legend>
              <p className="text-xs text-muted-foreground">
                默认保守：联网调研、冒烟测试、依赖安装均为关闭。
              </p>
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
            </fieldset>

            {formError && (
              <p className="text-sm text-destructive" role="alert">
                {formError}
              </p>
            )}

            <Button type="submit" disabled={isSubmitting} className="w-full">
              {isSubmitting ? '提交中…' : '创建任务并生成计划'}
            </Button>
          </form>
        </CardContent>
      </Card>
    </div>
  )
}
