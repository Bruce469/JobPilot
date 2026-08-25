import { describe, expect, it } from 'vitest'
import { decodeTxtBuffer, parseTxtLines } from '../txt'

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
