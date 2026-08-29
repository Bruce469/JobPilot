<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { getResume, updateResume } from '@/api/resumes'
import PdfViewerDialog from '@/components/PdfViewerDialog.vue'
import type { EducationItem, ExperienceItem, ProjectItem, Resume, ResumePayload } from '@/types'

const route = useRoute()
const router = useRouter()
const resumeId = route.params.id as string

interface EditableResume {
  name: string
  basic: { name: string; phone: string; email: string; target_position: string; city: string }
  education: EducationItem[]
  experience: ExperienceItem[]
  projects: ProjectItem[]
  skills: string[]
  summary: string
}

function emptyBasic() {
  return { name: '', phone: '', email: '', target_position: '', city: '' }
}

const form = reactive<EditableResume>({
  name: '',
  basic: emptyBasic(),
  education: [],
  experience: [],
  projects: [],
  skills: [],
  summary: '',
})

const loading = ref(true)
const saving = ref(false)
/** 源 PDF 文件名（getResume 返回的 pdf_file），仅在有附件时显示「查看源PDF」入口 */
const sourcePdfFile = ref<string | null>(null)
const pdfVisible = ref(false)

onMounted(async () => {
  try {
    const r: Resume = await getResume(resumeId)
    sourcePdfFile.value = r.pdf_file ?? null
    form.name = r.name
    form.basic = { ...emptyBasic(), ...(r.basic || {}) }
    form.education = (r.education || []).map((x) => ({ ...x }))
    form.experience = (r.experience || []).map((x) => ({ ...x }))
    form.projects = (r.projects || []).map((x) => ({ ...x }))
    form.skills = [...(r.skills || [])]
    form.summary = r.summary || ''
  } catch (e) {
    ElMessage.error(e instanceof Error ? e.message : '加载简历失败')
    router.push('/resumes')
  } finally {
    loading.value = false
  }
})

function addEducation() {
  form.education.push({ school: '', major: '', degree: '', start_date: '', end_date: '', description: '' })
}
function removeEducation(i: number) {
  form.education.splice(i, 1)
}

function addExperience() {
  form.experience.push({ company: '', position: '', start_date: '', end_date: '', responsibilities: '' })
}
function removeExperience(i: number) {
  form.experience.splice(i, 1)
}

function addProject() {
  form.projects.push({ name: '', role: '', start_date: '', end_date: '', description: '' })
}
function removeProject(i: number) {
  form.projects.splice(i, 1)
}

async function save(): Promise<boolean> {
  if (!form.name.trim()) {
    ElMessage.warning('简历名称必填')
    return false
  }
  if (!form.basic.name.trim()) {
    ElMessage.warning('基本信息中的姓名必填')
    return false
  }
  saving.value = true
  try {
    const payload: ResumePayload = {
      name: form.name.trim(),
      basic: {
        name: form.basic.name.trim(),
        phone: form.basic.phone.trim(),
        email: form.basic.email.trim(),
        target_position: form.basic.target_position.trim(),
        city: form.basic.city.trim(),
      },
      education: form.education,
      experience: form.experience,
      projects: form.projects,
      skills: form.skills,
      summary: form.summary.trim() || null,
    }
    await updateResume(resumeId, payload)
    ElMessage.success('简历已保存')
    return true
  } catch (e) {
    ElMessage.error(e instanceof Error ? e.message : '保存失败')
    return false
  } finally {
    saving.value = false
  }
}

async function onSave() {
  await save()
}

async function onSaveAndPreview() {
  const ok = await save()
  if (ok) router.push(`/resumes/${resumeId}/preview`)
}
</script>

<template>
  <div v-loading="loading" class="resume-edit-page">
    <div class="edit-header">
      <el-button @click="router.push('/resumes')">返回</el-button>
      <div class="header-right">
        <el-button v-if="sourcePdfFile" @click="pdfVisible = true">查看源PDF</el-button>
        <el-button :loading="saving" @click="onSave">保存</el-button>
        <el-button type="primary" :loading="saving" @click="onSaveAndPreview">保存并预览</el-button>
      </div>
    </div>

    <el-card class="section-card" shadow="never">
      <template #header>基本信息</template>
      <el-form label-width="86px" label-position="left">
        <el-row :gutter="12">
          <el-col :span="12">
            <el-form-item label="简历名称" required>
              <el-input v-model="form.name" placeholder="如：简历 v2-算法岗" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="姓名" required>
              <el-input v-model="form.basic.name" placeholder="姓名" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="12">
          <el-col :span="12">
            <el-form-item label="电话">
              <el-input v-model="form.basic.phone" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="邮箱">
              <el-input v-model="form.basic.email" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="12">
          <el-col :span="12">
            <el-form-item label="意向岗位">
              <el-input v-model="form.basic.target_position" placeholder="如：算法工程师" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="意向城市">
              <el-input v-model="form.basic.city" placeholder="如：北京" />
            </el-form-item>
          </el-col>
        </el-row>
      </el-form>
    </el-card>

    <el-card class="section-card" shadow="never">
      <template #header>
        <div class="section-head">
          <span>教育经历</span>
          <el-button link type="primary" @click="addEducation">添加</el-button>
        </div>
      </template>
      <div v-for="(item, i) in form.education" :key="i" class="sub-item">
        <el-row :gutter="12">
          <el-col :span="10">
            <el-input v-model="item.school" placeholder="学校" />
          </el-col>
          <el-col :span="8">
            <el-input v-model="item.major" placeholder="专业" />
          </el-col>
          <el-col :span="6">
            <el-input v-model="item.degree" placeholder="学历" />
          </el-col>
        </el-row>
        <el-row :gutter="12" class="sub-row">
          <el-col :span="6">
            <el-input v-model="item.start_date" placeholder="开始 2023-09" />
          </el-col>
          <el-col :span="6">
            <el-input v-model="item.end_date" placeholder="结束 2026-06" />
          </el-col>
          <el-col :span="12">
            <el-button link type="danger" @click="removeEducation(i)">删除此条</el-button>
          </el-col>
        </el-row>
        <el-input v-model="item.description" type="textarea" :rows="2" placeholder="说明（GPA、荣誉等，可选）" class="sub-row" />
      </div>
      <el-empty v-if="!form.education.length" description="暂无教育经历" :image-size="60" />
    </el-card>

    <el-card class="section-card" shadow="never">
      <template #header>
        <div class="section-head">
          <span>实习经历</span>
          <el-button link type="primary" @click="addExperience">添加</el-button>
        </div>
      </template>
      <div v-for="(item, i) in form.experience" :key="i" class="sub-item">
        <el-row :gutter="12">
          <el-col :span="10">
            <el-input v-model="item.company" placeholder="公司" />
          </el-col>
          <el-col :span="8">
            <el-input v-model="item.position" placeholder="岗位" />
          </el-col>
          <el-col :span="6">
            <el-button link type="danger" @click="removeExperience(i)">删除此条</el-button>
          </el-col>
        </el-row>
        <el-row :gutter="12" class="sub-row">
          <el-col :span="6">
            <el-input v-model="item.start_date" placeholder="开始 2025-07" />
          </el-col>
          <el-col :span="6">
            <el-input v-model="item.end_date" placeholder="结束 2025-10" />
          </el-col>
        </el-row>
        <el-input v-model="item.responsibilities" type="textarea" :rows="3" placeholder="职责与成果" class="sub-row" />
      </div>
      <el-empty v-if="!form.experience.length" description="暂无实习经历" :image-size="60" />
    </el-card>

    <el-card class="section-card" shadow="never">
      <template #header>
        <div class="section-head">
          <span>项目经历</span>
          <el-button link type="primary" @click="addProject">添加</el-button>
        </div>
      </template>
      <div v-for="(item, i) in form.projects" :key="i" class="sub-item">
        <el-row :gutter="12">
          <el-col :span="10">
            <el-input v-model="item.name" placeholder="项目名称" />
          </el-col>
          <el-col :span="8">
            <el-input v-model="item.role" placeholder="角色" />
          </el-col>
          <el-col :span="6">
            <el-button link type="danger" @click="removeProject(i)">删除此条</el-button>
          </el-col>
        </el-row>
        <el-row :gutter="12" class="sub-row">
          <el-col :span="6">
            <el-input v-model="item.start_date" placeholder="开始 2025-03" />
          </el-col>
          <el-col :span="6">
            <el-input v-model="item.end_date" placeholder="结束 2025-06" />
          </el-col>
        </el-row>
        <el-input v-model="item.description" type="textarea" :rows="3" placeholder="项目描述与成果" class="sub-row" />
      </div>
      <el-empty v-if="!form.projects.length" description="暂无项目经历" :image-size="60" />
    </el-card>

    <el-card class="section-card" shadow="never">
      <template #header>技能标签</template>
      <el-select
        v-model="form.skills"
        multiple
        filterable
        allow-create
        default-first-option
        placeholder="输入技能后回车，如 Python、PyTorch"
        style="width: 100%"
      >
        <el-option v-for="s in form.skills" :key="s" :label="s" :value="s" />
      </el-select>
    </el-card>

    <el-card class="section-card" shadow="never">
      <template #header>自我评价</template>
      <el-input v-model="form.summary" type="textarea" :rows="4" placeholder="一段话介绍自己（可选）" />
    </el-card>

    <!-- 源 PDF 在线预览 -->
    <PdfViewerDialog v-model="pdfVisible" :resume-id="resumeId" title="源 PDF 预览" />
  </div>
</template>

<style scoped>
.resume-edit-page {
  max-width: 860px;
  margin: 0 auto;
  padding-bottom: 40px;
}
.edit-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}
.header-right {
  display: flex;
  gap: 8px;
}
.section-card {
  margin-bottom: 12px;
}
.section-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.sub-item {
  border: 1px solid #f3f4f6;
  border-radius: 6px;
  padding: 10px;
  margin-bottom: 10px;
  background: #fafafa;
}
.sub-row {
  margin-top: 8px;
}
</style>
