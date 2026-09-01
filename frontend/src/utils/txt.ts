// txt 公司名单解析纯函数（PRD 4.12 批量导入）：解码与按行解析
// 全部为纯函数，便于单测（见 src/utils/__tests__/txt.spec.ts）

import type { CompanyImportRow } from '@/types'

/** txt 单行解析出的公司信息（缺失属性为 null） */
export type ParsedCompanyRow = CompanyImportRow

/** 明显不属于属性内容的占位词（如「官网未公开」），导入时视为缺失置空 */
const PLACEHOLDER_VALUES = new Set([
  '',
  '-',
  '—',
  '–',
  '/',
  '\\',
  '无',
  '没有',
  '未知',
  '未公开',
  '官网未公开',
  '暂无',
  '不详',
  '缺失',
  '待补充',
  '待定',
  'n/a',
  'na',
  'null',
  'none',
  'unknown',
])

/** 清洗单列取值：空值或占位词返回 null，其余 trim 后返回 */
function sanitizeField(raw: string | undefined): string | null {
  const text = (raw ?? '').trim()
  if (PLACEHOLDER_VALUES.has(text) || PLACEHOLDER_VALUES.has(text.toLowerCase())) return null
  return text
}

/**
 * 按行解析结构化公司信息：
 * - 每行按【公司全称】 【城市】 【行业】 【公司性质】 【公司官网】顺序以空格分隔，允许只给公司名
 * - 兼容 \r\n / \r / \n 换行，忽略空行
 * - 缺失列或占位内容（「官网未公开」「无」「-」等）置为 null
 * - 按公司名去重（保留首次出现）
 */
export function parseCompanyLines(text: string): ParsedCompanyRow[] {
  const seen = new Set<string>()
  const result: ParsedCompanyRow[] = []
  for (const raw of String(text).split(/\r\n|\r|\n/)) {
    const line = raw.trim()
    if (!line) continue
    const parts = line.split(/\s+/)
    const name = sanitizeField(parts[0])
    if (!name || seen.has(name)) continue
    seen.add(name)
    result.push({
      name,
      city: sanitizeField(parts[1]),
      industry: sanitizeField(parts[2]),
      nature: sanitizeField(parts[3]),
      website: sanitizeField(parts[4]),
    })
  }
  return result
}

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
