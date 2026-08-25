<script setup lang="ts">
import { computed } from 'vue'
import type { Resume } from '@/types'

const props = defineProps<{ resume: Resume }>()

const hasEducation = computed(() => props.resume.education?.length > 0)
const hasExperience = computed(() => props.resume.experience?.length > 0)
const hasProjects = computed(() => props.resume.projects?.length > 0)
const hasSkills = computed(() => props.resume.skills?.length > 0)
const hasSummary = computed(() => !!props.resume.summary?.trim())

const canExport = computed(
  () => hasEducation.value || hasExperience.value || hasProjects.value || hasSkills.value || hasSummary.value,
)
</script>

<template>
  <div class="resume-page">
    <div class="resume-header">
      <h1 class="resume-name">{{ resume.basic.name || '未填写姓名' }}</h1>
      <div class="resume-target">
        {{ resume.basic.target_position || '求职意向：未填写' }}
        <span v-if="resume.basic.city"> · {{ resume.basic.city }}</span>
      </div>
      <div class="resume-contact">
        <span v-if="resume.basic.phone">{{ resume.basic.phone }}</span>
        <span v-if="resume.basic.email">{{ resume.basic.email }}</span>
      </div>
    </div>

    <section v-if="hasEducation" class="resume-section">
      <h2 class="section-title">教育经历</h2>
      <div v-for="(item, i) in resume.education" :key="i" class="section-item">
        <div class="item-head">
          <span class="item-main">{{ item.school }}</span>
          <span class="item-side">{{ item.start_date }} ~ {{ item.end_date }}</span>
        </div>
        <div class="item-sub">
          <span v-if="item.major">{{ item.major }}</span>
          <span v-if="item.degree"> · {{ item.degree }}</span>
        </div>
        <p v-if="item.description" class="item-desc">{{ item.description }}</p>
      </div>
    </section>

    <section v-if="hasExperience" class="resume-section">
      <h2 class="section-title">实习经历</h2>
      <div v-for="(item, i) in resume.experience" :key="i" class="section-item">
        <div class="item-head">
          <span class="item-main">{{ item.company }}<template v-if="item.position"> · {{ item.position }}</template></span>
          <span class="item-side">{{ item.start_date }} ~ {{ item.end_date }}</span>
        </div>
        <p v-if="item.responsibilities" class="item-desc">{{ item.responsibilities }}</p>
      </div>
    </section>

    <section v-if="hasProjects" class="resume-section">
      <h2 class="section-title">项目经历</h2>
      <div v-for="(item, i) in resume.projects" :key="i" class="section-item">
        <div class="item-head">
          <span class="item-main">{{ item.name }}<template v-if="item.role"> · {{ item.role }}</template></span>
          <span class="item-side">{{ item.start_date }} ~ {{ item.end_date }}</span>
        </div>
        <p v-if="item.description" class="item-desc">{{ item.description }}</p>
      </div>
    </section>

    <section v-if="hasSkills" class="resume-section">
      <h2 class="section-title">技能</h2>
      <div class="skill-list">
        <span v-for="(s, i) in resume.skills" :key="i" class="skill-tag">{{ s }}</span>
      </div>
    </section>

    <section v-if="hasSummary" class="resume-section">
      <h2 class="section-title">自我评价</h2>
      <p class="item-desc">{{ resume.summary }}</p>
    </section>

    <div v-if="!canExport" class="resume-empty">
      该简历暂无内容，请先编辑补充至少一个区块。
    </div>
  </div>
</template>

<style scoped>
.resume-page {
  width: 210mm;
  min-height: 297mm;
  margin: 0 auto;
  background: #fff;
  color: #1f2937;
  padding: 16mm 18mm;
  box-sizing: border-box;
  font-size: 13px;
  line-height: 1.6;
}
.resume-header {
  border-bottom: 2px solid #1f2937;
  padding-bottom: 10px;
  margin-bottom: 14px;
}
.resume-name {
  font-size: 26px;
  font-weight: 700;
  margin: 0 0 4px;
}
.resume-target {
  font-size: 14px;
  color: #374151;
}
.resume-contact {
  margin-top: 6px;
  display: flex;
  gap: 16px;
  font-size: 12px;
  color: #6b7280;
}
.resume-section {
  margin-bottom: 14px;
}
.section-title {
  font-size: 15px;
  font-weight: 600;
  margin: 0 0 6px;
  padding-bottom: 3px;
  border-bottom: 1px solid #e5e7eb;
  color: #111827;
}
.section-item {
  margin-bottom: 8px;
}
.item-head {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  gap: 12px;
}
.item-main {
  font-weight: 600;
  font-size: 13px;
}
.item-side {
  font-size: 12px;
  color: #6b7280;
  white-space: nowrap;
}
.item-sub {
  font-size: 12px;
  color: #4b5563;
}
.item-desc {
  margin: 3px 0 0;
  font-size: 12px;
  color: #4b5563;
  white-space: pre-wrap;
}
.skill-list {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}
.skill-tag {
  background: #f3f4f6;
  border: 1px solid #e5e7eb;
  border-radius: 4px;
  padding: 1px 8px;
  font-size: 12px;
}
.resume-empty {
  color: #9ca3af;
  text-align: center;
  padding: 40px 0;
}
</style>
