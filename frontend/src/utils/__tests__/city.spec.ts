import { describe, expect, it } from 'vitest'
import { COMMON_CITIES, firstLetterOf, groupCitiesByLetter } from '../city'

describe('firstLetterOf', () => {
  it('常规汉字取拼音首字母', () => {
    expect(firstLetterOf('北京')).toBe('B')
    expect(firstLetterOf('上海')).toBe('S')
    expect(firstLetterOf('杭州')).toBe('H')
    expect(firstLetterOf('深圳')).toBe('S')
  })

  it('多音字按完整城市名消歧', () => {
    expect(firstLetterOf('重庆')).toBe('C')
    expect(firstLetterOf('厦门')).toBe('X')
    expect(firstLetterOf('长沙')).toBe('C')
  })

  it('英文字母取首字符大写', () => {
    expect(firstLetterOf('ABC')).toBe('A')
    expect(firstLetterOf('beijing')).toBe('B')
  })

  it('非字母开头归 #', () => {
    expect(firstLetterOf('123')).toBe('#')
    expect(firstLetterOf('9号')).toBe('#')
    expect(firstLetterOf('')).toBe('#')
  })
})

describe('groupCitiesByLetter', () => {
  it('按字母分组且组序 A-Z 升序', () => {
    const groups = groupCitiesByLetter(['北京', '上海', '安徽', '深圳', '成都'])
    expect(groups.map((g) => g.letter)).toEqual(['A', 'B', 'C', 'S'])
    const a = groups.find((g) => g.letter === 'A')
    expect(a?.cities).toEqual(['安徽'])
    const b = groups.find((g) => g.letter === 'B')
    expect(b?.cities).toEqual(['北京'])
    const s = groups.find((g) => g.letter === 'S')
    expect(s?.cities).toEqual(['上海', '深圳'])
  })

  it('组内按完整拼音升序', () => {
    const groups = groupCitiesByLetter(['长沙', '重庆', '成都'])
    const c = groups.find((g) => g.letter === 'C')
    expect(c?.cities).toEqual(['长沙', '成都', '重庆'])
  })

  it('非字母组排在最后', () => {
    const groups = groupCitiesByLetter(['北京', '9号城市', '上海'])
    expect(groups.map((g) => g.letter)).toEqual(['B', 'S', '#'])
  })

  it('输入去重', () => {
    expect(groupCitiesByLetter(['北京', '北京'])).toEqual([{ letter: 'B', cities: ['北京'] }])
  })

  it('空数组返回空', () => {
    expect(groupCitiesByLetter([])).toEqual([])
  })
})

describe('COMMON_CITIES', () => {
  it('内置常用城市齐全且无重复', () => {
    for (const c of ['北京', '上海', '广州', '深圳', '重庆', '杭州', '成都', '西安', '长沙', '厦门']) {
      expect(COMMON_CITIES).toContain(c)
    }
    expect(new Set(COMMON_CITIES).size).toBe(COMMON_CITIES.length)
  })
})
