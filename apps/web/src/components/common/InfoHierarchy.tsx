/**
 * InfoHierarchy — 页面统一信息层级布局组件
 *
 * 定义 MO 全局页面结构：
 *   PageHeader         — 页面顶部：标题 + StatusGuide
 *   PrimaryWorkArea    — 主工作区：不超过 2 个主要操作
 *   SupportingPanel    — 辅助面板：证据/日志/风险/配置/节点详情，可折叠/drawer/tabs
 *   SecondaryNavigation — 次级导航：返回历史、查看工作流、查看报告等链接
 *
 * 使用模式：
 *
 *   <div className="space-y-6">
 *     {/* PageHeader — StatusGuide 放在这里 * /}
 *     <StatusGuide title="..." whatNow="..." ... />
 *
 *     {/* 主布局：PrimaryWorkArea + SupportingPanel * /}
 *     <PageLayout
 *       primary={<PrimaryWorkArea>主内容</PrimaryWorkArea>}
 *       supporting={<SupportingPanel>证据/日志等</SupportingPanel>}
 *     />
 *
 *     <SecondaryNavigation items={[...]} />
 *   </div>
 */

import { useState, type ReactNode } from 'react'
import { ChevronDown, ChevronRight } from 'lucide-react'
import { cn } from '@/lib/utils'

// ─── PageHeader ────────────────────────────────────────────────────────

export interface PageHeaderProps {
  /** 页面主标题（用户可理解的中文） */
  title: string
  /** 标题下方的简短描述 */
  description?: string
  /** 右侧操作区（按钮组等） */
  actions?: ReactNode
  className?: string
}

/**
 * PageHeader — 页面标题区
 *
 * 位于 StatusGuide 下方，提供页面上下文标题和可选操作按钮。
 * 注意：状态引导使用 StatusGuide 组件，不在 PageHeader 中重复。
 */
export function PageHeader({ title, description, actions, className }: PageHeaderProps) {
  return (
    <div className={cn('flex items-start justify-between gap-4 flex-wrap', className)}>
      <div className="min-w-0">
        <h2 className="text-lg font-semibold text-foreground">{title}</h2>
        {description && (
          <p className="mt-1 text-sm text-muted-foreground">{description}</p>
        )}
      </div>
      {actions && (
        <div className="flex items-center gap-2 flex-shrink-0">{actions}</div>
      )}
    </div>
  )
}

// ─── PageLayout (主布局容器) ───────────────────────────────────

export interface PageLayoutProps {
  /** 主工作区内容（可通过 children 或 primary prop 传入） */
  primary?: ReactNode
  /** 辅助面板内容（可选） */
  supporting?: ReactNode
  /** children 方式使用时自动识别 PrimaryWorkArea 和 SupportingPanel */
  children?: ReactNode
  /** 辅助面板位置：右侧（默认）或底部 */
  supportingPosition?: 'right' | 'bottom'
  /** 主工作区与辅助面板的宽度比例，默认 3:1 */
  ratio?: '2:1' | '3:1' | '3:2'
  className?: string
}

const RATIO_CLASS: Record<string, { primary: string; supporting: string }> = {
  '2:1': { primary: 'lg:col-span-2', supporting: 'lg:col-span-1' },
  '3:1': { primary: 'lg:col-span-3', supporting: 'lg:col-span-1' },
  '3:2': { primary: 'lg:col-span-3', supporting: 'lg:col-span-2' },
}

/**
 * PageLayout — 页面主布局容器
 *
 * 默认使用 3 栏主 + 1 栏辅助的网格布局，移动端垂直堆叠。
 *
 * 支持两种用法：
 * 1. Props 方式：`<PageLayout primary={...} supporting={...} />`
 * 2. Children 方式：`<PageLayout><PrimaryWorkArea>...</PrimaryWorkArea><SupportingPanel>...</SupportingPanel></PageLayout>`
 */
export function PageLayout({
  primary,
  supporting,
  children,
  supportingPosition = 'right',
  ratio = '3:1',
  className,
}: PageLayoutProps) {
  // children 方式：兼容旧版 JSX 结构
  const content = primary ?? children

  if (!supporting) {
    return <div className={cn('space-y-6', className)}>{content}</div>
  }

  if (supportingPosition === 'bottom') {
    return (
      <div className={cn('space-y-6', className)}>
        <div>{content}</div>
        <div>{supporting}</div>
      </div>
    )
  }

  const cols = RATIO_CLASS[ratio] ?? RATIO_CLASS['3:1']

  return (
    <div className={cn('grid grid-cols-1 lg:grid-cols-4 gap-6', className)}>
      <div className={cn('space-y-6 min-w-0', cols.primary)}>{content}</div>
      {supporting && (
        <aside className={cn('space-y-4 min-w-0', cols.supporting)}>
          {supporting}
        </aside>
      )}
    </div>
  )
}

// ─── PrimaryWorkArea ────────────────────────────────────────────────────

export interface PrimaryWorkAreaProps {
  children: ReactNode
  /** 本区域的主标题 */
  title?: string
  /** 最多 2 个主要操作按钮 */
  actions?: ReactNode
  className?: string
}

/**
 * PrimaryWorkArea — 主工作区
 *
 * 页面最重要的任务内容区域。不超过 2 个主要操作。
 * 用于包裹核心表单、计划步骤列表、工作流图、对比矩阵、报告内容等。
 */
export function PrimaryWorkArea({ children, title, actions, className }: PrimaryWorkAreaProps) {
  return (
    <section className={cn('space-y-4', className)} aria-label={title}>
      {(title || actions) && (
        <div className="flex items-center justify-between gap-3 flex-wrap">
          {title && <h3 className="text-base font-medium text-foreground">{title}</h3>}
          {actions && <div className="flex items-center gap-2">{actions}</div>}
        </div>
      )}
      {children}
    </section>
  )
}

// ─── SupportingPanel ────────────────────────────────────────────────────

export type SupportingPanelVariant = 'card' | 'drawer' | 'tabs' | 'collapsible'

export interface TabDef {
  id: string
  label: string
  content: ReactNode
}

export interface SupportingPanelProps {
  children?: ReactNode
  /** 面板标题 */
  title?: string
  /**
   * 显示形态：
   * - card: 默认，卡片形式固定在页面侧栏
   * - collapsible: 可折叠的卡片
   * - tabs: tab 切换面板（需提供 tabs prop）
   * - drawer: 请使用独立的 SupportingDrawer 组件
   */
  variant?: SupportingPanelVariant
  /** tabs 模式下 tab 定义 */
  tabs?: TabDef[]
  /** collapsible 模式下是否默认展开 */
  defaultOpen?: boolean
  /**
   * 是否标记为"技术详情"（内部术语在此显示）。
   * 仅 card / collapsible / tabs 变体生效。
   */
  technical?: boolean
  className?: string
}

/**
 * SupportingPanel — 辅助信息面板
 *
 * 承载证据列表、日志、风险详情、配置摘要、原始节点详情等技术/辅助信息。
 * - card: 默认卡片形式
 * - collapsible: 点击标题折叠/展开
 * - tabs: 水平 tab 切换（通过 tabs prop 定义）
 * - drawer: 使用独立的 SupportingDrawer 组件
 *
 * 标记 technical={true} 表示内部可能包含原始 node id / evidence id / tool name 等技术术语。
 */
export function SupportingPanel({
  children,
  title,
  variant = 'card',
  tabs,
  defaultOpen = true,
  technical = false,
  className,
}: SupportingPanelProps) {
  // ── collapsible 状态 ──────────────────────────────────────
  const [collapsed, setCollapsed] = useState(!defaultOpen)

  // ── tabs 状态 ──────────────────────────────────────────────
  const [activeTabId, setActiveTabId] = useState<string>(
    tabs && tabs.length > 0 ? tabs[0].id : '',
  )

  // ── 公共 header ───────────────────────────────────────────
  const headerMarkup = (title || technical) && (
    <div className="flex items-center gap-2 mb-3">
      {title && (
        <h4 className="text-sm font-medium text-muted-foreground uppercase tracking-wide">
          {title}
        </h4>
      )}
      {technical && (
        <span className="text-[10px] text-muted-foreground/60 bg-muted px-1.5 py-0.5 rounded">
          技术详情
        </span>
      )}
    </div>
  )

  // ── 公共样式 ──────────────────────────────────────────────
  const baseClasses = cn(
    'rounded-lg border bg-card p-4',
    technical && 'border-dashed border-muted-foreground/30',
    className,
  )

  // ── tabs 变体 ──────────────────────────────────────────────
  if (variant === 'tabs' && tabs && tabs.length > 0) {
    const activeTab = tabs.find((t) => t.id === activeTabId) ?? tabs[0]
    return (
      <section
        className={cn(baseClasses, 'p-0 overflow-hidden')}
        aria-label={title ?? activeTab.label}
      >
        {/* Tab 条 */}
        <div className="flex border-b" role="tablist">
          {tabs.map((tab) => (
            <button
              key={tab.id}
              role="tab"
              aria-selected={tab.id === activeTabId}
              onClick={() => setActiveTabId(tab.id)}
              className={cn(
                'px-4 py-2.5 text-sm font-medium transition-colors border-b-2 -mb-px',
                tab.id === activeTabId
                  ? 'border-primary text-primary'
                  : 'border-transparent text-muted-foreground hover:text-foreground hover:border-muted-foreground/30',
              )}
            >
              {tab.label}
            </button>
          ))}
        </div>
        {/* Tab 内容 */}
        <div className="p-4">{activeTab.content}</div>
      </section>
    )
  }

  // ── collapsible 变体 ──────────────────────────────────────
  if (variant === 'collapsible') {
    return (
      <section className={baseClasses} aria-label={title ?? '辅助信息'}>
        <button
          type="button"
          onClick={() => setCollapsed(!collapsed)}
          className="flex items-center justify-between w-full text-left"
          aria-expanded={!collapsed}
        >
          {headerMarkup ? (
            <div>{headerMarkup}</div>
          ) : (
            <span className="text-sm font-medium">{title ?? '详情'}</span>
          )}
          {collapsed ? (
            <ChevronRight className="h-4 w-4 text-muted-foreground flex-shrink-0" aria-hidden />
          ) : (
            <ChevronDown className="h-4 w-4 text-muted-foreground flex-shrink-0" aria-hidden />
          )}
        </button>
        {!collapsed && <div className="mt-3 text-sm">{children}</div>}
      </section>
    )
  }

  // ── card 变体（默认）─────────────────────────────────────
  return (
    <section
      className={baseClasses}
      aria-label={title ?? (technical ? '技术详情' : '辅助信息')}
    >
      {headerMarkup}
      <div className="text-sm">{children}</div>
    </section>
  )
}

// ─── SecondaryNavigation ────────────────────────────────────────────────

export interface NavItem {
  label: string
  href?: string
  onClick?: () => void
  /** 高亮当前活跃项 */
  active?: boolean
  icon?: ReactNode
}

export interface SecondaryNavigationProps {
  items: NavItem[]
  /** 返回链接（通常是返回历史列表） */
  backTo?: NavItem
  className?: string
}

/**
 * SecondaryNavigation — 次级导航
 *
 * 页面底部的导航链接，如：返回历史、查看工作流、查看报告、导出等。
 * 用于页面间的跳转，放在主要内容区下方。
 */
export function SecondaryNavigation({ items, backTo, className }: SecondaryNavigationProps) {
  return (
    <nav className={cn('flex items-center justify-between gap-3 pt-4 border-t', className)} aria-label="次级导航">
      <div className="flex items-center gap-1 flex-wrap">
        {backTo && (
          backTo.href ? (
            <a
              href={backTo.href}
              className="inline-flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground transition-colors px-2 py-1 rounded hover:bg-muted"
            >
              {backTo.icon}
              {backTo.label}
            </a>
          ) : (
            <button
              type="button"
              onClick={backTo.onClick}
              className="inline-flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground transition-colors px-2 py-1 rounded hover:bg-muted"
            >
              {backTo.icon}
              {backTo.label}
            </button>
          )
        )}
      </div>
      <div className="flex items-center gap-1 flex-wrap">
        {items.map((item, idx) =>
          item.href ? (
            <a
              key={idx}
              href={item.href}
              className={cn(
                'inline-flex items-center gap-1.5 text-sm px-2 py-1 rounded transition-colors',
                item.active
                  ? 'bg-primary/10 text-primary font-medium'
                  : 'text-muted-foreground hover:text-foreground hover:bg-muted',
              )}
            >
              {item.icon}
              {item.label}
            </a>
          ) : (
            <button
              key={idx}
              type="button"
              onClick={item.onClick}
              className={cn(
                'inline-flex items-center gap-1.5 text-sm px-2 py-1 rounded transition-colors',
                item.active
                  ? 'bg-primary/10 text-primary font-medium'
                  : 'text-muted-foreground hover:text-foreground hover:bg-muted',
              )}
            >
              {item.icon}
              {item.label}
            </button>
          ),
        )}
      </div>
    </nav>
  )
}
