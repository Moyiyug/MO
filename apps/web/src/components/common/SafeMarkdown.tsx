import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import rehypeSanitize from 'rehype-sanitize'

interface SafeMarkdownProps {
  markdown: string
  className?: string
}

/** Markdown 安全渲染 — 必须 rehype-sanitize，禁止原始 HTML */
export function SafeMarkdown({ markdown, className }: SafeMarkdownProps) {
  return (
    <div className={className}>
      <ReactMarkdown remarkPlugins={[remarkGfm]} rehypePlugins={[rehypeSanitize]}>
        {markdown}
      </ReactMarkdown>
    </div>
  )
}
