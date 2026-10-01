import { Fragment, type ReactNode } from 'react'

/**
 * Minimal, safe Markdown renderer for tutor answers.
 * Supports headings, bold, italic, inline code, fenced code blocks, and bulleted / numbered lists.
 * Everything is rendered as React elements (no HTML injection), so model output cannot inject markup.
 */
function renderInline(text: string, keyPrefix: string): ReactNode[] {
  const nodes: ReactNode[] = []
  const pattern = /(\*\*[^*]+\*\*|`[^`]+`|\*[^*\s][^*]*\*)/g
  let last = 0
  let match: RegExpExecArray | null
  let i = 0
  while ((match = pattern.exec(text)) !== null) {
    if (match.index > last) nodes.push(text.slice(last, match.index))
    const token = match[0]
    const key = `${keyPrefix}-${i++}`
    if (token.startsWith('**')) {
      nodes.push(<strong key={key} className="font-semibold text-foreground">{token.slice(2, -2)}</strong>)
    } else if (token.startsWith('`')) {
      nodes.push(
        <code key={key} className="rounded bg-muted px-1 py-0.5 font-mono text-[0.85em]">
          {token.slice(1, -1)}
        </code>
      )
    } else {
      nodes.push(<em key={key}>{token.slice(1, -1)}</em>)
    }
    last = match.index + token.length
  }
  if (last < text.length) nodes.push(text.slice(last))
  return nodes
}

export function MarkdownText({ content }: { content: string }) {
  const lines = (content || '').replace(/\r\n/g, '\n').split('\n')
  const blocks: ReactNode[] = []
  let list: { ordered: boolean; items: string[] } | null = null
  let paragraph: string[] = []
  let code: string[] | null = null

  const flushParagraph = () => {
    if (paragraph.length) {
      const k = `p${blocks.length}`
      blocks.push(
        <p key={k}>
          {paragraph.map((l, idx) => (
            <Fragment key={idx}>
              {idx > 0 && <br />}
              {renderInline(l, `${k}-${idx}`)}
            </Fragment>
          ))}
        </p>
      )
      paragraph = []
    }
  }
  const flushList = () => {
    if (list) {
      const k = `l${blocks.length}`
      const Tag = list.ordered ? 'ol' : 'ul'
      blocks.push(
        <Tag key={k} className={list.ordered ? 'list-decimal space-y-1 pl-5' : 'list-disc space-y-1 pl-5'}>
          {list.items.map((item, idx) => (
            <li key={idx}>{renderInline(item, `${k}-${idx}`)}</li>
          ))}
        </Tag>
      )
      list = null
    }
  }

  for (const raw of lines) {
    const line = raw.trimEnd()
    if (code !== null) {
      if (line.trim().startsWith('```')) {
        blocks.push(
          <pre key={`c${blocks.length}`} className="overflow-x-auto rounded-xl bg-muted p-3 font-mono text-xs">
            {code.join('\n')}
          </pre>
        )
        code = null
      } else {
        code.push(raw)
      }
      continue
    }
    if (line.trim().startsWith('```')) {
      flushParagraph()
      flushList()
      code = []
      continue
    }
    const heading = /^(#{1,4})\s+(.*)$/.exec(line)
    const bullet = /^\s*[-*•]\s+(.*)$/.exec(line)
    const numbered = /^\s*\d+[.)]\s+(.*)$/.exec(line)
    if (heading) {
      flushParagraph()
      flushList()
      blocks.push(
        <p key={`h${blocks.length}`} className="font-display font-semibold text-foreground">
          {renderInline(heading[2], `h${blocks.length}`)}
        </p>
      )
    } else if (bullet || numbered) {
      flushParagraph()
      const ordered = Boolean(numbered)
      if (!list || list.ordered !== ordered) {
        flushList()
        list = { ordered, items: [] }
      }
      list.items.push((bullet || numbered)![1])
    } else if (!line.trim()) {
      flushParagraph()
      flushList()
    } else {
      flushList()
      paragraph.push(line)
    }
  }
  if (code !== null) {
    blocks.push(
      <pre key={`c${blocks.length}`} className="overflow-x-auto rounded-xl bg-muted p-3 font-mono text-xs">
        {(code as string[]).join('\n')}
      </pre>
    )
  }
  flushParagraph()
  flushList()

  return <div className="space-y-3 leading-relaxed">{blocks}</div>
}
