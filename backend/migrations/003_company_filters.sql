-- 003_company_filters: 公司库筛选支持
-- 新增 city（城市）与 nature（公司性质：国企/央企/私企/外企等）两列，供公司库按城市/性质筛选。

ALTER TABLE companies ADD COLUMN city TEXT;
ALTER TABLE companies ADD COLUMN nature TEXT;
CREATE INDEX IF NOT EXISTS idx_companies_city   ON companies(city);
CREATE INDEX IF NOT EXISTS idx_companies_nature ON companies(nature);
