"""异步任务（架构 5.5 / ADR-3）：内存任务表 + 单个后台工作线程 + 串行执行。

probe/fetch 返回 202 + job_id，前端轮询 GET /api/tasks/{job_id}。
"""
import logging
import queue
import threading
import time

from .. import dao, util
from . import ats as ats_mod
from . import probe as probe_mod
from .errors import FetchError, RobotsDisallowed, TaskTimeout
from .http import fetch, robots_allowed

logger = logging.getLogger("app.fetcher")

MAX_TASKS = 100
TASK_TIMEOUT = 60.0  # 单公司整任务上限 60s
MAX_BATCH_UNITS = 60  # 批量任务每家公司独立 60s 预算，总预算封顶 60 分钟

TASKS: dict[str, dict] = {}
_LOCK = threading.Lock()
_QUEUE: queue.Queue = queue.Queue()
_STARTED = False


def submit(task_type: str, payload: dict) -> str:
    job_id = util.new_id()
    with _LOCK:
        TASKS[job_id] = {
            "job_id": job_id, "type": task_type, "status": "queued",
            "progress": "排队中", "result": None, "error": None, "created_at": util.now_iso(),
        }
        _trim()
    _QUEUE.put((job_id, payload))
    return job_id


def get(job_id: str) -> dict | None:
    with _LOCK:
        task = TASKS.get(job_id)
        if not task:
            return None
        result = dict(task)
        result["queue_length"] = sum(1 for t in TASKS.values() if t["status"] == "queued")
        return result


def start() -> None:
    global _STARTED
    if _STARTED:
        return
    _STARTED = True
    threading.Thread(target=_worker_loop, name="fetcher-worker", daemon=True).start()


def _trim() -> None:
    if len(TASKS) > MAX_TASKS:
        for k in sorted(TASKS, key=lambda k: TASKS[k]["created_at"])[:-MAX_TASKS]:
            del TASKS[k]


def _worker_loop() -> None:
    while True:
        job_id, payload = _QUEUE.get()
        try:
            _run_task(job_id, payload)
        except Exception:
            logger.exception("任务异常 job_id=%s", job_id)
            with _LOCK:
                task = TASKS.get(job_id)
                if task:
                    task["status"] = "failed"
                    task["error"] = {"code": "INTERNAL_ERROR", "message": "任务异常"}
        finally:
            _QUEUE.task_done()


def _run_task(job_id: str, payload: dict) -> None:
    task = TASKS[job_id]
    task["status"] = "running"
    task["progress"] = "开始"
    start = time.monotonic()
    # 批量任务（resolve/probe_batch 带 company_ids）：每家公司独立 60s 预算，总预算封顶 30 分钟
    company_ids = payload.get("company_ids") or []
    is_batch = task["type"] in ("resolve", "probe_batch") and company_ids
    budget = min(len(company_ids), MAX_BATCH_UNITS) * TASK_TIMEOUT if is_batch else TASK_TIMEOUT
    deadline = start + budget
    try:
        if task["type"] == "probe":
            task["result"] = _run_probe(payload, deadline)
            task["progress"] = "完成"
        elif task["type"] == "probe_batch":
            task["result"] = _run_probe_batch(payload, deadline, task)
            task["progress"] = "完成"
        elif task["type"] == "resolve":
            task["result"] = _run_resolve(payload, deadline, task)
            task["progress"] = "完成"
        else:
            task["result"] = _run_fetch(payload, deadline)
            task["progress"] = "完成"
        # 批量任务留一个单任务预算的容差：最后一家公司可能因在途请求越过总预算，
        # 单家超时会中断该家并保留已完成部分，不应把整个批量判为超时。
        if time.monotonic() - start > budget + (TASK_TIMEOUT if is_batch else 0):
            raise TaskTimeout()
        task["status"] = "done"
    except TaskTimeout:
        task["status"] = "failed"
        task["progress"] = "超时"
        task["error"] = {"code": "TIMEOUT", "message": f"任务超时（>{budget:.0f}s），已降级为手动录入"}
        _mark_company(payload, probe_status="需人工", fetch_result="超时，请手动录入")
    except RobotsDisallowed:
        task["status"] = "failed"
        task["progress"] = "robots 禁止"
        task["error"] = {"code": "ROBOTS_DISALLOW", "message": "robots.txt 禁止抓取"}
        _mark_company(payload, probe_status="需人工", fetch_result="robots 禁止抓取")
    except FetchError as exc:
        task["status"] = "failed"
        task["error"] = {"code": exc.code, "message": exc.message}
        if exc.mark_manual:
            _mark_company(payload, probe_status="需人工")


def _mark_company(payload: dict, probe_status: str | None = None, fetch_result: str | None = None) -> None:
    cid = payload.get("company_id")
    if not cid:
        return
    updates = {}
    if probe_status:
        updates["probe_status"] = probe_status
    if fetch_result:
        updates["last_fetch_result"] = fetch_result
        updates["last_fetched_at"] = util.now_iso()
    if updates:
        dao.update_company(cid, updates)


def _company_deadline(deadline: float | None) -> float:
    """批量任务中单家公司的预算：不超过任务总 deadline，且最多再给一个单任务预算。"""
    fresh = time.monotonic() + TASK_TIMEOUT
    return min(deadline, fresh) if deadline else fresh


def _run_probe(payload: dict, deadline: float) -> dict:
    company = dao.get_company(payload["company_id"])
    if not company:
        raise FetchError("COMPANY_NOT_FOUND", "公司不存在", mark_manual=False)
    candidates, code, msg = probe_mod.probe_company(company["website"], deadline)
    if code:
        raise FetchError(code, msg)
    updates = {"probe_status": "成功" if candidates else "需人工"}
    if candidates and not company.get("career_url"):
        # 最高置信度候选写入 career_url，仍可人工修正后复用
        updates["career_url"] = candidates[0]["url"]
    dao.update_company(company["id"], updates)
    return {"candidates": candidates}


def _run_probe_batch(payload: dict, deadline: float, task: dict) -> dict:
    """批量探测：逐公司探测招聘页并写库（probe_status / 缺失时写最佳候选 career_url）。

    与单条探测语义一致：有候选置「成功」、无候选置「需人工」、异常记 failed 不阻塞其余；
    已探测成功（probe_status=成功）的公司跳过，节省网络与限速预算。
    """
    company_ids = payload.get("company_ids") or []
    total = len(company_ids)
    results = []
    ok = manual = failed = skipped = 0
    for i, cid in enumerate(company_ids):
        task["progress"] = f"已探测 {i}/{total}"
        company = dao.get_company(cid)
        if not company:
            failed += 1
            results.append({"company_id": cid, "name": None, "status": "failed", "error": "公司不存在"})
            continue
        if company.get("probe_status") == "成功":
            skipped += 1
            results.append({"company_id": cid, "name": company["name"], "status": "skipped",
                            "career_url": company.get("career_url")})
            continue
        try:
            candidates, code, msg = probe_mod.probe_company(company["website"], _company_deadline(deadline))
            if code:
                raise FetchError(code, msg)
            updates = {"probe_status": "成功" if candidates else "需人工"}
            if candidates and not company.get("career_url"):
                updates["career_url"] = candidates[0]["url"]
            dao.update_company(company["id"], updates)
            if candidates:
                ok += 1
            else:
                manual += 1
            results.append({
                "company_id": cid, "name": company["name"],
                "status": "成功" if candidates else "需人工",
                "career_url": candidates[0]["url"] if candidates else None,
            })
        except Exception as exc:  # 单公司失败不阻塞其余，置「需人工」等待人工处理
            logger.exception("单公司探测异常 cid=%s", cid)
            failed += 1
            dao.update_company(cid, {"probe_status": "需人工"})
            results.append({"company_id": cid, "name": company["name"], "status": "failed", "error": str(exc)})
    task["progress"] = f"已探测 {total}/{total}"
    return {"results": results, "ok": ok, "manual": manual, "failed": failed, "skipped": skipped, "total": total}


def _run_fetch(payload: dict, deadline: float) -> dict:
    company = dao.get_company(payload["company_id"])
    if not company:
        raise FetchError("COMPANY_NOT_FOUND", "公司不存在", mark_manual=False)
    url = str(payload.get("career_url") or company.get("career_url") or "").strip()
    if not url:
        raise FetchError("NO_CAREER_URL", "公司尚未配置招聘页链接，请先探测或手动填写", mark_manual=False)
    if not robots_allowed(url, deadline):
        raise RobotsDisallowed()
    html = fetch(url, deadline).text
    ats_name, adapter = ats_mod.detect_ats(url, html)
    candidates = adapter.extract_jobs(html, url)
    updates = {"ats_type": ats_name, "last_fetched_at": util.now_iso(), "probe_status": "成功"}
    if candidates:
        updates["last_fetch_result"] = f"解析到 {len(candidates)} 条岗位"
    else:
        updates["probe_status"] = "需人工"
        updates["last_fetch_result"] = "解析 0 条岗位，请手动录入"
    dao.update_company(company["id"], updates)
    return {
        "ats_type": ats_name,
        "career_url": url,
        "job_candidates": [c.model_dump() for c in candidates],
        "count": len(candidates),
    }


def _run_resolve(payload: dict, deadline: float, task: dict) -> dict:
    """批量自动补全：逐公司 resolve，进度含「已补全 x/y」，结果含每公司数据。

    补全结果自动写入缺失字段（仅填充 website/industry/career_url/city/nature 为空的字段，
    不覆盖已有值，防搜索误配覆盖手填数据）；五项信息完整的公司跳过（source=skipped）；
    非映射公司主体信息已完整、仅缺城市/性质时直接跳过（搜索兜底无法产出这两项，
    避免无意义网络请求）；单公司失败不阻塞其余。
    """
    from .resolve import resolve_company, resolve_from_info, resolve_from_mapping

    company_ids = payload.get("company_ids") or []
    total = len(company_ids)
    results = []
    resolved = skipped = 0
    for i, cid in enumerate(company_ids):
        task["progress"] = f"已补全 {i}/{total}"
        company = dao.get_company(cid)
        if not company:
            results.append({"company_id": cid, "name": None, "website": None, "industry": None,
                            "city": None, "nature": None, "career_url": None,
                            "source": "failed", "error": "公司不存在"})
            continue
        if (company.get("website") and company.get("industry") and company.get("career_url")
                and company.get("city") and company.get("nature")):
            skipped += 1
            results.append({"company_id": cid, "name": company["name"],
                            "website": company["website"], "industry": company["industry"],
                            "city": company["city"], "nature": company["nature"],
                            "career_url": company["career_url"], "source": "skipped"})
            continue
        r = resolve_from_mapping(company["name"])
        if r is None:
            r = resolve_from_info(company["name"])
        if r is not None and r.get("website"):
            pass  # 离线层完整命中（含官网），直接使用
        else:
            if r is None and company.get("website") and company.get("industry") and company.get("career_url"):
                # 非映射/非 A股公司：仅缺城市/性质，搜索无法补全，直接跳过
                skipped += 1
                results.append({"company_id": cid, "name": company["name"],
                                "website": company["website"], "industry": company["industry"],
                                "city": company.get("city"), "nature": company.get("nature"),
                                "career_url": company["career_url"], "source": "skipped"})
                continue
            # 未命中离线层 / 离线层命中但缺官网（如央企国企名录）：走完整 resolve（搜索补官网 + 合并名录元数据）
            try:
                r = resolve_company(company["name"], _company_deadline(deadline))
            except Exception as exc:  # 单公司失败不阻塞其余
                logger.exception("单公司补全异常 cid=%s", cid)
                r = {"name": company["name"], "website": None, "industry": None,
                     "city": None, "nature": None, "career_url": None,
                     "source": "failed", "confidence": None, "error": str(exc)}
        if r.get("source") != "failed":
            updates = {}
            for field in ("website", "industry", "career_url", "city", "nature"):
                if not company.get(field) and r.get(field):
                    updates[field] = r[field]
            if updates:
                dao.update_company(cid, updates)
                resolved += 1
                results.append({"company_id": cid, **r})
            elif r.get("source") in ("mapping", "info"):
                # 离线层确定命中但已无新字段可写（如 A股公司仅缺招聘站/性质，离线层无法提供）→ 视为跳过
                skipped += 1
                results.append({"company_id": cid, **r, "source": "skipped"})
            else:
                resolved += 1
                results.append({"company_id": cid, **r})
        else:
            results.append({"company_id": cid, **r})
    task["progress"] = f"已补全 {total}/{total}"
    return {"results": results, "resolved": resolved, "skipped": skipped, "total": total}
