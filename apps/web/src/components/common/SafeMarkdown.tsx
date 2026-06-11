import type { ReactNode } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import rehypeSanitize from 'rehype-sanitize'

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

/** Markdown 安全渲染 — 必须 rehype-sanitize，禁止原始 HTML */
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
        }}
      >
        {markdown}
      </ReactMarkdown>
    </div>
  )
}
