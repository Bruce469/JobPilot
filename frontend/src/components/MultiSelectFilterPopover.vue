<script setup lang="ts">
// 可复用多选筛选弹窗：城市（按字母分组）与行业（平铺）共用。
// Trigger 只读回显，点击打开弹窗；内部草稿确定才提交（update:modelValue + confirm），取消还原。
import { computed, ref } from 'vue'
import { ArrowDown, Close, Search } from '@element-plus/icons-vue'
import { pinyin } from 'pinyin-pro'
import { groupCitiesByLetter, type LetterGroup } from '@/utils/city'

const props = withDefaults(
  defineProps<{
    /** 已选值（trigger 回显 + 清除按钮） */
    modelValue: string[]
    /** 候选池（已合并 DB 值 + 静态常量并去重） */
    options: string[]
    /** 最近选择（已按候选池过滤）；为空时隐藏「最近选择」区 */
    recent?: string[]
    title?: string
    placeholder?: string
    /** true=按字母分组（城市），false=平铺网格（行业） */
    grouped?: boolean
  }>(),
  { recent: () => [], title: '', placeholder: '请选择', grouped: true },
)

const emit = defineEmits<{
  (e: 'update:modelValue', v: string[]): void
  (e: 'confirm', v: string[]): void
}>()

const visible = ref(false)
const keyword = ref('')
// 弹窗内草稿：确定才提交，取消/关闭还原
const selected = ref<string[]>([])

function open() {
  selected.value = [...props.modelValue]
  keyword.value = ''
  visible.value = true
}

function toggle(value: string) {
  const idx = selected.value.indexOf(value)
  if (idx >= 0) selected.value.splice(idx, 1)
  else selected.value.push(value)
}

function isSelected(value: string): boolean {
  return selected.value.includes(value)
}

/** 关键字过滤：城市名 / 完整拼音 / 首字母缩写命中均可（如 beijing / bj / 北京） */
function cityMatch(name: string, kw: string): boolean {
  if (name.toLowerCase().includes(kw)) return true
  const full = pinyin(name, { toneType: 'none' }).replace(/\s+/g, '').toLowerCase()
  if (full.includes(kw)) return true
  const initials = pinyin(name, { pattern: 'first', toneType: 'none', type: 'array' })
    .join('')
    .toLowerCase()
  return initials.includes(kw)
}

const filteredOptions = computed(() => {
  const kw = keyword.value.trim().toLowerCase()
  if (!kw) return props.options
  return props.options.filter((o) => cityMatch(o, kw))
})

const letterGroups = computed<LetterGroup[]>(() => (props.grouped ? groupCitiesByLetter(filteredOptions.value) : []))

function resetDraft() {
  selected.value = []
}

function onClear() {
  selected.value = []
}

function onCancel() {
  visible.value = false
}

function onConfirm() {
  visible.value = false
  emit('update:modelValue', [...selected.value])
  emit('confirm', [...selected.value])
}

/** trigger 右侧清除：立即清空并提交空数组（触发防抖刷新） */
function clearTrigger() {
  emit('update:modelValue', [])
  emit('confirm', [])
}

const triggerText = computed(() => props.modelValue.join(', '))
</script>

<template>
  <div class="msf">
    <div class="msf-trigger" :class="{ 'is-empty': !modelValue.length }" @click="open">
      <span v-if="modelValue.length" class="msf-trigger-text">{{ triggerText }}</span>
      <span v-else class="msf-trigger-placeholder">{{ placeholder }}</span>
      <el-icon v-if="modelValue.length" class="msf-trigger-icon is-clear" @click.stop="clearTrigger">
        <Close />
      </el-icon>
      <el-icon v-else class="msf-trigger-icon">
        <ArrowDown />
      </el-icon>
    </div>

    <el-dialog
      v-model="visible"
      :title="title || '多选筛选'"
      width="600px"
      :close-on-click-modal="false"
      @closed="resetDraft"
    >
      <div v-if="recent.length" class="msf-recent">
        <div class="msf-section-title">最近选择</div>
        <div class="msf-chips">
          <span
            v-for="r in recent"
            :key="r"
            class="msf-chip"
            :class="{ 'is-active': isSelected(r) }"
            @click="toggle(r)"
          >{{ r }}</span>
        </div>
      </div>

      <el-input v-model="keyword" :placeholder="`搜索${title || '选项'}`" clearable class="msf-search">
        <template #prefix>
          <el-icon><Search /></el-icon>
        </template>
      </el-input>

      <div class="msf-body">
        <div v-if="grouped" class="msf-groups">
          <div v-for="g in letterGroups" :key="g.letter" class="msf-group">
            <div class="msf-letter">{{ g.letter }}</div>
            <div class="msf-chips">
              <span
                v-for="c in g.cities"
                :key="c"
                class="msf-chip"
                :class="{ 'is-active': isSelected(c) }"
                @click="toggle(c)"
              >{{ c }}</span>
            </div>
          </div>
        </div>
        <div v-else class="msf-groups">
          <div class="msf-group">
            <div class="msf-chips">
              <span
                v-for="c in filteredOptions"
                :key="c"
                class="msf-chip"
                :class="{ 'is-active': isSelected(c) }"
                @click="toggle(c)"
              >{{ c }}</span>
            </div>
          </div>
        </div>
        <el-empty v-if="!filteredOptions.length" :image-size="60" description="无匹配项" />
      </div>

      <template #footer>
        <el-button @click="onClear">清空</el-button>
        <el-button @click="onCancel">取消</el-button>
        <el-button type="primary" @click="onConfirm">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
/* Trigger 只读框：与相邻筛选框（el-input 默认 32px 高）视觉一致 */
.msf-trigger {
  display: flex;
  align-items: center;
  gap: 6px;
  width: 100%;
  height: 32px;
  padding: 0 11px;
  border: 1px solid #dcdfe6;
  border-radius: 4px;
  background: #fff;
  box-sizing: border-box;
  cursor: pointer;
  transition: border-color 0.2s;
}
.msf-trigger:hover {
  border-color: #c0c4cc;
}
.msf-trigger.is-empty:hover {
  border-color: #409eff;
}
.msf-trigger-text {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 14px;
  color: #606266;
}
.msf-trigger-placeholder {
  flex: 1;
  min-width: 0;
  font-size: 14px;
  color: #a8abb2;
}
.msf-trigger-icon {
  flex-shrink: 0;
  font-size: 12px;
  color: #c0c4cc;
}
.msf-trigger-icon.is-clear {
  border-radius: 50%;
}
.msf-trigger-icon.is-clear:hover {
  color: #409eff;
}

.msf-recent {
  margin-bottom: 12px;
}
.msf-section-title {
  font-size: 12px;
  color: #909399;
  margin-bottom: 6px;
}
.msf-search {
  margin-bottom: 10px;
}
.msf-body {
  max-height: 360px;
  min-height: 240px;
  overflow-y: auto;
  border: 1px solid #ebeef5;
  border-radius: 6px;
  padding: 8px 10px;
}
.msf-groups {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.msf-group {
  display: flex;
  align-items: flex-start;
  gap: 10px;
}
.msf-letter {
  flex-shrink: 0;
  width: 24px;
  height: 24px;
  line-height: 24px;
  text-align: center;
  font-size: 13px;
  font-weight: 600;
  color: #409eff;
  background: #ecf5ff;
  border-radius: 4px;
  position: sticky;
  top: 0;
}
.msf-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
.msf-chip {
  padding: 2px 12px;
  height: 26px;
  line-height: 20px;
  font-size: 13px;
  border: 1px solid #dcdfe6;
  border-radius: 4px;
  color: #606266;
  background: #fff;
  cursor: pointer;
  user-select: none;
  transition: all 0.2s;
}
.msf-chip:hover {
  border-color: #409eff;
  color: #409eff;
}
.msf-chip.is-active {
  border-color: #409eff;
  color: #fff;
  background: #409eff;
}
</style>
