// 城市工具：拼音首字母分组（纯前端离线，pinyin-pro 做词组级多音字消歧）
import { pinyin } from 'pinyin-pro'

/** 内置常用城市（直辖市 / 省会 / 计划单列市及主要经济城市），与 DB distinct 值并集后作为候选池 */
export const COMMON_CITIES = [
  '北京',
  '上海',
  '广州',
  '深圳',
  '天津',
  '重庆',
  '杭州',
  '南京',
  '苏州',
  '成都',
  '武汉',
  '西安',
  '长沙',
  '郑州',
  '青岛',
  '大连',
  '宁波',
  '厦门',
  '福州',
  '合肥',
  '济南',
  '沈阳',
  '哈尔滨',
  '长春',
  '石家庄',
  '太原',
  '呼和浩特',
  '乌鲁木齐',
  '兰州',
  '西宁',
  '银川',
  '贵阳',
  '昆明',
  '南宁',
  '海口',
  '南昌',
  '无锡',
  '佛山',
  '东莞',
  '珠海',
  '温州',
  '泉州',
  '常州',
  '烟台',
]

/**
 * 城市首字母（分组锚点）：A-Z；
 * 汉字按完整城市名取拼音（词组级消歧，如「重庆」→ C、「厦门」→ X）；
 * 非字母开头（数字/符号/无法取拼音）统一归 '#'。
 */
export function firstLetterOf(city: string): string {
  if (!city) return '#'
  const ch = city.charAt(0)
  if (/[a-zA-Z]/.test(ch)) return ch.toUpperCase()
  if (/[0-9]/.test(ch)) return '#'
  // 对整个名称取拼音：单字会丢失词组多音字信息（「重」单字读 zhong），
  // 因此必须用完整城市名让 pinyin-pro 命中词库（「重庆」→ chong qing → C）
  const first = pinyin(city, { pattern: 'first', toneType: 'none', type: 'array' })[0]
  if (first && /[a-zA-Z]/.test(first)) return first.charAt(0).toUpperCase()
  return '#'
}

export interface LetterGroup {
  letter: string
  cities: string[]
}

/** 城市名完整拼音（无音调、去空格），用于组内排序 */
function pinyinSortKey(city: string): string {
  return pinyin(city, { toneType: 'none' }).replace(/\s+/g, '')
}

/**
 * 按首字母分组：组序 A-Z 升序、'#' 最后；组内按完整拼音（本地化）升序。
 * 输入去重、忽略空串；返回有序数组。
 */
export function groupCitiesByLetter(cities: string[]): LetterGroup[] {
  const map = new Map<string, string[]>()
  const order: string[] = []
  for (const city of cities) {
    if (!city) continue
    const letter = firstLetterOf(city)
    const bucket = map.get(letter)
    if (bucket) {
      if (!bucket.includes(city)) bucket.push(city)
    } else {
      map.set(letter, [city])
      order.push(letter)
    }
  }
  const groups = order.map((letter) => ({ letter, cities: map.get(letter) as string[] }))
  groups.sort((a, b) => {
    if (a.letter === '#') return 1
    if (b.letter === '#') return -1
    return a.letter.localeCompare(b.letter)
  })
  for (const g of groups) {
    g.cities.sort((x, y) => pinyinSortKey(x).localeCompare(pinyinSortKey(y)) || x.localeCompare(y))
  }
  return groups
}
