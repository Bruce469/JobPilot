"""状态流转业务单测：事件写入 / 同状态去重 / applied_at / ended_at。"""
from app.dao import list_events
from app.services import change_status, create_job


def test_status_flow_writes_events(app_db):
    job = create_job({"company": "示例", "position": "后端开发"})
    jid = job["id"]
    assert job["status"] == "待投递"

    job2, event = change_status(jid, "笔试", note="收到笔试邀请", time="2026-08-24T10:00:00")
    assert job2["status"] == "笔试"
    assert event["type"] == "状态流转"
    assert event["from_status"] == "待投递" and event["to_status"] == "笔试"
    assert event["note"] == "收到笔试邀请"
    assert event["time"] == "2026-08-24T10:00:00"


def test_same_status_no_event(app_db):
    job = create_job({"company": "示例"})
    _, event = change_status(job["id"], "待投递")
    assert event is None


def test_applied_and_terminal_dates(app_db):
    job = create_job({"company": "示例"})
    jid = job["id"]
    job, _ = change_status(jid, "已投递")
    assert job["applied_at"] is not None          # 进入已投递记 applied_at
    job, _ = change_status(jid, "已Offer")
    assert job["ended_at"] is not None            # 进终态记 ended_at
    job, _ = change_status(jid, "一面")
    assert job["ended_at"] is None                # 从终态回退清 ended_at


def test_events_ordered(app_db):
    job = create_job({"company": "示例"})
    jid = job["id"]
    change_status(jid, "已投递")
    change_status(jid, "笔试")
    events = list_events(jid)
    assert [e["to_status"] for e in events] == ["已投递", "笔试"]
    assert all(e["type"] == "状态流转" for e in events)
