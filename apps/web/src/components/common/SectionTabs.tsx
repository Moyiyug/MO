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
    <div className={cn('flex border-b', className)} role="tablist">
      {tabs.map((tab) => (
        <button
          key={tab.id}
          type="button"
          role="tab"
          aria-selected={tab.id === activeTab}
          onClick={() => onTabChange(tab.id)}
          className={cn(
            'inline-flex items-center gap-1.5 px-4 py-2.5 text-sm font-medium transition-colors',
            'border-b-2 -mb-px',
            tab.id === activeTab
              ? 'border-primary text-primary'
              : 'border-transparent text-muted-foreground hover:text-foreground hover:border-muted-foreground/30',
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
