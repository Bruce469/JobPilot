import { describe, expect, it } from 'vitest'
import { mergeCandidates, withRecentOnTop } from '../options'

describe('mergeCandidates', () => {
  it('静态在前、DB 在后，保序去重', () => {
    expect(mergeCandidates(['互联网', '金融'], ['金融', '半导体'])).toEqual(['互联网', '金融', '半导体'])
  })

  it('DB 独有的值（不在静态常量中）被保留', () => {
    expect(mergeCandidates(['互联网'], ['半导体', '芯片'])).toEqual(['互联网', '半导体', '芯片'])
  })

  it('静态值为空时仅剩 DB 值', () => {
    expect(mergeCandidates([], ['半导体'])).toEqual(['半导体'])
  })

  it('DB 值为空时仅剩静态值', () => {
    expect(mergeCandidates(['互联网', '金融'], [])).toEqual(['互联网', '金融'])
  })

  it('两者都为空返回空数组', () => {
    expect(mergeCandidates([], [])).toEqual([])
  })
})

describe('withRecentOnTop', () => {
  it('recent 置顶、池内其余值保序补齐，整体去重', () => {
    expect(withRecentOnTop(['国企', '外企'], ['国企', '私企', '央企', '外企'])).toEqual([
      '国企',
      '外企',
      '私企',
      '央企',
    ])
  })

  it('过滤失效值（不在池内的最近点击不出现）', () => {
    expect(withRecentOnTop(['国企', '已下线', '私企'], ['国企', '私企', '央企'])).toEqual(['国企', '私企', '央企'])
  })

  it('不重复出现', () => {
    expect(withRecentOnTop(['国企', '国企'], ['国企', '私企'])).toEqual(['国企', '私企'])
  })

  it('recent 为空时等于原候选池', () => {
    const pool = ['国企', '私企']
    expect(withRecentOnTop([], pool)).toEqual(pool)
  })

  it('候选池为空时返回空数组', () => {
    expect(withRecentOnTop(['国企'], [])).toEqual([])
  })
})
