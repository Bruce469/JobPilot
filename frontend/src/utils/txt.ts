// txt 公司名单解析纯函数（PRD 4.12 批量导入）：解码与按行解析
// 全部为纯函数，便于单测（见 src/utils/__tests__/txt.spec.ts）

/**
 * 按行解析公司名单：
 * - 兼容 \r\n / \r / \n 换行
 * - 忽略空行，trim 首尾空格
 * - 去重（保留首次出现）
 */
export function parseTxtLines(text: string): string[] {
  const seen = new Set<string>()
  const result: string[] = []
  for (const raw of String(text).split(/\r\n|\r|\n/)) {
    const line = raw.trim()
    if (!line) continue
    if (seen.has(line)) continue
    seen.add(line)
    result.push(line)
  }
  return result
}

/**
 * 兼容解码 txt 文件字节：优先 UTF-8 严格解码，失败（说明非 UTF-8）回退 GBK；
 * 若运行环境不支持 gbk 标签，退化为非严格 UTF-8（替换字符兜底，尽量不抛错）。
 */
export function decodeTxtBuffer(buffer: ArrayBuffer): string {
  try {
    return new TextDecoder('utf-8', { fatal: true }).decode(buffer)
  } catch {
    try {
      return new TextDecoder('gbk').decode(buffer)
    } catch {
      return new TextDecoder('utf-8').decode(buffer)
    }
  }
}
