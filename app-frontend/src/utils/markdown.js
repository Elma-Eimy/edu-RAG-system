/**
 * A lightweight, zero-dependency Markdown parser for rendering AI responses.
 * Supported features: Bold (**), Italic (*), Headers (#), Bullet/Numbered lists, Inline code (`), and Fenced code blocks (```).
 * Automatically escapes HTML for XSS prevention and cleans up newlines to respect white-space styling.
 */
export function renderMarkdown(text) {
  if (!text) return ''

  // 1. Escape HTML for XSS prevention
  let html = text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')

  // 2. Fenced code blocks (placeholder to protect newlines and syntax)
  const codeBlocks = []
  html = html.replace(/```([\s\S]*?)```/g, (match, code) => {
    const placeholder = `__CODE_BLOCK_PLACEHOLDER_${codeBlocks.length}__`
    codeBlocks.push(`<pre class="code-block"><code>${code.trim()}</code></pre>`)
    return placeholder
  })

  // 3. Inline code
  const inlineCodes = []
  html = html.replace(/`([^`\n]+)`/g, (match, code) => {
    const placeholder = `__INLINE_CODE_PLACEHOLDER_${inlineCodes.length}__`
    inlineCodes.push(`<code>${code}</code>`)
    return placeholder
  })

  // 4. Bold and Italic
  html = html.replace(/\*\*([\s\S]*?)\*\*/g, '<strong>$1</strong>')
  html = html.replace(/\*([\s\S]*?)\*/g, '<em>$1</em>')

  // 5. Headers (# to ######)
  html = html.replace(/^(#{1,6})\s+(.+)$/gm, (match, hashes, title) => {
    const level = hashes.length
    return `<h${level}>${title}</h${level}>`
  })

  // 6. Lists (Bullet lists & Numbered lists)
  const lines = html.split('\n')
  let inUl = false
  let inOl = false
  const processedLines = []

  for (let line of lines) {
    const trimmed = line.trim()
    
    // Check for bullet lists
    if (trimmed.startsWith('- ') || trimmed.startsWith('* ') || trimmed.startsWith('+ ')) {
      if (inOl) {
        processedLines.push('</ol>')
        inOl = false
      }
      const content = trimmed.substring(2).trim()
      if (!inUl) {
        processedLines.push('<ul>')
        inUl = true
      }
      processedLines.push(`<li>${content}</li>`)
    } 
    // Check for numbered lists (e.g. 1. Item)
    else if (/^\d+\.\s+/.test(trimmed)) {
      if (inUl) {
        processedLines.push('</ul>')
        inUl = false
      }
      const match = trimmed.match(/^(\d+)\.\s+(.+)$/)
      const content = match[2].trim()
      if (!inOl) {
        processedLines.push('<ol>')
        inOl = true
      }
      processedLines.push(`<li>${content}</li>`)
    } 
    // Regular line
    else {
      if (inUl) {
        processedLines.push('</ul>')
        inUl = false
      }
      if (inOl) {
        processedLines.push('</ol>')
        inOl = false
      }
      processedLines.push(line)
    }
  }

  if (inUl) processedLines.push('</ul>')
  if (inOl) processedLines.push('</ol>')

  html = processedLines.join('\n')

  // 7. Paragraphs & Line breaks
  const blocks = html.split(/\n\s*\n/)
  const parsedBlocks = blocks.map(block => {
    const trimmed = block.trim()
    if (!trimmed) return ''
    
    // If it's already a list, header, code block placeholder, don't wrap in <p>
    if (
      trimmed.startsWith('<ul>') || 
      trimmed.startsWith('<ol>') || 
      trimmed.startsWith('<h') || 
      trimmed.startsWith('__CODE_BLOCK_PLACEHOLDER')
    ) {
      return trimmed
    }
    
    // Otherwise wrap in <p> and replace single newlines with <br>
    const content = trimmed.replace(/\n/g, '<br>')
    return `<p>${content}</p>`
  })
  
  html = parsedBlocks.filter(b => b).join('')

  // Strip all newlines outside code blocks to prevent white-space: pre-wrap issues
  html = html.replace(/\n/g, '')

  // 8. Restore code blocks and inline code
  codeBlocks.forEach((codeHtml, idx) => {
    html = html.replace(`__CODE_BLOCK_PLACEHOLDER_${idx}__`, codeHtml)
  })
  
  inlineCodes.forEach((inlineHtml, idx) => {
    html = html.replace(`__INLINE_CODE_PLACEHOLDER_${idx}__`, inlineHtml)
  })

  return html
}
