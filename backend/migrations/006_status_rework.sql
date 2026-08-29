-- 006_status_rework: 合并「简历筛选」到「已投递」+ 岗位表新增流转辅助列
-- 历史 job_events 中的「简历筛选」事件不改（历史事实），仅当前状态归一到「已投递」
UPDATE jobs SET status='已投递' WHERE status='简历筛选';
-- next_time: 等待环节（笔试/一面/二面/三面/HR面）的计划时间，格式 YYYY-MM-DD 或 YYYY-MM-DDTHH:MM
ALTER TABLE jobs ADD COLUMN next_time TEXT;
-- fail_stage: 被拒环节标签（简历挂/笔试挂/一面挂/二面挂/三面挂/HR挂/其他）
ALTER TABLE jobs ADD COLUMN fail_stage TEXT;
-- last_note / last_note_at: 最近一次流转备注冗余列（列表直显用），随状态流转写入
ALTER TABLE jobs ADD COLUMN last_note TEXT;
ALTER TABLE jobs ADD COLUMN last_note_at TEXT;
