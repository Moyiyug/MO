/**
 * SectionTabs — 区域内标签切换
 *
 * 水平 tab 按钮组，用于页面内区域切换（如：计划步骤 / 候选仓库 / 评分权重）。
 * 不涉及路由，纯 UI 状态。
 *
 * 使用示例：
 *   <SectionTabs
 *     tabs={[
 *       { id: 'steps', label: '计划步骤', count: 5 },
 *       { id: 'repos', label: '候选仓库', count: 3 },
 *       { id: 'weights', label: '评分权重' },
 *     ]}
 *     activeTab="steps"
 *     onTabChange={setTab}
 *   />
 */

import { cn } from '@/lib/utils'

// ─── 类型 ──────────────────────────────────────────────────────────────

export interface SectionTab {
  id: string
  label: string
  /** 可选数字徽章 */
  count?: number
}

export interface SectionTabsProps {
  tabs: SectionTab[]
  activeTab: string
  onTabChange: (id: string) => void
  className?: string
}

// ─── 组件 ──────────────────────────────────────────────────────────────

export function SectionTabs({
  tabs,
  activeTab,
  onTabChange,
  className,
}: SectionTabsProps) {
  if (tabs.length === 0) return null

  return (
    <div
      className={cn(
        'flex overflow-x-auto rounded-lg border bg-background/45 p-1 shadow-[0_1px_0_rgba(255,255,255,0.72)_inset]',
        className,
      )}
      role="tablist"
    >
      {tabs.map((tab) => (
        <button
          key={tab.id}
          type="button"
          role="tab"
          aria-selected={tab.id === activeTab}
          onClick={() => onTabChange(tab.id)}
          className={cn(
            'inline-flex items-center gap-1.5 rounded-md border px-3 py-2 text-sm font-medium transition-colors',
            tab.id === activeTab
              ? 'border-blue-300 bg-blue-50/90 text-blue-900 shadow-sm'
              : 'border-transparent text-muted-foreground hover:border-blue-200 hover:bg-blue-50/50 hover:text-blue-900',
          )}
        >
          {tab.label}
          {tab.count !== undefined && tab.count > 0 && (
            <span
              className={cn(
                'inline-flex items-center justify-center min-w-[18px] h-[18px] rounded-full px-1 text-xs',
                tab.id === activeTab
                  ? 'bg-primary/15 text-primary'
                  : 'bg-muted text-muted-foreground',
              )}
            >
              {tab.count}
            </span>
          )}
        </button>
      ))}
    </div>
  )
}
