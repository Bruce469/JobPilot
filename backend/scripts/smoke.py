"""冒烟测试：临时目录 DB + 随机端口启动后端，跑主要端点断言后自动退出。

用法：python scripts/smoke.py [--host 127.0.0.1]
"""
import argparse
import json
import os
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import httpx

BACKEND_DIR = Path(__file__).resolve().parent.parent
PASS, FAIL = 0, 0


def check(name: str, cond: bool, detail: str = ""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  [PASS] {name}")
    else:
        FAIL += 1
        print(f"  [FAIL] {name} {detail}")


def free_port() -> int:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def wait_boot(base: str, timeout: float = 20) -> dict:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            r = httpx.get(f"{base}/boot", timeout=3)
            if r.status_code == 200:
                return r.json()
        except httpx.HTTPError:
            pass
        time.sleep(0.4)
    raise RuntimeError("后端启动超时")


def poll_task(base: str, job_id: str, headers: dict, timeout: float = 40) -> dict:
    deadline = time.time() + timeout
    while time.time() < deadline:
        d = httpx.get(f"{base}/tasks/{job_id}", headers=headers, timeout=5).json()
        if d["status"] in ("done", "failed"):
            return d
        time.sleep(0.5)
    raise RuntimeError(f"任务轮询超时 job_id={job_id}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    args = parser.parse_args()

    port = free_port()
    base = f"http://{args.host}:{port}/api"
    tmpdir = tempfile.mkdtemp(prefix="jobhunter-smoke-")
    env = dict(os.environ, APP_DB_PATH=str(Path(tmpdir) / "smoke.db"), APP_PORT=str(port))
    proc = subprocess.Popen(
        [sys.executable, str(BACKEND_DIR / "run.py"), "--host", args.host, "--port", str(port)],
        cwd=str(BACKEND_DIR), env=env,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    try:
        boot = wait_boot(base)
        token = boot["token"]
        check("boot 返回 token/schema_version/app", bool(token) and boot["schema_version"] >= 1
              and bool(boot["app"].get("name")))
        headers = {"X-Auth-Token": token}

        # ---- 鉴权与 Host 校验 ----
        r = httpx.get(f"{base}/jobs", timeout=5)
        check("无 token 请求被拒 401", r.status_code == 401 and r.json()["error"]["code"] == "UNAUTHORIZED")
        r = httpx.post(f"{base}/boot", timeout=5)  # 方法不允许
        check("错误方法返回非 2xx", r.status_code != 200)

        # ---- 公司 ----
        r = httpx.post(f"{base}/companies", json={"name": "示例科技", "website": "https://example.com",
                                                  "industry": "互联网"}, headers=headers, timeout=5)
        check("创建公司 201", r.status_code == 201, r.text)
        company = r.json()
        cid = company["id"]
        r = httpx.post(f"{base}/companies", json={"name": "示例科技", "website": "https://x.com"},
                       headers=headers, timeout=5)
        check("同名公司 409", r.status_code == 409 and r.json()["error"]["code"] == "CONFLICT")

        # ---- 岗位 CRUD ----
        r = httpx.post(f"{base}/jobs", json={"company": "示例科技", "company_id": cid,
                                             "position": "后端开发工程师", "city": "北京,上海",
                                             "deadline": "2026-09-30"}, headers=headers, timeout=5)
        check("创建岗位 201 默认待投递", r.status_code == 201 and r.json()["status"] == "待投递", r.text)
        jid = r.json()["id"]
        r = httpx.get(f"{base}/jobs/{jid}", headers=headers, timeout=5)
        check("岗位详情含空 events", r.json()["events"] == [])

        # ---- 状态流转 ----
        r = httpx.post(f"{base}/jobs/{jid}/status", json={"status": "笔试", "note": "收到笔试邀请"},
                       headers=headers, timeout=5)
        d = r.json()
        check("流转到笔试并写事件", d["job"]["status"] == "笔试" and d["event"]["type"] == "状态流转"
              and d["event"]["from_status"] == "待投递" and d["event"]["to_status"] == "笔试", r.text)
        r = httpx.post(f"{base}/jobs/{jid}/status", json={"status": "笔试"}, headers=headers, timeout=5)
        check("同状态流转不写事件", r.json()["event"] is None)
        r = httpx.post(f"{base}/jobs/{jid}/status", json={"status": "已投递"}, headers=headers, timeout=5)
        check("进入已投递记 applied_at", bool(r.json()["job"]["applied_at"]))
        r = httpx.post(f"{base}/jobs/{jid}/status", json={"status": "已Offer"}, headers=headers, timeout=5)
        check("进终态记 ended_at", bool(r.json()["job"]["ended_at"]))
        r = httpx.post(f"{base}/jobs/{jid}/status", json={"status": "一面"}, headers=headers, timeout=5)
        check("终态回退清 ended_at", r.json()["job"]["ended_at"] is None)
        r = httpx.post(f"{base}/jobs/{jid}/status", json={"status": "不存在的状态"}, headers=headers, timeout=5)
        check("非法状态 400", r.status_code == 400 and r.json()["error"]["code"] == "VALIDATION_ERROR")

        # ---- 导入去重 ----
        r = httpx.post(f"{base}/jobs/import", json={"company_id": cid, "jobs": [
            {"position": "算法工程师", "city": "北京", "source_job_id": "a1"},
            {"position": "算法工程师", "city": "北京", "source_job_id": "a1"},      # source_job_id 重复
            {"position": "前端开发", "city": "上海"},
            {"position": "【2026秋招】前端开发", "city": "上海"},                    # 规范化后重复
            {"position": "", "city": "北京"},                                       # 缺岗位名
        ]}, headers=headers, timeout=5)
        d = r.json()
        check("导入 新增2/跳过2/失败1", d["added"] == 2 and d["skipped"] == 2 and d["failed"] == 1
              and len(d["added_ids"]) == 2, json.dumps(d, ensure_ascii=False))

        # ---- 批量删除 ----
        r = httpx.post(f"{base}/jobs", json={"company": "示例科技", "position": "删A"}, headers=headers, timeout=5)
        d1 = r.json()["id"]
        r = httpx.post(f"{base}/jobs", json={"company": "示例科技", "position": "删B"}, headers=headers, timeout=5)
        d2 = r.json()["id"]
        r = httpx.post(f"{base}/jobs/batch-delete", json={"ids": [d1, d2]}, headers=headers, timeout=5)
        check("批量删除 deleted=2", r.json()["deleted"] == 2, r.text)

        # ---- 列表筛选 ----
        r = httpx.get(f"{base}/jobs", params={"status": "一面"}, headers=headers, timeout=5)
        check("按状态筛选", r.json()["total"] == 1, r.text)
        r = httpx.get(f"{base}/jobs", params={"keyword": "算法"}, headers=headers, timeout=5)
        check("关键词筛选", r.json()["total"] == 1)

        # ---- 简历 ----
        r = httpx.post(f"{base}/resumes", json={"name": "简历v1",
                                                "basic": {"name": "张三", "phone": "13800000000",
                                                          "email": "a@b.com", "target_position": "后端", "city": "北京"}},
                       headers=headers, timeout=5)
        check("创建简历 201", r.status_code == 201, r.text)
        rid = r.json()["id"]
        r = httpx.put(f"{base}/jobs/{jid}", json={"resume_id": rid}, headers=headers, timeout=5)
        check("岗位绑定简历并冻结名称快照", r.json()["resume_name"] == "简历v1", r.text)
        r = httpx.delete(f"{base}/resumes/{rid}", headers=headers, timeout=5)
        check("删除被引用简历返回引用数", r.json().get("referenced_by") == 1 and r.json().get("deleted") is False)
        r = httpx.delete(f"{base}/resumes/{rid}?force=true", headers=headers, timeout=5)
        check("force 删除简历 204", r.status_code == 204)
        r = httpx.get(f"{base}/jobs/{jid}", headers=headers, timeout=5)
        check("简历删除后岗位引用置空", r.json()["resume_id"] is None and r.json()["resume_name"] is None)

        # ---- 备份导出/导入 ----
        r = httpx.get(f"{base}/backup/export", headers=headers, timeout=5)
        backup = r.json()
        check("备份导出含三集合与 schema_version", backup["schema_version"] >= 1
              and len(backup["jobs"]) >= 3 and len(backup["companies"]) == 1)
        r = httpx.post(f"{base}/backup/import", json={"schema_version": 1, "mode": "merge",
                                                      "companies": [{"id": "c-new-1", "name": "新公司",
                                                                     "website": "https://new.com"}],
                                                      "jobs": [], "resumes": []}, headers=headers, timeout=5)
        check("备份合并导入新增公司", r.json()["companies_added"] == 1)
        r = httpx.post(f"{base}/backup/import", json={"schema_version": 99, "mode": "merge",
                                                      "jobs": [], "companies": [], "resumes": []},
                       headers=headers, timeout=5)
        check("过高 schema_version 422", r.status_code == 422 and r.json()["error"]["code"] == "IMPORT_ERROR")
        r = httpx.post(f"{base}/backup/import", json={"schema_version": 1, "mode": "merge",
                                                      "jobs": [{"id": "j-x", "company": ""}],
                                                      "companies": [], "resumes": []}, headers=headers, timeout=5)
        check("非法备份字段 422 且不改数据", r.status_code == 422)

        # ---- 统计 ----
        r = httpx.get(f"{base}/stats", headers=headers, timeout=5)
        s = r.json()
        check("stats 口径字段齐全", set(s) >= {"total_applied", "active", "offered", "rejected",
                                               "pending_followup", "funnel", "channel_dist", "weekly_trend"})
        check("stats 数字合理", s["total_applied"] >= s["active"] and len(s["weekly_trend"]) == 4)

        # ---- 异步任务 ----
        r = httpx.get(f"{base}/tasks/not-exist", headers=headers, timeout=5)
        check("不存在的任务 404", r.status_code == 404)

        # ---- 公司批量导入与自动补全（PRD 4.12 v0.6；仅测映射路径/失败路径，避免真实搜索） ----
        r = httpx.post(f"{base}/companies/import",
                       json={"names": ["示例科技", "新公司A", "新公司A", "新公司B"], "resolve": False},
                       headers=headers, timeout=5)
        d = r.json()
        check("批量导入 新增2/跳过2（含名单）",
              d["added"] == 2 and d["skipped"] == 2
              and "示例科技" in d["skipped_names"] and "新公司A" in d["skipped_names"],
              json.dumps(d, ensure_ascii=False))
        r = httpx.post(f"{base}/companies/import", json={"names": []}, headers=headers, timeout=5)
        check("空名单导入 400", r.status_code == 400 and r.json()["error"]["code"] == "VALIDATION_ERROR")

        r = httpx.post(f"{base}/companies/resolve", json={"name": "字节跳动"}, headers=headers, timeout=10)
        d = r.json()
        check("单公司补全映射命中",
              r.status_code == 200 and d["source"] == "mapping" and d["website"].startswith("http")
              and bool(d["career_url"]) and d["industry"] == "互联网", json.dumps(d, ensure_ascii=False))
        r = httpx.post(f"{base}/companies/resolve", json={"name": ""}, headers=headers, timeout=5)
        check("空公司名补全 400", r.status_code == 400 and r.json()["error"]["code"] == "VALIDATION_ERROR")

        r = httpx.post(f"{base}/companies", json={"name": "腾讯", "website": "https://placeholder.invalid"},
                       headers=headers, timeout=5)
        tx = r.json()
        r = httpx.post(f"{base}/companies/{tx['id']}/resolve", headers=headers, timeout=10)
        d = r.json()
        check("已有公司补全映射命中",
              d["source"] == "mapping" and d["website"] == "https://www.tencent.com"
              and d["industry"] == "互联网", json.dumps(d, ensure_ascii=False))

        # 批量导入 + 异步批量补全（映射命中，离线安全）
        r = httpx.post(f"{base}/companies/import", json={"names": ["美团", "快手"], "resolve": True},
                       headers=headers, timeout=5)
        d = r.json()
        check("批量导入+异步补全返回 job_id", d["added"] == 2 and bool(d.get("job_id")),
              json.dumps(d, ensure_ascii=False))
        task = poll_task(base, d["job_id"], headers, timeout=60)
        check("批量补全任务 done 且每公司 mapping 结果",
              task["status"] == "done" and task["result"]["total"] == 2
              and task["result"]["resolved"] == 2
              and all(r["source"] == "mapping" for r in task["result"]["results"]),
              json.dumps(task, ensure_ascii=False))

        # ---- Host 校验 ----
        try:
            raw = socket.create_connection((args.host, port), timeout=5)
            raw.sendall(b"GET /api/boot HTTP/1.1\r\nHost: evil.com\r\n\r\n")
            resp = raw.recv(2048).decode(errors="replace")
            raw.close()
            check("恶意 Host 头 403", "403" in resp.split("\r\n")[0], resp.split("\r\n")[0])
        except OSError as exc:
            check("恶意 Host 头 403", False, str(exc))
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()

    print(f"\n冒烟结果：{PASS} 通过 / {FAIL} 失败")
    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
