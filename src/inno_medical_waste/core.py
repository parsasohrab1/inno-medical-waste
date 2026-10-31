"""Medical-waste chain-of-custody: QR code with check digits, stage tracking and compliance rules.

Lab prototype on SYNTHETIC data only (TRL 4). Time limits are illustrative placeholders to be set from the ministry's regulation.
"""
import numpy as np

TYPES = {"1": "infectious", "2": "sharps", "3": "pharmaceutical", "4": "general"}
STAGES = ["generated", "collected", "stored", "treated", "disposed"]
LIMIT_H = {"collect": 24, "treat": 72}
TOL = 0.10  # weight tolerance between consecutive stages
WARDS = 12

CRITERIA = [
    ("violation_recall", ">=", 0.99, "injected violations detected"),
    ("violation_precision", ">=", 0.99, "alerts that are real injected violations"),
    ("qr_tamper_detection", ">=", 0.99, "single-digit QR corruptions detected by check digits"),
]


def check_digits(body):
    return 98 - (int(body) * 100) % 97


def make_code(ward, type_code, yymmdd, serial):
    body = "%02d%s%06d%05d" % (ward, type_code, yymmdd, serial)
    return body + "%02d" % check_digits(body)


def valid_code(code):
    return len(code) == 16 and code.isdigit() and int(code) % 97 == 1


def parse_code(code):
    if not valid_code(code):
        raise ValueError("invalid code")
    return {"ward": int(code[:2]), "type": TYPES.get(code[2], "unknown"), "date": code[3:9], "serial": int(code[9:14])}


def check_record(rec):
    """rec: dict code, type, events: list of {stage, t_h, kg}. Returns sorted list of violation ids."""
    v = []
    if not valid_code(rec["code"]):
        return ["R0_bad_code"]
    ev = {e["stage"]: e for e in rec["events"]}
    if "disposed" in ev and any(s not in ev for s in STAGES[:-1] if not (s == "treated" and rec["type"] in ("general",))):
        v.append("R1_missing_stage")
    if "generated" in ev and "collected" in ev and ev["collected"]["t_h"] - ev["generated"]["t_h"] > LIMIT_H["collect"]:
        v.append("R2_late_collection")
    if "stored" in ev and "treated" in ev and ev["treated"]["t_h"] - ev["stored"]["t_h"] > LIMIT_H["treat"]:
        v.append("R3_late_treatment")
    seq = [ev[s] for s in STAGES if s in ev]
    for a, b in zip(seq, seq[1:]):
        if a["kg"] > 0 and abs(b["kg"] - a["kg"]) / a["kg"] > TOL:
            v.append("R4_weight_mismatch"); break
    if rec["type"] == "sharps" and not rec.get("container_id"):
        v.append("R5_sharps_without_container")
    if parse_code(rec["code"])["type"] != rec["type"]:
        v.append("R6_type_mismatch")
    return sorted(v)


def simulate(seed=0, n=1500):
    rng = np.random.default_rng(seed)
    recs = []
    for i in range(n):
        tc = str(rng.choice(list(TYPES), p=[0.35, 0.1, 0.05, 0.5])); typ = TYPES[tc]
        code = make_code(int(rng.integers(0, WARDS)), tc, 261031 - int(rng.integers(0, 30)), i)
        kg = float(rng.uniform(0.5, 12)); t = 0.0; ev = [{"stage": "generated", "t_h": t, "kg": kg}]
        for stage, dt in (("collected", rng.uniform(1, 20)), ("stored", rng.uniform(0.5, 4)), ("treated", rng.uniform(2, 60)), ("disposed", rng.uniform(1, 20))):
            t += dt; kg *= rng.uniform(0.97, 1.03); ev.append({"stage": stage, "t_h": round(t, 2), "kg": round(kg, 3)})
        if typ == "general":
            ev = [e for e in ev if e["stage"] != "treated"]
        rec = {"code": code, "type": typ, "container_id": ("BX%04d" % i) if typ == "sharps" else "", "events": ev, "injected": []}
        recs.append(rec)
    for i in rng.choice(n, int(0.12 * n), replace=False):
        r = recs[i]; ev = {e["stage"]: e for e in r["events"]}
        kind = ["R1_missing_stage", "R2_late_collection", "R3_late_treatment", "R4_weight_mismatch", "R5_sharps_without_container", "R6_type_mismatch"][int(rng.integers(0, 6))]
        if kind == "R5_sharps_without_container" and r["type"] != "sharps":
            kind = "R4_weight_mismatch"
        if kind == "R3_late_treatment" and "treated" not in ev:
            kind = "R2_late_collection"
        if kind == "R1_missing_stage":
            if r["type"] == "general":
                kind = "R2_late_collection"
            else:
                r["events"] = [e for e in r["events"] if e["stage"] != "stored"]
        if kind == "R2_late_collection":
            shift = 30 - (ev["collected"]["t_h"] - ev["generated"]["t_h"]) + rng.uniform(0, 5)
            for e in r["events"]:
                if e["stage"] != "generated":
                    e["t_h"] = round(e["t_h"] + shift, 2)
        elif kind == "R3_late_treatment":
            shift = 80 - (ev["treated"]["t_h"] - ev["stored"]["t_h"])
            if shift > 0:
                for e in r["events"]:
                    if e["stage"] in ("treated", "disposed"):
                        e["t_h"] = round(e["t_h"] + shift, 2)
        elif kind == "R4_weight_mismatch":
            for e in r["events"]:
                if e["stage"] in ("treated", "disposed"):
                    e["kg"] = round(e["kg"] * 0.6, 3)
            if r["type"] == "general":
                ev["disposed"]["kg"] = round(ev["disposed"]["kg"] * 1.0, 3)
        elif kind == "R5_sharps_without_container":
            r["container_id"] = ""
        elif kind == "R6_type_mismatch":
            r["type"] = "general" if r["type"] != "general" else "infectious"
        r["injected"].append(kind)
    for r in recs:  # ground truth = what a perfect rule engine should flag after injection
        r["truth"] = None
    return recs


def tamper(code, rng):
    i = int(rng.integers(0, len(code))); d = str((int(code[i]) + int(rng.integers(1, 10))) % 10)
    return code[:i] + d + code[i + 1:]


def compliance_by_ward(recs):
    tot, ok = {}, {}
    for r in recs:
        w = int(r["code"][:2]); tot[w] = tot.get(w, 0) + 1; ok[w] = ok.get(w, 0) + (not check_record(r))
    return {w: ok[w] / tot[w] for w in sorted(tot)}


def evaluate(seed=0):
    recs = simulate(seed)
    tp = fp = fn = 0
    for r in recs:
        flagged = bool(check_record(r)); injected = bool(r["injected"])
        tp += flagged and injected; fp += flagged and not injected; fn += (not flagged) and injected
    rng = np.random.default_rng(seed + 99)
    det = np.mean([not valid_code(tamper(r["code"], rng)) for r in recs for _ in range(2)])
    return {"violation_recall": tp / max(tp + fn, 1), "violation_precision": tp / max(tp + fp, 1), "qr_tamper_detection": float(det), "n_injected": tp + fn}


def generate(seed=0):
    recs = simulate(seed, 600)
    return {"bags": [dict(code=r["code"], type=r["type"], container_id=r["container_id"], violations=";".join(check_record(r))) for r in recs],
            "events": [dict(code=r["code"], stage=e["stage"], t_h=e["t_h"], kg=e["kg"]) for r in recs for e in r["events"]]}


def demo(seed=0):
    recs = simulate(seed, 300)
    c = compliance_by_ward(recs)
    return "Compliance by ward: " + ", ".join("W%02d=%.0f%%" % (w, 100 * v) for w, v in c.items())
