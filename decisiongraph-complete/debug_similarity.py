"""
Debug script: trace the full similarity pipeline for a BYOC case
against seed precedents to find why zero scored matches.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from decisiongraph.aml_seed_generator import generate_all_banking_seeds, SCENARIOS
from decisiongraph.aml_fingerprint import (
    AMLFingerprintSchemaRegistry,
    apply_aml_banding,
)

# ── Build the same registry used by the server ──────────────────────────
registry = AMLFingerprintSchemaRegistry()


def _anchor_value(payload, field_id):
    for anchor in payload.anchor_facts:
        if anchor.field_id == field_id:
            return str(anchor.value)
    return None


def _truthy(value):
    if value is None:
        return False
    return str(value).lower() in {"true", "yes", "1"}


# ── Simulate a BYOC PEP case ──────────────────────────────────────────
# This is what a PEP + cross-border + high-risk wire case looks like
# after fingerprint_facts is built in service/main.py
case_facts = {
    "customer.pep": True,
    "customer.type": "individual",
    "customer.relationship_length": "new",
    "customer.pep_type": "foreign",
    "txn.type": "wire",
    "txn.amount_band": "10k_25k",
    "txn.cross_border": True,
    "txn.destination_country_risk": "high",
    "screening.sanctions_match": False,
    "screening.adverse_media": False,
    "gate1_allowed": True,
    "gate2_str_required": False,
    # These come from extract_facts() and get merged
    "sanctions_result": "NO_MATCH",
    "document_status": "VALID",
    "customer_response": "COMPLIANT",
    "adverse_media_mltf": False,
    "legal_prohibition": False,
}

reason_codes = ["RC-TXN-PEP", "RC-TXN-PEP-EDD", "RC-KYC-PEP-APPROVED"]

# ── Step 1: Schema selection ──────────────────────────────────────────
def _select_schema_id_for_codes(codes):
    prefixes = {code.split("-")[1] for code in codes if code.startswith("RC-") and "-" in code}
    if "RPT" in prefixes:
        return "decisiongraph:aml:report:v1"
    if "SCR" in prefixes:
        return "decisiongraph:aml:screening:v1"
    if "KYC" in prefixes:
        return "decisiongraph:aml:kyc:v1"
    if "MON" in prefixes:
        return "decisiongraph:aml:monitoring:v1"
    return "decisiongraph:aml:txn:v1"


schema_id = _select_schema_id_for_codes(reason_codes)
print(f"=== Schema Selection ===")
print(f"Case reason codes: {reason_codes}")
print(f"Selected schema: {schema_id}")

# ── Step 2: Apply banding ──────────────────────────────────────────────
schema = registry.get_schema_by_id(schema_id)

print(f"\n=== Schema '{schema_id}' relevant_facts ===")
for f in sorted(schema.relevant_facts):
    print(f"  {f}")

case_banded = apply_aml_banding(case_facts, schema)
print(f"\n=== Case Banded Facts ===")
for k, v in sorted(case_banded.items()):
    print(f"  {k}: {v!r}  (type: {type(v).__name__})")

# ── Step 3: Case feature extraction (as done in query_similar_precedents) ──
case_channel = case_facts.get("txn.type")
case_amount_band = case_banded.get("txn.amount_band") or case_banded.get("txn.cash_amount_band")
case_cross_border = case_banded.get("txn.cross_border")
case_destination_risk = case_banded.get("txn.destination_country_risk")
case_pep = case_facts.get("customer.pep")
case_customer_type = case_facts.get("customer.type")
case_relationship = case_facts.get("customer.relationship_length")
case_sanctions_match = _truthy(case_facts.get("screening.sanctions_match"))

print(f"\n=== Case Feature Vector (as extracted by query_similar_precedents) ===")
print(f"  case_channel:          {case_channel!r}")
print(f"  case_amount_band:      {case_amount_band!r}")
print(f"  case_cross_border:     {case_cross_border!r}  (type: {type(case_cross_border).__name__})")
print(f"  case_destination_risk: {case_destination_risk!r}")
print(f"  case_pep:              {case_pep!r}  (type: {type(case_pep).__name__})")
print(f"  case_customer_type:    {case_customer_type!r}")
print(f"  case_relationship:     {case_relationship!r}")
print(f"  case_sanctions_match:  {case_sanctions_match!r}")

# ── Step 4: Generate seeds and find matching ones ──────────────────────
seeds = generate_all_banking_seeds()
print(f"\n=== Seed Generation ===")
print(f"Total seeds: {len(seeds)}")

# Count by schema
schema_counts = {}
for s in seeds:
    sid = s.fingerprint_schema_id
    schema_counts[sid] = schema_counts.get(sid, 0) + 1
print(f"Seeds by schema:")
for sid, count in sorted(schema_counts.items()):
    print(f"  {sid}: {count}")

# ── Step 5: Find raw overlaps (min_overlap=1) ──────────────────────────
case_code_set = set(reason_codes)
overlapping = []
for seed in seeds:
    overlap = len(case_code_set.intersection(seed.reason_codes))
    if overlap >= 1:
        overlapping.append((seed, overlap))

print(f"\n=== Raw Overlaps ===")
print(f"Overlapping seeds (min_overlap=1): {len(overlapping)}")

# ── Step 6: Apply hard filters ──────────────────────────────────────────
filtered_out = {"schema": 0, "jurisdiction": 0, "customer_type": 0, "sanctions": 0}
passed_hard_filter = []

for seed, overlap in overlapping:
    # Filter 1: schema match
    if seed.fingerprint_schema_id != schema_id:
        filtered_out["schema"] += 1
        continue

    # Filter 2: customer_type mismatch
    prec_customer_type = _anchor_value(seed, "customer.type") or _anchor_value(seed, "entity.type")
    if case_customer_type and prec_customer_type and str(case_customer_type) != str(prec_customer_type):
        filtered_out["customer_type"] += 1
        continue

    # Filter 3: sanctions
    prec_sanctions = _truthy(_anchor_value(seed, "screening.sanctions_match"))
    if case_sanctions_match and not prec_sanctions:
        filtered_out["sanctions"] += 1
        continue

    passed_hard_filter.append((seed, overlap))

print(f"\n=== Hard Filter Results ===")
print(f"Filtered out by schema mismatch:        {filtered_out['schema']}")
print(f"Filtered out by customer_type mismatch:  {filtered_out['customer_type']}")
print(f"Filtered out by sanctions mismatch:      {filtered_out['sanctions']}")
print(f"Passed hard filters:                     {len(passed_hard_filter)}")

if not passed_hard_filter:
    # Show why schema filtering killed everything
    print("\n=== DEBUGGING: Schema mismatch detail ===")
    for seed, overlap in overlapping[:5]:
        print(f"  Seed scenario: {seed.scenario_code}, schema: {seed.fingerprint_schema_id}")
        prec_ct = _anchor_value(seed, "customer.type")
        print(f"    customer.type: seed={prec_ct!r} vs case={case_customer_type!r}")
    sys.exit(1)

# ── Step 7: Score one precedent in detail ──────────────────────────────
print(f"\n{'='*70}")
print(f"=== DETAILED SCORING: First 3 precedents that passed filters ===")
print(f"{'='*70}")

AML_SIMILARITY_WEIGHTS = {
    "rules_overlap": 0.30,
    "gate_match": 0.25,
    "typology_overlap": 0.15,
    "amount_bucket": 0.10,
    "channel_method": 0.07,
    "corridor_match": 0.08,
    "pep_match": 0.05,
    "customer_profile": 0.05,
    "geo_risk": 0.05,
}

def _code_weight(code):
    if code.startswith("RC-SCR-") or code.startswith("RC-RPT-"):
        return 3.0
    return 1.0

def _bucket_similarity(a, b):
    if not a or not b:
        return 0.0
    if a == b:
        return 1.0
    ordered = ["under_3k","3k_10k","10k_25k","25k_50k","25k_100k","50k_plus","100k_500k","500k_1m","over_1m"]
    if a in ordered and b in ordered:
        return 0.5 if abs(ordered.index(a) - ordered.index(b)) == 1 else 0.0
    return 0.0

def _channel_group(v):
    if not v: return "unknown"
    v = v.lower()
    if "wire" in v: return "wire"
    if "cash" in v: return "cash"
    if "crypto" in v: return "crypto"
    return v

def _channel_similarity(a, b):
    if not a or not b: return 0.0
    if a == b: return 1.0
    return 0.5 if _channel_group(a) == _channel_group(b) else 0.0

def _typology_tokens(codes):
    tokens = set()
    for code in codes:
        c = code.upper()
        if "STRUCT" in c: tokens.add("structuring")
        if "LAYER" in c or "RAPID" in c: tokens.add("layering")
        if "CRYPTO" in c: tokens.add("crypto")
        if "FATF" in c: tokens.add("geo_risk")
        if "PEP" in c: tokens.add("pep")
        if "SANCTION" in c or c.startswith("RC-SCR-"): tokens.add("sanctions")
        if "ADVERSE" in c: tokens.add("adverse_media")
    return tokens


case_typologies = _typology_tokens(reason_codes)
case_code_weights = sum(_code_weight(c) for c in reason_codes) or 1.0

for i, (seed, overlap) in enumerate(passed_hard_filter[:3]):
    print(f"\n--- Precedent {i+1}: {seed.scenario_code} (overlap={overlap}) ---")
    print(f"  Seed codes:  {seed.reason_codes}")
    print(f"  Seed schema: {seed.fingerprint_schema_id}")

    # Show seed anchor facts
    print(f"  Seed anchor facts:")
    for af in seed.anchor_facts:
        print(f"    {af.field_id}: {af.value!r} (type: {type(af.value).__name__})")

    # Rules overlap
    overlap_codes = set(reason_codes).intersection(seed.reason_codes)
    weighted_overlap = sum(_code_weight(c) for c in overlap_codes)
    rules_overlap = weighted_overlap / case_code_weights
    print(f"\n  Component Scores:")
    print(f"    rules_overlap:     {rules_overlap:.2f}  (overlap codes: {overlap_codes})")

    # Gate match
    prec_gate1 = True  # seeds don't store gates directly
    prec_gate2 = False
    gate_matches = int(True == prec_gate1) + int(False == prec_gate2)
    gate_match_score = 1.0 if gate_matches == 2 else 0.5 if gate_matches == 1 else 0.0
    print(f"    gate_match:        {gate_match_score:.2f}")

    # Typology
    prec_typologies = _typology_tokens(seed.reason_codes)
    typo_union = case_typologies.union(prec_typologies)
    typology_overlap = len(case_typologies.intersection(prec_typologies)) / len(typo_union) if typo_union else 0.0
    print(f"    typology_overlap:  {typology_overlap:.2f}  (case={case_typologies}, prec={prec_typologies})")

    # Amount bucket
    prec_amount = _anchor_value(seed, "txn.amount_band") or _anchor_value(seed, "txn.cash_amount_band")
    amount_score = _bucket_similarity(case_amount_band, prec_amount)
    print(f"    amount_bucket:     {amount_score:.2f}  (case={case_amount_band!r}, prec={prec_amount!r})")

    # Channel
    prec_channel = _anchor_value(seed, "txn.type")
    channel_score = _channel_similarity(case_channel, prec_channel)
    print(f"    channel_method:    {channel_score:.2f}  (case={case_channel!r}, prec={prec_channel!r})")

    # Corridor
    prec_cross_border = _anchor_value(seed, "txn.cross_border")
    corridor_score = 0.0
    if case_cross_border is not None and prec_cross_border is not None:
        corridor_score = 1.0 if str(case_cross_border).lower() == str(prec_cross_border).lower() else 0.0
    print(f"    corridor_match:    {corridor_score:.2f}  (case={case_cross_border!r} vs prec={prec_cross_border!r})")

    # PEP
    prec_pep = _anchor_value(seed, "customer.pep")
    pep_score = 0.0
    if case_pep is not None and prec_pep is not None:
        pep_score = 1.0 if str(case_pep).lower() == str(prec_pep).lower() else 0.0
    print(f"    pep_match:         {pep_score:.2f}  (case={case_pep!r}/{str(case_pep).lower()} vs prec={prec_pep!r}/{str(prec_pep).lower() if prec_pep else 'None'})")

    # Customer profile
    prec_customer_type = _anchor_value(seed, "customer.type")
    prec_relationship = _anchor_value(seed, "customer.relationship_length")
    profile_matches = 0
    if case_customer_type and prec_customer_type and str(case_customer_type) == str(prec_customer_type):
        profile_matches += 1
    if case_relationship and prec_relationship and str(case_relationship) == str(prec_relationship):
        profile_matches += 1
    customer_profile_score = 1.0 if profile_matches == 2 else 0.5 if profile_matches == 1 else 0.0
    print(f"    customer_profile:  {customer_profile_score:.2f}  (type: {case_customer_type!r}=={prec_customer_type!r}, rel: {case_relationship!r}=={prec_relationship!r})")

    # Geo risk
    prec_geo = _anchor_value(seed, "txn.destination_country_risk")
    geo_score = 0.0
    if case_destination_risk is not None and prec_geo is not None:
        geo_score = 1.0 if str(case_destination_risk).lower() == str(prec_geo).lower() else 0.0
    print(f"    geo_risk:          {geo_score:.2f}  (case={case_destination_risk!r} vs prec={prec_geo!r})")

    # Evaluable components
    component_scores = {
        "rules_overlap": rules_overlap,
        "gate_match": gate_match_score,
        "typology_overlap": typology_overlap,
        "amount_bucket": amount_score,
        "channel_method": channel_score,
        "corridor_match": corridor_score,
        "pep_match": pep_score,
        "customer_profile": customer_profile_score,
        "geo_risk": geo_score,
    }

    evaluable = {"rules_overlap", "gate_match"}
    if case_typologies or prec_typologies:
        evaluable.add("typology_overlap")
    if case_amount_band and prec_amount:
        evaluable.add("amount_bucket")
    if case_channel and prec_channel:
        evaluable.add("channel_method")
    if (case_cross_border is not None and prec_cross_border is not None) or \
       (case_destination_risk is not None and prec_geo is not None):
        evaluable.add("corridor_match")
    if case_pep is not None and prec_pep is not None:
        evaluable.add("pep_match")
    if (case_customer_type and prec_customer_type) or \
       (case_relationship and prec_relationship):
        evaluable.add("customer_profile")
    if case_destination_risk is not None and prec_geo is not None:
        evaluable.add("geo_risk")

    evaluable_weight = sum(AML_SIMILARITY_WEIGHTS[k] for k in evaluable) or 1.0
    raw_score = sum(AML_SIMILARITY_WEIGHTS[k] * component_scores[k] for k in evaluable)
    similarity_score = raw_score / evaluable_weight

    print(f"\n  Evaluable components: {sorted(evaluable)}")
    print(f"  Evaluable weight:    {evaluable_weight:.2f}")
    print(f"  Raw score:           {raw_score:.4f}")
    print(f"  Similarity score:    {similarity_score:.4f} ({similarity_score*100:.1f}%)")
    print(f"  Threshold (prod):    0.60 (60%)")
    print(f"  PASSES THRESHOLD:    {'YES ✓' if similarity_score >= 0.60 else 'NO ✗'}")

# ── Step 8: Score ALL precedents and show distribution ─────────────────
print(f"\n{'='*70}")
print(f"=== FULL SCORING: All {len(passed_hard_filter)} precedents ===")
print(f"{'='*70}")

score_buckets = {"90-100": 0, "80-89": 0, "70-79": 0, "60-69": 0, "50-59": 0, "40-49": 0, "30-39": 0, "20-29": 0, "10-19": 0, "0-9": 0}
above_threshold = 0

for seed, overlap in passed_hard_filter:
    # Compute full score (abbreviated)
    overlap_codes = set(reason_codes).intersection(seed.reason_codes)
    weighted_overlap = sum(_code_weight(c) for c in overlap_codes)
    rules_overlap = weighted_overlap / case_code_weights

    prec_typologies = _typology_tokens(seed.reason_codes)
    typo_union = case_typologies.union(prec_typologies)
    typology_overlap = len(case_typologies.intersection(prec_typologies)) / len(typo_union) if typo_union else 0.0

    prec_amount = _anchor_value(seed, "txn.amount_band") or _anchor_value(seed, "txn.cash_amount_band")
    prec_channel = _anchor_value(seed, "txn.type")
    prec_cross_border = _anchor_value(seed, "txn.cross_border")
    prec_pep = _anchor_value(seed, "customer.pep")
    prec_customer_type = _anchor_value(seed, "customer.type")
    prec_relationship = _anchor_value(seed, "customer.relationship_length")
    prec_geo = _anchor_value(seed, "txn.destination_country_risk")

    amount_score = _bucket_similarity(case_amount_band, prec_amount)
    channel_score = _channel_similarity(case_channel, prec_channel)
    corridor_score = 0.0
    if case_cross_border is not None and prec_cross_border is not None:
        corridor_score = 1.0 if str(case_cross_border).lower() == str(prec_cross_border).lower() else 0.0
    pep_score = 0.0
    if case_pep is not None and prec_pep is not None:
        pep_score = 1.0 if str(case_pep).lower() == str(prec_pep).lower() else 0.0
    profile_matches = 0
    if case_customer_type and prec_customer_type and str(case_customer_type) == str(prec_customer_type):
        profile_matches += 1
    if case_relationship and prec_relationship and str(case_relationship) == str(prec_relationship):
        profile_matches += 1
    customer_profile_score = 1.0 if profile_matches == 2 else 0.5 if profile_matches == 1 else 0.0
    geo_score = 0.0
    if case_destination_risk is not None and prec_geo is not None:
        geo_score = 1.0 if str(case_destination_risk).lower() == str(prec_geo).lower() else 0.0

    component_scores = {
        "rules_overlap": rules_overlap, "gate_match": 1.0,
        "typology_overlap": typology_overlap, "amount_bucket": amount_score,
        "channel_method": channel_score, "corridor_match": corridor_score,
        "pep_match": pep_score, "customer_profile": customer_profile_score,
        "geo_risk": geo_score,
    }

    evaluable = {"rules_overlap", "gate_match"}
    if case_typologies or prec_typologies: evaluable.add("typology_overlap")
    if case_amount_band and prec_amount: evaluable.add("amount_bucket")
    if case_channel and prec_channel: evaluable.add("channel_method")
    if (case_cross_border is not None and prec_cross_border is not None) or \
       (case_destination_risk is not None and prec_geo is not None):
        evaluable.add("corridor_match")
    if case_pep is not None and prec_pep is not None: evaluable.add("pep_match")
    if (case_customer_type and prec_customer_type) or \
       (case_relationship and prec_relationship): evaluable.add("customer_profile")
    if case_destination_risk is not None and prec_geo is not None: evaluable.add("geo_risk")

    evaluable_weight = sum(AML_SIMILARITY_WEIGHTS[k] for k in evaluable) or 1.0
    raw_score = sum(AML_SIMILARITY_WEIGHTS[k] * component_scores[k] for k in evaluable)
    similarity_score = raw_score / evaluable_weight
    pct = int(similarity_score * 100)

    if pct >= 60: above_threshold += 1

    if pct >= 90: score_buckets["90-100"] += 1
    elif pct >= 80: score_buckets["80-89"] += 1
    elif pct >= 70: score_buckets["70-79"] += 1
    elif pct >= 60: score_buckets["60-69"] += 1
    elif pct >= 50: score_buckets["50-59"] += 1
    elif pct >= 40: score_buckets["40-49"] += 1
    elif pct >= 30: score_buckets["30-39"] += 1
    elif pct >= 20: score_buckets["20-29"] += 1
    elif pct >= 10: score_buckets["10-19"] += 1
    else: score_buckets["0-9"] += 1

print(f"\nScore distribution:")
for bucket, count in score_buckets.items():
    bar = "█" * min(count // 2, 40)
    print(f"  {bucket}%: {count:4d}  {bar}")
print(f"\nAbove 60% threshold: {above_threshold}")
print(f"Below 60% threshold: {len(passed_hard_filter) - above_threshold}")
