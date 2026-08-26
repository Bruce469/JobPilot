# -*- coding: utf-8 -*-
"""构建 A股上市公司离线信息库（数据源：巨潮资讯 cninfo，经 akshare，免费、无需 token）。

产出：app/fetcher/company_info_data.json —— A股公司 {name(简称), aliases(全称/曾用简称), website(官方网站),
industry(证监会行业→本项目词表), city(注册地址提取), nature: null}。
可断点续跑：按代码进度增量写入，跳过已完成的代码。

用法：
    python scripts/build_akshare_company_db.py            # 全量构建
    python scripts/build_akshare_company_db.py --limit 500  # 只构建前 500 家（试跑）
"""
import argparse
import json
import re
import sys
import time
from pathlib import Path

import akshare as ak

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app.fetcher import company_map  # noqa: E402
from app.fetcher.normalize import normalize_company  # noqa: E402
from app.fetcher.resolve import extract_city  # noqa: E402

OUT = Path(__file__).resolve().parent.parent / "app" / "fetcher" / "company_info_data.json"
CACHE = Path(__file__).resolve().parent / "company_db_progress.json"  # 断点进度（code → done）

# 证监会行业（cninfo 所属行业）→ 本项目行业词表
CNINFO_INDUSTRY_MAP = {
    "货币金融服务": "金融", "资本市场服务": "金融", "保险业": "金融", "其他金融业": "金融",
    "软件和信息技术服务业": "科技", "互联网和相关服务": "互联网", "电信、广播电视和卫星传输服务": "通信",
    "计算机、通信和其他电子设备制造业": "科技", "电气机械和器材制造业": "制造",
    "汽车制造业": "汽车", "铁路、船舶、航空航天和其他运输设备制造业": "制造",
    "通用设备制造业": "制造", "专用设备制造业": "制造", "仪器仪表制造业": "制造",
    "金属制品业": "制造", "黑色金属冶炼和压延加工业": "制造", "有色金属冶炼和压延加工业": "制造",
    "非金属矿物制品业": "制造", "橡胶和塑料制品业": "制造", "化学原料和化学制品制造业": "制造",
    "化学纤维制造业": "制造", "医药制造业": "医药", "食品制造业": "快消", "酒、饮料和精制茶制造业": "快消",
    "农副食品加工业": "快消", "烟草制品业": "快消", "纺织业": "制造", "纺织服装、服饰业": "制造",
    "造纸和纸制品业": "制造", "印刷和记录媒介复制业": "制造", "家具制造业": "制造",
    "木材加工和木、竹、藤、棕、草制品业": "制造", "文教、工美、体育和娱乐用品制造业": "制造",
    "石油和天然气开采业": "能源", "开采辅助活动": "能源", "煤炭开采和洗选业": "能源",
    "石油加工、炼焦和核燃料加工业": "能源", "电力、热力生产和供应业": "能源", "燃气生产和供应业": "能源",
    "水的生产和供应业": "能源", "黑色金属矿采选业": "能源", "有色金属矿采选业": "能源",
    "非金属矿采选业": "能源", "农、林、牧、渔服务业": "快消", "农业": "快消", "林业": "快消",
    "畜牧业": "快消", "渔业": "快消", "农副食品加工业": "快消", "食品制造业": "快消",
    "批发业": "其他", "零售业": "其他", "租赁和商务服务业": "咨询", "房地产业": "地产",
    "建筑装饰和其他建筑业": "地产", "土木工程建筑业": "地产", "房屋建筑业": "地产",
    "仓储业": "物流", "道路运输业": "物流", "水上运输业": "物流", "航空运输业": "物流",
    "铁路运输业": "物流", "装卸搬运和运输代理业": "物流", "邮政业": "物流",
    "研究和试验发展": "科技", "专业技术服务业": "咨询", "科技推广和应用服务业": "科技",
    "教育": "教育", "卫生": "医药", "新闻和出版业": "其他", "广播、电视、电影和影视录音制作业": "其他",
    "文化艺术业": "其他", "体育": "其他", "公共设施管理业": "其他", "生态保护和环境治理业": "能源",
    "综合": "其他",
}


def _norm_website(raw) -> str | None:
    raw = str(raw or "").strip()
    if not raw:
        return None
    if not raw.startswith(("http://", "https://")):
        raw = "https://" + raw
    return raw.rstrip("/")


def _norm_short(name: str) -> str:
    """A股简称：去尾随全角 Ａ/Ｂ/Ｃ（如「万科Ａ」→「万科」）并去全部空白（如「万  科」→「万科」）。"""
    return re.sub(r"\s+", "", re.sub(r"[ＡＢＣ]$", "", name.strip()))


def _parse_profile(df) -> dict | None:
    """从 cninfo 单股票概况 DataFrame 提取映射条目。"""
    row = df.iloc[0]
    short = _norm_short(str(row.get("A股简称") or ""))
    full = str(row.get("公司名称") or "").strip()
    website = _norm_website(row.get("官方网站"))
    if not short or not website:
        return None
    industry = CNINFO_INDUSTRY_MAP.get(str(row.get("所属行业") or "").strip())
    city = extract_city(str(row.get("注册地址") or ""))
    aliases = []
    for a in [full, *(str(row.get("曾用简称") or "").split(">>"))]:
        a = a.strip()
        if a and a != short and a not in aliases:
            aliases.append(a)
    return {"name": short, "aliases": aliases, "website": website,
            "industry": industry, "city": city, "nature": None}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=0, help="只处理前 N 家（0=全部）")
    args = parser.parse_args()

    codes = ak.stock_info_a_code_name()
    print(f"A股代码总数: {len(codes)}")

    progress: dict = {}
    if CACHE.exists():
        progress = json.loads(CACHE.read_text(encoding="utf-8"))
    existing: dict = {}
    if OUT.exists():
        for e in json.loads(OUT.read_text(encoding="utf-8")):
            existing[normalize_company(e["name"])] = e

    # 与手工 curated 映射冲突的公司跳过（curated 更完整）
    curated_keys: set = set()
    for e in company_map.all_entries():
        curated_keys.add(normalize_company(e["name"]))
        curated_keys.update(normalize_company(a) for a in (e.get("aliases") or []))

    added = skipped = failed = 0
    out_entries: list = []
    for i, row in codes.iterrows():
        code, name = str(row["code"]), str(row["name"])
        if args.limit and i >= args.limit:
            break
        if progress.get(code):
            continue
        try:
            df = ak.stock_profile_cninfo(symbol=code)
        except Exception as exc:
            failed += 1
            progress[code] = "failed"
            if failed % 20 == 0:
                print(f"  失败 {failed} 家，最近: {name} {str(exc)[:60]}")
            continue
        entry = _parse_profile(df)
        progress[code] = "done"
        if entry:
            keys = {normalize_company(entry["name"])}
            keys.update(normalize_company(a) for a in entry["aliases"])
            if keys & curated_keys:
                skipped += 1
            elif normalize_company(entry["name"]) in existing:
                skipped += 1
            else:
                out_entries.append(entry)
                existing[normalize_company(entry["name"])] = entry
                added += 1
        else:
            skipped += 1
        time.sleep(0.25)
        if (i + 1) % 100 == 0:
            CACHE.write_text(json.dumps(progress, ensure_ascii=False), encoding="utf-8")
            _flush(OUT, existing)
            print(f"  进度 {i + 1}/{len(codes)}，新增 {added}，跳过 {skipped}，失败 {failed}")

    CACHE.write_text(json.dumps(progress, ensure_ascii=False), encoding="utf-8")
    _flush(OUT, existing)
    print(f"完成：新增 {added} 家，跳过 {skipped} 家，失败 {failed} 家；共 {len(existing)} 家")


def _flush(path: Path, entries: dict) -> None:
    path.write_text(json.dumps(list(entries.values()), ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
