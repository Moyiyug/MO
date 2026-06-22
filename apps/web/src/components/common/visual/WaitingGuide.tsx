import { Brain, FileSearch, Route, Sparkles } from 'lucide-react'

import { OrnamentLayer } from './OrnamentLayer'
import { BlueprintPanel } from './BlueprintPanel'
import { cn } from '@/lib/utils'

export type WaitingGuideVariant = 'planning' | 'executing' | 'reporting' | 'loading'

interface WaitingGuideProps {
  title?: string
  description?: string
  steps?: string[]
  variant?: WaitingGuideVariant
  className?: string
}

const DEFAULT_STEPS: Record<WaitingGuideVariant, string[]> = {
  planning: ['理解研究目标', '拆解调研步骤', '准备候选范围'],
  executing: ['读取仓库资料', '分析代码结构', '整理证据链'],
  reporting: ['汇总研究发现', '组织报告结构', '检查待确认项'],
  loading: ['读取数据', '整理页面', '准备展示'],
}

const VARIANT_ICON: Record<WaitingGuideVariant, React.ReactNode> = {
  planning: <Route className="h-5 w-5" aria-hidden />,
  executing: <Brain className="h-5 w-5" aria-hidden />,
  reporting: <FileSearch className="h-5 w-5" aria-hidden />,
  loading: <Sparkles className="h-5 w-5" aria-hidden />,
}

const VARIANT_ORNAMENT = {
  planning: 'spark-field' as const,
  executing: 'research-flow' as const,
  reporting: 'halo' as const,
  loading: 'spark-field' as const,
}

const VARIANT_ORNAMENT_TONE = {
  planning: 'blue' as const,
  executing: 'amber' as const,
  reporting: 'blue' as const,
  loading: 'blue' as const,
}

const VARIANT_ORNAMENT_MOTION = {
  planning: 'float' as const,
  executing: 'draw' as const,
  reporting: 'float' as const,
  loading: 'float' as const,
}

export function WaitingGuide({
  title = '正在处理',
  description = '系统正在推进当前步骤，请稍候。',
  steps,
  variant = 'loading',
  className,
}: WaitingGuideProps) {
  const items = steps ?? DEFAULT_STEPS[variant]

  return (
    <BlueprintPanel
      label="working"
      className={cn('mx-auto my-12 max-w-2xl overflow-hidden', className)}
      contentClassName="relative px-6 py-8"
    >
      <OrnamentLayer
        variant={VARIANT_ORNAMENT[variant]}
        placement="top-right"
        density="medium"
        tone={VARIANT_ORNAMENT_TONE[variant]}
        motion={VARIANT_ORNAMENT_MOTION[variant]}
        size="lg"
      />

      <div className="relative z-10 max-w-lg space-y-4">
        <div className="flex items-start gap-3">
          <div className="rounded-md border bg-background/80 p-2 text-blue-700 shadow-sm">
            {VARIANT_ICON[variant]}
          </div>
          <div>
            <h2 className="text-base font-semibold text-foreground">{title}</h2>
            <p className="mt-1 text-sm text-muted-foreground">{description}</p>
          </div>
        </div>

        <ol className="space-y-2 text-sm text-muted-foreground">
          {items.map((step, index) => (
            <li key={step} className="flex items-center gap-2">
              <span className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full border bg-background/80 font-mono text-[10px] text-blue-700">
                {index + 1}
              </span>
              <span>{step}</span>
            </li>
          ))}
        </ol>
      </div>
    </BlueprintPanel>
  )
}
