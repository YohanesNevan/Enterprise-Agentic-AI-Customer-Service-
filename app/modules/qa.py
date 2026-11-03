"""FR-QA-001..007 sampling + skor. BR-QA-01: 10% acak + 100% risiko."""
import random
from ..core.ids import new_id
from ..core import audit as audit_svc

REVIEWS: dict[str, dict] = {}
AUTO_FAIL_RULES = ["PII_UNDER_AL", "NO_CITATION", "PROHIBITED_TOOL"]

def draw_sample(closed_ids: list[str], mandatory_ids: list[str], seed: int = 42) -> dict:
    rnd = random.Random(seed)
    base = set(rnd.sample(closed_ids, max(0, int(len(closed_ids) * 0.1)))) if closed_ids else set()
    selected = sorted(base | set(mandatory_ids))
    run_id = new_id("qa_review")
    audit_svc.emit("TNT-TEST", new_id("correlation"), "SYSTEM", "qa-sampler", "qa.sample_drawn",
                   "qa_sample", run_id, "qa-svc", after={"selected": selected, "seed": seed})
    return {"sample_run_id": run_id, "method": "10pct_random+100pct_risk", "seed": seed, "selected_ids": selected}

def score_review(item_id: str, scores: dict[str, int], reviewer: str, corr: str, auto_fail: str | None = None) -> dict:
    total = 0 if auto_fail else sum(scores.values())
    rid = new_id("qa_review")
    r = {"review_id": rid, "item_id": item_id, "scores": scores, "total": total,
         "auto_fail": bool(auto_fail), "auto_fail_criterion": auto_fail, "reviewer_id": reviewer}
    REVIEWS[rid] = r
    audit_svc.emit("TNT-TEST", corr, "HUMAN_AGENT", reviewer, "qa.review_completed",
                   "qa_review", rid, "qa-svc", after={"total": total, "auto_fail": auto_fail})
    return r
