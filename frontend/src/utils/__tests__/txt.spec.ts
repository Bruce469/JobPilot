import { describe, expect, it } from 'vitest'
import { decodeTxtBuffer, parseCompanyLines, parseTxtLines } from '../txt'

describe('parseTxtLines（txt 按行解析）', () => {
  it('按行拆分、trim 首尾空格、忽略空行', () => {
    expect(parseTxtLines('字节跳动\n腾讯  \n  \r\n 阿里巴巴 \n')).toEqual(['字节跳动', '腾讯', '阿里巴巴'])
  })

  it('兼容 \\r\\n 与 \\r 换行符', () => {
    expect(parseTxtLines('a\r\nb\rc\nd')).toEqual(['a', 'b', 'c', 'd'])
  })

  it('去重并保留首次出现顺序', () => {
    expect(parseTxtLines('字节跳动\n腾讯\n字节跳动\n腾讯\n美团')).toEqual(['字节跳动', '腾讯', '美团'])
  })

  it('空文本 / 全空白行返回空数组', () => {
    expect(parseTxtLines('')).toEqual([])
    expect(parseTxtLines('  \n\t\r\n  ')).toEqual([])
  })

  it('行内全角/半角空格保留（仅去首尾空白）', () => {
    expect(parseTxtLines('  字节跳动  ')).toEqual(['字节跳动'])
    expect(parseTxtLines('北 京 字节跳动')).toEqual(['北 京 字节跳动'])
  })
})

describe('parseCompanyLines（txt 结构化公司信息解析）', () => {
  it('按空格拆出名称/城市/行业/性质/官网五个字段', () => {
    expect(parseCompanyLines('字节跳动 北京 互联网 民营企业 https://www.bytedance.com')).toEqual([
      { name: '字节跳动', city: '北京', industry: '互联网', nature: '民营企业', website: 'https://www.bytedance.com' },
    ])
  })

  it('兼容 \\r\\n 与 \\r 换行、忽略空行、按公司名去重', () => {
    const text = '字节跳动 北京\r\n\r\n腾讯 深圳\r\n字节跳动 上海\n美团\t'
    expect(parseCompanyLines(text)).toEqual([
      { name: '字节跳动', city: '北京', industry: null, nature: null, website: null },
      { name: '腾讯', city: '深圳', industry: null, nature: null, website: null },
      { name: '美团', city: null, industry: null, nature: null, website: null },
    ])
  })

  it('占位内容（官网未公开 / 无 / - / 未知等）置为空', () => {
    expect(parseCompanyLines('某公司 北京 互联网 官网未公开 官网未公开')).toEqual([
      { name: '某公司', city: '北京', industry: '互联网', nature: null, website: null },
    ])
    expect(parseCompanyLines('某公司 无 - / 未知')).toEqual([
      { name: '某公司', city: null, industry: null, nature: null, website: null },
    ])
  })

  it('仅公司名的旧格式文件兼容解析', () => {
    expect(parseCompanyLines('字节跳动\n腾讯')).toEqual([
      { name: '字节跳动', city: null, industry: null, nature: null, website: null },
      { name: '腾讯', city: null, industry: null, nature: null, website: null },
    ])
  })

  it('中间列缺失用占位词占位时不影响后续列位置', () => {
    expect(parseCompanyLines('国家电网 北京 - 国企 https://www.sgcc.com.cn')).toEqual([
      { name: '国家电网', city: '北京', industry: null, nature: '国企', website: 'https://www.sgcc.com.cn' },
    ])
  })

  it('空文本 / 全占位行返回空数组', () => {
    expect(parseCompanyLines('')).toEqual([])
    expect(parseCompanyLines('  \n\r\n')).toEqual([])
    expect(parseCompanyLines('无\n-')).toEqual([])
  })
})

describe('decodeTxtBuffer（UTF-8/GBK 兼容解码）', () => {
  it('UTF-8 字节按 UTF-8 解码', () => {
    const bytes = new TextEncoder().encode('字节跳动\n腾讯')
    expect(decodeTxtBuffer(bytes.buffer)).toBe('字节跳动\n腾讯')
  })

  it('UTF-8 带 BOM 时正常解码（BOM 被剥离）', () => {
    const bytes = new Uint8Array([0xef, 0xbb, 0xbf, 0xe5, 0xad, 0x97]) // BOM + "字"
    expect(decodeTxtBuffer(bytes.buffer)).toBe('字')
  })

  it('GBK 字节（非合法 UTF-8）回退 GBK 解码', () => {
    // "字节跳动" 的 GBK 编码
    const gbk = new Uint8Array([0xd7, 0xd6, 0xbd, 0xda, 0xcc, 0xf8, 0xb6, 0xaf])
    expect(decodeTxtBuffer(gbk.buffer)).toBe('字节跳动')
  })

  it('空内容返回空字符串', () => {
    expect(decodeTxtBuffer(new ArrayBuffer(0))).toBe('')
  })

  it('解码后可被 parseTxtLines 继续解析（集成）', () => {
    const gbk = new Uint8Array([
      0xd7, 0xd6, 0xbd, 0xda, 0xcc, 0xf8, 0xb6, 0xaf, 0x0d, 0x0a, // 字节跳动\r\n
      0xb0, 0xd9, 0xb6, 0xc8, 0x0a, // 百度\n（末尾带换行）
    ])
    expect(parseTxtLines(decodeTxtBuffer(gbk.buffer))).toEqual(['字节跳动', '百度'])
  })
})
