"""FX-CUSTOMERS + FX-SLA + checksum stabil. SD-02: RNG turunan per entitas agar stabil."""
import hashlib, json, random
from datetime import datetime, timezone, timedelta

def gen(seed: int = 42):
    customers, cases_seed, sla_seed = [], [], []
    r_cust = random.Random(f"{seed}/customers")
    for i in range(50):
        customers.append({"customer_id": f"CUS-TEST-{i:03d}", "email_hash": hashlib.sha256(f"user{i}@example.test".encode()).hexdigest()[:16],
                          "vulnerability_marker": i < 8, "is_synthetic": True})
    r_sla = random.Random(f"{seed}/sla")
    for i in range(30):
        # offset tepat di 80% dan 100% untuk uji AT_RISK/BREACHED
        cases_seed.append({"sla_record": f"SLA-TEST-{i:03d}", "offset_pct": 80 if i % 2 == 0 else 100})
    manifest = {"seed": seed, "customers": len(customers), "sla_markers": len(cases_seed)}
    blob = json.dumps({"customers": customers, "sla": cases_seed}, sort_keys=True).encode()
    manifest["sha256"] = hashlib.sha256(blob).hexdigest()
    return manifest

if __name__ == "__main__":
    import sys
    seed = int(sys.argv[sys.argv.index("--seed") + 1]) if "--seed" in sys.argv else 42
    print(json.dumps(gen(seed), indent=2))
