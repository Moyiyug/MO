import type { ReactNode } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import rehypeSanitize from 'rehype-sanitize'
import { ExternalLink, GitBranch } from 'lucide-react'

interface SafeMarkdownProps {
  markdown: string
  className?: string
}

function headingIdFromChildren(children: ReactNode): string | undefined {
  const text = String(children).trim()
  if (text.startsWith('evidence-')) {
    return text
  }
  return undefined
}

/** Markdown 安全渲染 — 必须 rehype-sanitize，禁止原始 HTML。外部链接添加 target=_blank。Mermaid 代码块显示图表标签。 */
export function SafeMarkdown({ markdown, className }: SafeMarkdownProps) {
  return (
    <div className={className}>
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        rehypePlugins={[rehypeSanitize]}
        components={{
          h3: ({ children, ...props }) => {
            const id = headingIdFromChildren(children)
            return (
              <h3 id={id} {...props}>
                {children}
              </h3>
            )
          },
          a: ({ href, children, ...props }) => {
            const isExternal = href && (href.startsWith('http://') || href.startsWith('https://'))
            return (
              <a
                href={href}
                target={isExternal ? '_blank' : undefined}
                rel={isExternal ? 'noopener noreferrer' : undefined}
                className="inline-flex items-center gap-0.5 text-primary underline underline-offset-2 hover:no-underline"
                {...props}
              >
                {children}
                {isExternal && <ExternalLink className="h-3 w-3 inline" aria-hidden />}
              </a>
            )
          },
          code: ({ className: codeClass, children, ...props }) => {
            const isBlock = codeClass?.startsWith('language-')
            const isMermaid = codeClass === 'language-mermaid'

            if (isMermaid) {
              // Mermaid 图表：显示带标签的代码块占位符
              return (
                <div className="my-4 rounded-lg border-2 border-dashed border-blue-300 bg-blue-50/50 p-4">
                  <div className="flex items-center gap-2 mb-2 text-blue-700">
                    <GitBranch className="h-4 w-4" aria-hidden />
                    <span className="text-sm font-medium">Mermaid 图表</span>
                  </div>
                  <pre className="overflow-x-auto text-xs text-blue-900/70 font-mono whitespace-pre-wrap">
                    {children}
                  </pre>
                  <p className="mt-2 text-xs text-blue-600/70">
                    图表渲染功能即将上线，当前显示为原始代码。
                  </p>
                </div>
              )
            }

            return (
              <code
                className={
                  isBlock
                    ? `block bg-muted rounded-md p-3 text-sm font-mono overflow-x-auto ${codeClass ?? ''}`
                    : 'bg-muted rounded px-1.5 py-0.5 text-xs font-mono'
                }
                {...props}
              >
                {children}
              </code>
            )
          },
          pre: ({ children, ...props }) => (
            <pre className="my-3 overflow-x-auto" {...props}>
              {children}
            </pre>
          ),
        }}
      >
        {markdown}
      </ReactMarkdown>
    </div>
  )
}
