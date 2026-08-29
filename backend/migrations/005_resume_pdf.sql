-- 005_resume_pdf: 简历表新增源 PDF 附件列
-- 只存文件名（{resume_id}.pdf），不存全路径；文件本体在 DATA_DIR/resume_files/ 下
ALTER TABLE resumes ADD COLUMN pdf_file TEXT;
