/**
 * 用于渲染 AI 回复的轻量级、无依赖 Markdown 解析器。
 * 支持的功能：加粗 (**)、斜体 (*)、标题 (#)、无序/有序列表、行内代码 (`) 以及围栏代码块 (```)。
 * 自动转义 HTML 以防御 XSS，并清理换行符以契合空白样式设置。
 */
export function renderMarkdown(text) {
  if (!text) return ''

  // 1. 转义 HTML 以防御 XSS 攻击
  let html = text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')

  // 2. 围栏代码块（使用占位符以保护换行符和语法）
  const codeBlocks = []
  html = html.replace(/```([a-zA-Z0-9#\+\-]+)?(?:\r?\n)?([\s\S]*?)```/g, (match, lang, code) => {
    const placeholder = `__CODE_BLOCK_PLACEHOLDER_${codeBlocks.length}__`
    const language = lang ? lang.trim() : ''
    const cleanCode = code.trim()
    const languageClass = language ? ` class="language-${language}"` : ''
    const headerHtml = language ? `<div class="code-block-header">${language}</div>` : ''
    codeBlocks.push(`<div class="code-block-container">${headerHtml}<pre class="code-block"><code${languageClass}>${cleanCode}</code></pre></div>`)
    return placeholder
  })

  // 3. 行内代码
  const inlineCodes = []
  html = html.replace(/`([^`\n]+)`/g, (match, code) => {
    const placeholder = `__INLINE_CODE_PLACEHOLDER_${inlineCodes.length}__`
    inlineCodes.push(`<code>${code}</code>`)
    return placeholder
  })

  // 4. 加粗和斜体
  html = html.replace(/\*\*([\s\S]*?)\*\*/g, '<strong>$1</strong>')
  html = html.replace(/\*([\s\S]*?)\*/g, '<em>$1</em>')

  // 5. 标题 (# 到 ######)
  html = html.replace(/^(#{1,6})\s+(.+)$/gm, (match, hashes, title) => {
    const level = hashes.length
    return `<h${level}>${title}</h${level}>`
  })

  // 5.5 水平分割线 (---)
  html = html.replace(/^\s*[-*_]{3,}\s*$/gm, '<hr>')

  // 6. 列表与引用块（无序列表、有序列表、引用块）
  const lines = html.split('\n')
  let inUl = false
  let inOl = false
  let inQuote = false
  const processedLines = []

  for (let line of lines) {
    const trimmed = line.trim()
    
    // 检查引用块
    if (trimmed.startsWith('>')) {
      if (inUl) {
        processedLines.push('</ul>')
        inUl = false
      }
      if (inOl) {
        processedLines.push('</ol>')
        inOl = false
      }
      const content = trimmed.substring(1).trim()
      if (!inQuote) {
        processedLines.push('<blockquote>')
        inQuote = true
      }
      processedLines.push(content)
    }
    // 检查无序列表
    else if (trimmed.startsWith('- ') || trimmed.startsWith('* ') || trimmed.startsWith('+ ')) {
      if (inQuote) {
        processedLines.push('</blockquote>')
        inQuote = false
      }
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
    // 检查有序列表（例如 1. Item）
    else if (/^\d+\.\s+/.test(trimmed)) {
      if (inQuote) {
        processedLines.push('</blockquote>')
        inQuote = false
      }
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
    // 普通行
    else {
      if (inUl) {
        processedLines.push('</ul>')
        inUl = false
      }
      if (inOl) {
        processedLines.push('</ol>')
        inOl = false
      }
      if (inQuote) {
        processedLines.push('</blockquote>')
        inQuote = false
      }
      processedLines.push(line)
    }
  }

  if (inUl) processedLines.push('</ul>')
  if (inOl) processedLines.push('</ol>')
  if (inQuote) processedLines.push('</blockquote>')

  html = processedLines.join('\n')

  // 7. 段落与换行符
  const blocks = html.split(/\n\s*\n/)
  const parsedBlocks = blocks.map(block => {
    const trimmed = block.trim()
    if (!trimmed) return ''
    
    // 如果已经是列表、标题、水平分割线、引用块或代码块占位符，则不要用 <p> 标签包裹
    if (
      trimmed.startsWith('<ul>') || 
      trimmed.startsWith('<ol>') || 
      trimmed.startsWith('<h') || 
      trimmed.startsWith('<hr>') || 
      trimmed.startsWith('<blockquote>') || 
      trimmed.startsWith('__CODE_BLOCK_PLACEHOLDER')
    ) {
      if (trimmed.startsWith('<blockquote>')) {
        const content = trimmed.slice(12, -13).trim().replace(/\n/g, '<br>')
        return `<blockquote>${content}</blockquote>`
      }
      return trimmed
    }
    
    // 否则用 <p> 包裹，并将单个换行符替换为 <br>
    const content = trimmed.replace(/\n/g, '<br>')
    return `<p>${content}</p>`
  })
  
  html = parsedBlocks.filter(b => b).join('')

  // 清除代码块之外的所有换行符，以防止 white-space: pre-wrap 样式导致的问题
  html = html.replace(/\n/g, '')

  // 8. 还原代码块和行内代码占位符
  codeBlocks.forEach((codeHtml, idx) => {
    html = html.replace(`__CODE_BLOCK_PLACEHOLDER_${idx}__`, codeHtml)
  })
  
  inlineCodes.forEach((inlineHtml, idx) => {
    html = html.replace(`__INLINE_CODE_PLACEHOLDER_${idx}__`, inlineHtml)
  })

  return html
}
