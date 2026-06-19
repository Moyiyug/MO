/**
 * SupportingDrawer — 右侧滑出面板
 *
 * 自定义右侧抽屉面板。支持：
 * - Escape 键关闭
 * - Tab 焦点陷阱（打开后 Tab 在抽屉内循环）
 * - 背景滚动锁定
 * - 关闭后恢复焦点
 *
 * 使用示例：
 *   <SupportingDrawer open={open} onClose={() => setOpen(false)} title="节点详情">
 *     <NodeDetailContent />
 *   </SupportingDrawer>
 */

import { useEffect, useRef, type ReactNode } from 'react'
import { X } from 'lucide-react'

import { cn } from '@/lib/utils'

// ─── 类型 ──────────────────────────────────────────────────────────────

export interface SupportingDrawerProps {
  open: boolean
  onClose: () => void
  title: string
  children: ReactNode
  /** 是否标记为技术详情 */
  technical?: boolean
  /** 面板宽度 */
  width?: 'sm' | 'md' | 'lg'
  className?: string
}

const WIDTH_CLASS: Record<string, string> = {
  sm: 'max-w-sm',
  md: 'max-w-md',
  lg: 'max-w-lg',
}

const FOCUSABLE_SELECTOR =
  'a[href], button:not([disabled]), input:not([disabled]), textarea:not([disabled]), select:not([disabled]), [tabindex]:not([tabindex="-1"])'

// ─── 组件 ──────────────────────────────────────────────────────────────

export function SupportingDrawer({
  open,
  onClose,
  title,
  children,
  technical = false,
  width = 'md',
  className,
}: SupportingDrawerProps) {
  const panelRef = useRef<HTMLElement>(null)
  const prevFocusRef = useRef<HTMLElement | null>(null)

  useEffect(() => {
    if (!open) return

    // 记住打开前焦点
    prevFocusRef.current = document.activeElement as HTMLElement

    // 锁定背景滚动
    const prevOverflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'

    // 焦点移入抽屉
    const timer = setTimeout(() => {
      const panel = panelRef.current
      if (!panel) return
      const firstFocusable = panel.querySelector<HTMLElement>(FOCUSABLE_SELECTOR)
      firstFocusable?.focus()
    }, 100)

    // 键盘处理
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        onClose()
        return
      }
      if (e.key === 'Tab') {
        const panel = panelRef.current
        if (!panel) return
        const focusables = panel.querySelectorAll<HTMLElement>(FOCUSABLE_SELECTOR)
        if (focusables.length === 0) {
          e.preventDefault()
          return
        }
        const first = focusables[0]
        const last = focusables[focusables.length - 1]
        if (e.shiftKey) {
          // Shift+Tab：如果当前焦点是第一个，循环到最后
          if (document.activeElement === first) {
            e.preventDefault()
            last.focus()
          }
        } else {
          // Tab：如果当前焦点是最后一个，循环到第一个
          if (document.activeElement === last) {
            e.preventDefault()
            first.focus()
          }
        }
      }
    }

    document.addEventListener('keydown', handleKeyDown)

    return () => {
      clearTimeout(timer)
      document.removeEventListener('keydown', handleKeyDown)
      document.body.style.overflow = prevOverflow
      // 恢复焦点
      prevFocusRef.current?.focus()
    }
  }, [open, onClose])

  if (!open) return null

  return (
    <>
      {/* 遮罩层 */}
      <div
        className="fixed inset-0 z-40 bg-slate-950/38 backdrop-blur-[2px] transition-opacity"
        aria-hidden
        onClick={onClose}
      />

      {/* 抽屉面板 */}
      <aside
        ref={panelRef}
        role="dialog"
        aria-modal="true"
        aria-label={title}
        className={cn(
          'fixed right-0 top-0 z-50 h-full w-full sm:w-96 lg:max-w-md',
          'mo-blueprint-panel border-l border-blue-200/80 bg-background/92 shadow-2xl shadow-slate-900/20',
          'flex min-w-0 flex-col',
          'animate-in slide-in-from-right duration-300',
          WIDTH_CLASS[width],
          className,
        )}
      >
        {/* 头部 */}
        <div className="mo-subtle-field flex items-center justify-between gap-2 border-b border-[var(--mo-line)] px-5 py-4">
          <div className="flex items-center gap-2 min-w-0">
            <h3 className="truncate text-base font-semibold tracking-wide text-[var(--mo-ink)]">
              {title}
            </h3>
            {technical && (
              <span className="flex-shrink-0 rounded border border-blue-200 bg-blue-50 px-1.5 py-0.5 text-[10px] uppercase tracking-[0.16em] text-blue-700">
                技术详情
              </span>
            )}
          </div>
          <button
            type="button"
            onClick={onClose}
            className="flex-shrink-0 rounded-md border border-transparent p-1.5 text-muted-foreground transition-colors hover:border-blue-200 hover:bg-blue-50 hover:text-blue-800"
            aria-label="关闭"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        {/* 内容区 */}
        <div className="min-h-0 flex-1 overflow-y-auto px-5 py-4 text-sm break-words">
          {children}
        </div>
      </aside>
    </>
  )
}
