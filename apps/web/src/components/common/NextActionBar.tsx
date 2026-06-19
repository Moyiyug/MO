/**
 * NextActionBar — 页面内联操作栏
 *
 * 规则：
 * - 主 CTA 只保留一个（variant="default"）
 * - 次要动作使用 outline/ghost
 * - 危险动作使用 destructive + 内置二次确认 Dialog
 *
 * 使用示例：
 *   <NextActionBar
 *     primary={{ label: '批准并开始执行', onClick: handleApprove }}
 *     secondary={[{ label: '重新生成', onClick: handleRegenerate }]}
 *     destructive={{ label: '删除', onClick: handleDelete }}
 *     destructiveConfirm={{ title: '确认删除', description: '...', confirmLabel: '确认删除' }}
 *     backTo={{ label: '返回历史', href: '/history' }}
 *   />
 */

import { useState, type ReactNode } from 'react'
import { Link } from 'react-router-dom'
import { AlertTriangle, ArrowRight } from 'lucide-react'

import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { cn } from '@/lib/utils'

// ─── 类型 ──────────────────────────────────────────────────────────────

export interface PrimaryAction {
  label: string
  onClick?: () => void
  /** 站内路由，使用 React Router Link，避免整页刷新 */
  to?: string
  href?: string
  disabled?: boolean
  destructive?: boolean
}

export interface NavItem {
  label: string
  /** 站内路由，使用 React Router Link，避免整页刷新 */
  to?: string
  href?: string
  onClick?: () => void
  active?: boolean
  icon?: ReactNode
}

function isInternalHref(href: string | undefined): href is string {
  return Boolean(href && href.startsWith('/'))
}

function ActionContent({
  action,
  showArrow,
}: {
  action: PrimaryAction | NavItem
  showArrow?: boolean
}) {
  return (
    <>
      {'icon' in action ? action.icon : null}
      {action.label}
      {showArrow && <ArrowRight className="ml-1.5 h-3.5 w-3.5" aria-hidden />}
    </>
  )
}

function ActionLink({
  action,
  showArrow,
}: {
  action: PrimaryAction | NavItem
  showArrow?: boolean
}) {
  const target = action.to ?? (isInternalHref(action.href) ? action.href : undefined)
  if (target) {
    return (
      <Link to={target}>
        <ActionContent action={action} showArrow={showArrow} />
      </Link>
    )
  }
  return (
    <a href={action.href}>
      <ActionContent action={action} showArrow={showArrow} />
    </a>
  )
}

export interface NextActionBarProps {
  /** 唯一主 CTA */
  primary?: PrimaryAction
  /** 次要操作（最多 3 个） */
  secondary?: PrimaryAction[]
  /** 危险操作 */
  destructive?: PrimaryAction
  /** 危险操作的二次确认文案 */
  destructiveConfirm?: {
    title: string
    description: string
    confirmLabel?: string
  }
  /** 左侧返回/导航 */
  backTo?: NavItem
  className?: string
}

// ─── 组件 ──────────────────────────────────────────────────────────────

export function NextActionBar({
  primary,
  secondary,
  destructive,
  destructiveConfirm,
  backTo,
  className,
}: NextActionBarProps) {
  const [showDestructiveConfirm, setShowDestructiveConfirm] = useState(false)

  const hasActions = primary || (secondary && secondary.length > 0) || destructive

  if (!hasActions && !backTo) return null

  return (
    <>
      <div
        className={cn(
          'relative z-10 flex items-center justify-between gap-3 flex-wrap',
          'mo-blueprint-panel rounded-lg border bg-card/90 px-5 py-3 shadow-sm',
          className,
        )}
      >
        {/* 左侧：返回 */}
        <div>
          {backTo && (
            backTo.href || backTo.to ? (
              <Button variant="ghost" size="sm" asChild>
                <ActionLink action={backTo} />
              </Button>
            ) : (
              <Button variant="ghost" size="sm" onClick={backTo.onClick}>
                {backTo.icon}
                {backTo.label}
              </Button>
            )
          )}
        </div>

        {/* 右侧：操作按钮组 */}
        <div className="flex items-center gap-2 flex-wrap">
          {/* 危险操作 */}
          {destructive && (
            <Button
              variant="destructive"
              size="sm"
              disabled={destructive.disabled}
              onClick={() => {
                if (destructiveConfirm) {
                  setShowDestructiveConfirm(true)
                } else {
                  destructive.onClick?.()
                }
              }}
            >
              {destructive.label}
            </Button>
          )}

          {/* 次要操作 */}
          {secondary?.map((action, idx) =>
            action.href || action.to ? (
              <Button key={idx} variant="outline" size="sm" disabled={action.disabled} asChild>
                <ActionLink action={action} />
              </Button>
            ) : (
              <Button
                key={idx}
                variant="outline"
                size="sm"
                disabled={action.disabled}
                onClick={action.onClick}
              >
                {action.label}
              </Button>
            ),
          )}

          {/* 主 CTA */}
          {primary && (
            primary.href || primary.to ? (
              <Button size="sm" disabled={primary.disabled} asChild>
                <ActionLink action={primary} showArrow />
              </Button>
            ) : (
              <Button size="sm" disabled={primary.disabled} onClick={primary.onClick}>
                <ActionContent action={primary} showArrow />
              </Button>
            )
          )}
        </div>
      </div>

      {/* 危险操作确认 Dialog */}
      {destructiveConfirm && (
        <Dialog open={showDestructiveConfirm} onOpenChange={setShowDestructiveConfirm}>
          <DialogContent>
            <DialogHeader>
              <DialogTitle className="flex items-center gap-2">
                <AlertTriangle className="h-5 w-5 text-destructive" aria-hidden />
                {destructiveConfirm.title}
              </DialogTitle>
              <DialogDescription>{destructiveConfirm.description}</DialogDescription>
            </DialogHeader>
            <DialogFooter>
              <Button variant="outline" size="sm" onClick={() => setShowDestructiveConfirm(false)}>
                取消
              </Button>
              <Button
                variant="destructive"
                size="sm"
                onClick={() => {
                  setShowDestructiveConfirm(false)
                  destructive?.onClick?.()
                }}
              >
                {destructiveConfirm.confirmLabel ?? destructive?.label ?? '确认'}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      )}
    </>
  )
}
