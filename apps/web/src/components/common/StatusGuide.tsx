/**
 * StatusGuide — 页面顶部状态引导组件
 *
 * 每页顶部必须回答三个问题：
 *   1. 现在在做什么？（whatNow）
 *   2. 为什么不能继续 / 为什么建议下一步？（blockReason）
 *   3. 点击哪里可以推进？（primaryAction / actionHref / onAction）
 *
 * 使用示例：
 *   <StatusGuide
 *     title="审阅调研计划"
 *     whatNow="审阅系统生成的调研计划，确认后即可开始执行"
 *     primaryAction={{ label: '批准并开始执行', onClick: handleApprove }}
 *   />
 *
 *   <StatusGuide
 *     title="审阅调研计划"
 *     whatNow="审阅系统生成的调研计划"
 *     blockReason="请至少选择一个候选仓库"
 *   />
 */

import type { ReactNode } from 'react'
import { Link } from 'react-router-dom'
import { AlertCircle, ArrowRight, CheckCircle2, HelpCircle, Info, PauseCircle } from 'lucide-react'

import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'

// ─── 类型定义 ──────────────────────────────────────────────────────────

export type GuideSeverity = 'info' | 'warning' | 'success' | 'blocked'

export interface PrimaryAction {
  label: string
  onClick?: () => void
  /** 站内路由，使用 React Router Link，避免整页刷新 */
  to?: string
  href?: string
  disabled?: boolean
  /** 危险操作需二次确认 */
  destructive?: boolean
}

function isInternalHref(href: string | undefined): href is string {
  return Boolean(href && href.startsWith('/'))
}

function ActionLabel({
  action,
  showArrow = false,
}: {
  action: PrimaryAction
  showArrow?: boolean
}) {
  return (
    <>
      {action.label}
      {showArrow && <ArrowRight className="ml-1.5 h-3.5 w-3.5" aria-hidden />}
    </>
  )
}

function LinkedActionContent({
  action,
  showArrow,
}: {
  action: PrimaryAction
  showArrow?: boolean
}) {
  const target = action.to ?? (isInternalHref(action.href) ? action.href : undefined)
  if (target) {
    return (
      <Link to={target}>
        <ActionLabel action={action} showArrow={showArrow} />
      </Link>
    )
  }
  return (
    <a href={action.href}>
      <ActionLabel action={action} showArrow={showArrow} />
    </a>
  )
}

export interface StatusGuideProps {
  /** 页面主标题（用户可理解的中文） */
  title: string
  /** 当前在做什么（简短一句话） */
  whatNow: string
  /**
   * 阻塞原因 / 建议下一步的原因。
   * - 有则显示为警告/阻塞样式，没有主 CTA。
   * - 无则显示为信息/成功样式，可显示主 CTA。
   */
  blockReason?: string
  /** 严重程度：info（默认）/ warning（有阻塞）/ success（可推进）/ blocked（硬阻塞） */
  severity?: GuideSeverity
  /** 主行动按钮 */
  primaryAction?: PrimaryAction
  /** 次要行动按钮 */
  secondaryActions?: PrimaryAction[]
  /** 页面顶部右侧的状态徽章（如 TaskStatusBadge） */
  statusBadge?: ReactNode
  /** 附加的提示信息（在引导文字下方） */
  hint?: string
  className?: string
}

// ─── 颜色 / 图标映射 ──────────────────────────────────────────────────

const SEVERITY_STYLE: Record<
  GuideSeverity,
  { panel: string; accent: string; icon: ReactNode; text: string; block: string }
> = {
  info: {
    panel: 'border-blue-200/80',
    accent: 'bg-blue-600',
    icon: <Info className="h-5 w-5 text-blue-600 flex-shrink-0" aria-hidden />,
    text: 'text-blue-950',
    block: 'border-blue-200 bg-blue-50/70 text-blue-900',
  },
  warning: {
    panel: 'border-amber-300/90',
    accent: 'bg-amber-500',
    icon: <AlertCircle className="h-5 w-5 text-amber-600 flex-shrink-0" aria-hidden />,
    text: 'text-amber-950',
    block: 'border-amber-300 bg-amber-50/85 text-amber-900',
  },
  success: {
    panel: 'border-emerald-200/90',
    accent: 'bg-emerald-500',
    icon: <CheckCircle2 className="h-5 w-5 text-emerald-600 flex-shrink-0" aria-hidden />,
    text: 'text-emerald-950',
    block: 'border-emerald-200 bg-emerald-50/75 text-emerald-900',
  },
  blocked: {
    panel: 'border-red-300/90',
    accent: 'bg-red-500',
    icon: <PauseCircle className="h-5 w-5 text-red-600 flex-shrink-0" aria-hidden />,
    text: 'text-red-950',
    block: 'border-red-300 bg-red-50/85 text-red-900',
  },
}

// ─── 组件 ──────────────────────────────────────────────────────────────

export function StatusGuide({
  title,
  whatNow,
  blockReason,
  severity: explicitSeverity,
  primaryAction,
  secondaryActions,
  statusBadge,
  hint,
  className,
}: StatusGuideProps) {
  // 自动推断严重程度
  const severity: GuideSeverity =
    explicitSeverity ??
    (blockReason ? 'warning' : primaryAction ? 'info' : 'info')

  const style = SEVERITY_STYLE[severity]

  return (
    <div
      className={cn(
        'mo-blueprint-panel mo-dossier-surface relative overflow-hidden rounded-lg border px-5 py-4 shadow-sm shadow-slate-900/5',
        severity === 'warning' && 'mo-node-waiting',
        style.panel,
        className,
      )}
      role="status"
      aria-live="polite"
    >
      <div className="mo-dossier-ornament" aria-hidden />
      <div className={cn('mo-scan-line absolute inset-y-0 left-0 w-1.5', style.accent)} aria-hidden />
      <div className="pointer-events-none absolute right-4 top-3 z-10 hidden font-mono text-[10px] uppercase tracking-[0.26em] text-muted-foreground/55 sm:block">
        dossier
      </div>
      <div className="relative z-10 flex items-start gap-4">
        {/* 图标 */}
        <div className="rounded-md border border-white/70 bg-background/72 p-1.5 shadow-sm">
          {style.icon}
        </div>

        {/* 主要内容 */}
        <div className="flex-1 min-w-0">
          {/* 标题行 */}
          <div className="flex items-center justify-between gap-3 flex-wrap">
            <h1 className={cn('text-base font-semibold tracking-[0.01em]', style.text)}>
              {title}
            </h1>
            {statusBadge}
          </div>

          {/* 当前做什么 */}
          <p className={cn('mt-1 text-sm', style.text, 'opacity-85')}>
            {whatNow}
          </p>

          {/* 阻塞原因 */}
          {blockReason && (
            <div
              className={cn(
                'mt-2 flex items-start gap-2 rounded-md border px-3 py-2 text-sm font-medium shadow-[0_1px_0_rgba(255,255,255,0.72)_inset]',
                style.block,
              )}
            >
              <AlertCircle className="h-4 w-4 mt-0.5 flex-shrink-0" aria-hidden />
              <span>{blockReason}</span>
            </div>
          )}

          {/* 提示 */}
          {hint && !blockReason && (
            <div className="mt-2 flex items-start gap-2 text-xs text-muted-foreground">
              <HelpCircle className="h-3.5 w-3.5 mt-0.5 flex-shrink-0" aria-hidden />
              <span>{hint}</span>
            </div>
          )}

          {/* 行动按钮 */}
          {(primaryAction || (secondaryActions && secondaryActions.length > 0)) && (
            <div className="mt-3 flex items-center gap-2 flex-wrap">
              {primaryAction && (
                primaryAction.href || primaryAction.to ? (
                  <Button
                    size="sm"
                    variant={primaryAction.destructive ? 'destructive' : 'default'}
                    disabled={primaryAction.disabled}
                    asChild
                  >
                    <LinkedActionContent action={primaryAction} showArrow />
                  </Button>
                ) : (
                  <Button
                    size="sm"
                    variant={primaryAction.destructive ? 'destructive' : 'default'}
                    disabled={primaryAction.disabled}
                    onClick={primaryAction.onClick}
                  >
                    <ActionLabel action={primaryAction} showArrow />
                  </Button>
                )
              )}
              {secondaryActions?.map((action, idx) =>
                action.href || action.to ? (
                  <Button
                    key={idx}
                    size="sm"
                    variant={action.destructive ? 'destructive' : 'outline'}
                    disabled={action.disabled}
                    asChild
                  >
                    <LinkedActionContent action={action} />
                  </Button>
                ) : (
                  <Button
                    key={idx}
                    size="sm"
                    variant={action.destructive ? 'destructive' : 'outline'}
                    disabled={action.disabled}
                    onClick={action.onClick}
                  >
                    {action.label}
                  </Button>
                ),
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
