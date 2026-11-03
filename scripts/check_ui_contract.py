"""Kontrak UI-vs-API: endpoint yang dipanggil web-workspace/src/App.jsx + api.js.
Jalankan saat backend hidup:  python scripts/check_ui_contract.py [--base http://localhost:8000]
"""
import json
import sys
import urllib.request

BASE = sys.argv[sys.argv.index("--base") + 1] if "--base" in sys.argv else "http://localhost:8000"
SUP = {"Content-Type": "application/json", "X-Role": "supervisor", "X-Actor-Type": "HUMAN_AGENT", "X-Actor-Id": "sup-1"}
QA = {"Content-Type": "application/json", "X-Role": "qa_analyst", "X-Actor-Type": "HUMAN_AGENT", "X-Actor-Id": "qa-1"}
CS = {"Content-Type": "application/json", "X-Role": "cs_agent", "X-Actor-Type": "HUMAN_AGENT", "X-Actor-Id": "agent-1"}
MGR = {"Content-Type": "application/json", "X-Role": "management", "X-Actor-Type": "HUMAN_AGENT", "X-Actor-Id": "mgr-1"}

ok = fail = 0


def call(name, method, path, headers=SUP, body=None, expect=(200,), raw=False):
    global ok, fail
    try:
        req = urllib.request.Request(
            BASE + path, data=json.dumps(body).encode() if body is not None else None,
            headers=headers, method=method)
        try:
            r = urllib.request.urlopen(req, timeout=10)
            status, data = r.status, r.read().decode()
        except urllib.error.HTTPError as he:
            status, data = he.code, he.read().decode()
        assert status in expect, f"status {status}: {data[:150]}"
        print(f"[PASS] {name} ({status}, {len(data)}b)")
        ok += 1
        return None if raw else (json.loads(data) if data else None)
    except Exception as e:
        print(f"[FAIL] {name}: {e}")
        fail += 1
        return None


call("landing /", "GET", "/", headers={})
call("healthz", "GET", "/healthz", headers={})
call("operational", "GET", "/v1/analytics/operational")
call("driver-tree", "GET", "/v1/analytics/driver-tree")
call("resolution", "GET", "/v1/analytics/resolution")
call("handoff stats", "GET", "/v1/analytics/handoff")
call("qa summary", "GET", "/v1/analytics/qa")
call("export csv cases", "GET", "/v1/analytics/export.csv?kind=cases", raw=True)
call("export csv handoffs", "GET", "/v1/analytics/export.csv?kind=handoffs", raw=True)
call("mgmt operational", "GET", "/v1/analytics/operational", headers=MGR)
call("queue list", "GET", "/v1/workspace/queue")
enq = call("queue enqueue", "POST", "/v1/workspace/queue/enqueue", body={
    "conversation_id": "CNV-UI-CHECK", "reason_code": "CUSTOMER_REQUEST",
    "severity": "HIGH", "queue_id": "Q-GENERAL", "skill_tags": ["chat"],
    "vulnerability_flag": True, "package_complete": True})
call("queue filter", "GET", "/v1/workspace/queue?queue_id=Q-GENERAL&skills=chat")
if enq:
    hid = enq["handoff_id"]
    call("read-model", "GET", "/v1/workspace/conversations/CNV-UI-CHECK")
    call("transfer (cs_agent)", "POST", f"/v1/workspace/handoffs/{hid}/transfer",
         headers=CS, body={"to_queue": "Q-DISPUTES", "reason": "cek", "note": "catatan wajib cek"})
    call("accept", "POST", f"/v1/workspace/handoffs/{hid}/accept", body={"agent_id": "agent-1"})
call("handoff tool", "POST", "/v1/handoffs", body={"conversation_id": "CNV-UI-CHECK", "reason_code": "CUSTOMER_REQUEST", "recent_turns": []})
call("copilot suggest", "POST", "/v1/copilot/suggest", body={"conversation_id": "CNV-UI-CHECK"})
t = call("create ticket", "POST", "/v1/tickets", headers=CS, body={
    "conversation_id": "CNV-UI-CHECK", "type": "GENERAL", "priority": "NORMAL", "description": "Dana belum masuk"})
c = call("create case", "POST", "/v1/cases", headers=CS, body={
    "conversation_id": "CNV-UI-CHECK", "category": "TRANSACTION_DISPUTE",
    "severity_proposed": "HIGH", "description": "Tidak mengenal transaksi"})
if c:
    cid = c["case_id"]
    call("close (expect 409)", "POST", f"/v1/cases/{cid}/close",
         body={"checklist": {"outcome_recorded": True}}, expect=(409,))
    call("evidence valid", "POST", f"/v1/cases/{cid}/evidence-requests", headers=CS, body={
        "items": [{"description": "Transaction detail showing date, amount and merchant"}], "reason": "cek"})
    call("evidence generik (expect 400)", "POST", f"/v1/cases/{cid}/evidence-requests", headers=CS, body={
        "items": [{"description": "bukti"}], "reason": "cek"}, expect=(400,))
    call("reopen", "POST", f"/v1/cases/{cid}/reopen", headers=CS, body={"reason": "cek kontrak"})
a = call("approval request", "POST", "/v1/approvals", headers=CS, body={
    "conversation_id": "CNV-UI-CHECK", "tool_name": "card_status_update",
    "args": {"card_id": "CARD-1"}, "justification": "cek", "risk_class": "WRITE_MEDIUM"})
call("approval list pending", "GET", "/v1/approvals?state=pending")
if a:
    aid = a["approval_id"]
    call("approval detail", "GET", f"/v1/approvals/{aid}")
    call("approval decide", "POST", f"/v1/approvals/{aid}/decide",
         body={"approver_id": "sup-1", "decision": "GRANTED", "comment": "cek kontrak"})
s = call("qa sample", "POST", "/v1/qa/sample", headers=QA, body={"seed": 42})
if s and s.get("selected_ids"):
    r = call("qa review", "POST", "/v1/qa/reviews", headers=QA, body={
        "item_id": s["selected_ids"][0],
        "scores": {"identitas": 8, "sitasi": 8, "klasifikasi": 8, "tool": 8, "bukti": 8, "komunikasi": 8, "komitmen": 8, "penutupan": 8}})
    if r:
        call("qa finding", "POST", "/v1/qa/findings", headers=QA, body={
            "review_id": r["review_id"], "type": "individual_coaching",
            "severity": "LOW", "description": "cek kontrak"})
else:
    print("[SKIP] qa review/finding (sampel kosong — belum ada case CLOSED)")
call("sla calculate", "POST", "/v1/sla/calculate", body={
    "object_type": "CASE", "category": "TRANSACTION_DISPUTE",
    "severity": "HIGH", "created_at": "2026-03-06T09:30:00+00:00"})
call("sla tick", "POST", "/internal/sla-tick")
call("outbox status", "GET", "/internal/outbox-status")
call("outbox drain", "POST", "/internal/outbox-drain")
call("notification", "POST", "/v1/notifications", body={"channel": "REGISTERED_EMAIL", "target": "x"})
call("audit trail kosong", "GET", "/v1/audit/trail/COR-UI-CHECK")

print(f"\n{ok} lolos, {fail} gagal")
raise SystemExit(1 if fail else 0)
