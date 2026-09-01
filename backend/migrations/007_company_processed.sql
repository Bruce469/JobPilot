-- 007_company_processed: 公司「已处理/未处理」标签
-- 0=未处理（默认），1=已处理；供公司库顶部筛选与行内切换。
ALTER TABLE companies ADD COLUMN processed INTEGER NOT NULL DEFAULT 0;
CREATE INDEX IF NOT EXISTS idx_companies_processed ON companies(processed);
