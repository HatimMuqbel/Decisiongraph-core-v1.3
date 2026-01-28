# Phase 3: Scholar Integration - Research

**Researched:** 2026-01-28
**Domain:** Scholar query layer extension for PolicyHead-aware bitemporal queries
**Confidence:** HIGH

## Summary

Phase 3 integrates Scholar (the query/resolver layer) with PolicyHead (policy snapshots) to enable policy-aware queries. The core requirement is that Scholar can filter facts based on which rules are currently "promoted" (active policy) at query time, including bitemporal queries that ask "what was the policy at time X?"

**Key findings:**
- Scholar already has bitemporal query infrastructure (`at_valid_time`, `as_of_system_time` parameters)
- `get_policy_head_at_time()` from Phase 1 provides the "which policy was active when?" lookup
- `QueryResult` dataclass needs extension with optional `policy_head_id` field
- Scholar needs a new query mode parameter `policy_mode` to enable policy filtering
- Auto-refresh after PolicyHead append is already solved: Scholar has `refresh()` method

**Primary recommendation:** Extend `Scholar.query_facts()` with `policy_mode: str = "all"` parameter. When `policy_mode="promoted_only"`, filter facts to only those produced by rules in the active PolicyHead's `promoted_rule_ids`. Use `get_policy_head_at_time()` for bitemporal policy lookups.

## Standard Stack

The established libraries/tools for this domain:

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Python stdlib | 3.10+ | dataclasses, typing, json | Already used throughout codebase |
| Existing scholar.py | v1.3 | Query/resolver layer | Foundation to extend, not replace |
| Existing policyhead.py | v1.5 | PolicyHead queries | `get_policy_head_at_time()` already implemented |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| pytest | 7.4+ | Unit testing | Already in project (671 tests passing) |
| test_utils.py | local | Fixed test timestamps | T0-T5 constants for deterministic tests |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Modify Scholar | Create PolicyScholar | Unnecessary duplication; Scholar is designed for extension |
| policy_mode string | PolicyMode enum | Enum adds type safety but over-engineering for 2-3 values; string matches existing patterns |
| Filter in Scholar | Filter in caller | Caller filtering violates encapsulation; policy filtering is Scholar responsibility |

**Installation:**
```bash
# No additional dependencies needed - all existing
```

## Architecture Patterns

### Recommended Project Structure
```
src/decisiongraph/
├── scholar.py           # Extend with policy_mode parameter, policy_head_id in result
├── policyhead.py        # (exists) get_policy_head_at_time() - no changes needed
└── __init__.py          # (may need new exports if any)

tests/
├── test_scholar.py      # (exists) - add policy-aware query tests
└── test_scholar_policy.py  # NEW: Focused policy-mode tests (SCH-01 through SCH-04)
```

### Pattern 1: Policy-Aware Query Mode
**What:** Add `policy_mode` parameter to `Scholar.query_facts()` to enable policy filtering
**When to use:** When user needs only facts from promoted rules (SCH-01)

**Example:**
```python
# Source: Derived from existing scholar.py query_facts() pattern (lines 892-1011)

def query_facts(
    self,
    requester_namespace: str,
    namespace: str,
    subject: Optional[str] = None,
    predicate: Optional[str] = None,
    object_value: Optional[str] = None,
    at_valid_time: Optional[str] = None,
    as_of_system_time: Optional[str] = None,
    requester_id: str = "anonymous",
    policy_mode: str = "all"  # NEW: "all" (default) or "promoted_only"
) -> QueryResult:
    """
    Query facts from the vault.

    Args:
        ...existing args...
        policy_mode: Query mode for policy filtering:
            - "all": Return all facts (default, backward compatible)
            - "promoted_only": Only return facts from promoted rules

    Returns:
        QueryResult with optional policy_head_id when policy_mode="promoted_only"
    """
```

### Pattern 2: Bitemporal Policy Lookup
**What:** Use `get_policy_head_at_time()` to find active policy for query's `as_of_system_time`
**When to use:** When `policy_mode="promoted_only"` (SCH-02)

**Example:**
```python
# Source: policyhead.py get_policy_head_at_time() (lines 422-460)

def _get_active_policy(
    self,
    namespace: str,
    as_of_system_time: str
) -> Optional[DecisionCell]:
    """
    Get the PolicyHead that was active at the given system_time.

    Uses get_policy_head_at_time() from policyhead.py.
    Returns None if no policy exists for namespace at that time.
    """
    from .policyhead import get_policy_head_at_time
    return get_policy_head_at_time(self.chain, namespace, as_of_system_time)
```

### Pattern 3: Rule-Based Fact Filtering
**What:** Filter facts to only those produced by promoted rules
**When to use:** After gathering candidates, before conflict resolution (SCH-04)

**Example:**
```python
# Source: Derived from logic_anchor.rule_id pattern in cell.py

def _filter_by_promoted_rules(
    self,
    candidates: List[DecisionCell],
    promoted_rule_ids: List[str]
) -> List[DecisionCell]:
    """
    Filter candidates to only those produced by promoted rules.

    Matches fact.logic_anchor.rule_id against promoted_rule_ids.
    """
    promoted_set = set(promoted_rule_ids)
    return [
        c for c in candidates
        if c.logic_anchor.rule_id in promoted_set
    ]
```

### Pattern 4: QueryResult Extension with policy_head_id
**What:** Add optional `policy_head_id` field to QueryResult
**When to use:** Include in result when `policy_mode="promoted_only"` (SCH-03)

**Example:**
```python
# Source: Extend existing QueryResult dataclass (scholar.py lines 97-127)

@dataclass
class QueryResult:
    """Result of a Scholar query"""
    # ...existing fields...

    # NEW: Policy tracking for policy_mode="promoted_only"
    policy_head_id: Optional[str] = None  # Cell ID of PolicyHead used for filtering
```

### Pattern 5: Auto-Refresh After PolicyHead Append
**What:** Scholar.refresh() already rebuilds indexes from chain
**When to use:** Caller invokes after any chain append (already working pattern)

**Example:**
```python
# Source: scholar.py lines 556-559

def refresh(self):
    """Refresh indexes after chain changes"""
    self.index = build_index_from_chain(self.chain)
    self.registry = build_registry_from_chain(self.chain.cells)
```

**Note:** Scholar already has refresh(). Success criteria 5 is about documenting this behavior and testing it with PolicyHead appends specifically.

### Anti-Patterns to Avoid
- **Hard-coding policy filtering in index:** Policy filtering is query-time, not index-time. Keep ScholarIndex policy-agnostic.
- **Caching PolicyHead lookups:** PolicyHead can change; always query fresh using `get_policy_head_at_time()`.
- **Breaking backward compatibility:** `policy_mode="all"` must be default, existing tests must pass unchanged.
- **Filtering rules by namespace mismatch:** PolicyHead is per-namespace; ensure fact's namespace matches PolicyHead's namespace.
- **Modifying QueryResult structure incompatibly:** `policy_head_id` must be optional (None for `policy_mode="all"`).

## Don't Hand-Roll

Problems that look simple but have existing solutions:

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Find active PolicyHead at time | Custom chain scan | `get_policy_head_at_time(chain, ns, time)` | Already implemented in Phase 1, handles edge cases |
| Parse policy data from cell | Custom JSON parsing | `parse_policy_data(policy_head)` | Already validates CellType, handles malformed data |
| Bitemporal fact filtering | Custom time logic | Existing `_is_valid_at_time()` | Already handles valid_from, valid_to, system_time |
| Index rebuilding | Custom cell iteration | `Scholar.refresh()` | Already exists, rebuilds both index and registry |
| Deterministic output ordering | Custom sorting | Existing `cell_sort_key()` pattern | Already ensures reproducible results |

**Key insight:** Phase 3 is integration, not invention. Combine existing PolicyHead queries with existing Scholar query patterns. The machinery exists; we're wiring it together.

## Common Pitfalls

### Pitfall 1: Breaking Backward Compatibility
**What goes wrong:** Existing tests fail because `policy_mode` parameter changes default behavior
**Why it happens:** Forgetting that `policy_mode` must default to `"all"` (no filtering)
**How to avoid:**
- Default `policy_mode="all"`
- Run all 671 existing tests before and after changes
- `policy_mode="all"` should produce identical results to current implementation
**Warning signs:** Any existing test_scholar.py test fails after changes.

### Pitfall 2: Namespace Mismatch in Policy Lookup
**What goes wrong:** Querying facts in `corp.hr` but looking up PolicyHead for `corp` (or vice versa)
**Why it happens:** PolicyHead is per-namespace; must match exact namespace being queried
**How to avoid:** Use query's `namespace` parameter to look up PolicyHead: `get_policy_head_at_time(chain, namespace, ...)`
**Warning signs:** Policy filtering returns unexpected results for child namespaces.

### Pitfall 3: Missing PolicyHead Returns Empty Results
**What goes wrong:** `policy_mode="promoted_only"` returns empty when no PolicyHead exists for namespace
**Why it happens:** No explicit handling of "namespace has no policy yet" case
**How to avoid:**
- Document behavior: if no PolicyHead exists, what happens?
- Option A: Return empty result (strict - only promoted rules allowed)
- Option B: Return all results (lenient - no policy = no filtering)
- Recommendation: Return empty with explicit `authorization.reason = "no_policy_head"`
**Warning signs:** Different behavior when PolicyHead is None vs empty promoted_rule_ids.

### Pitfall 4: Rule ID Matching Edge Cases
**What goes wrong:** Fact's `logic_anchor.rule_id` doesn't match `promoted_rule_ids` format
**Why it happens:** Inconsistent rule ID formatting (e.g., "rule:salary_v1" vs "salary_v1")
**How to avoid:**
- Use exact string matching (current pattern)
- Document expected rule_id format in promotion workflow
- Test with real rule_ids from existing test cases
**Warning signs:** Promoted rules not filtering correctly despite matching names.

### Pitfall 5: Bitemporal Confusion
**What goes wrong:** Using `at_valid_time` to look up PolicyHead instead of `as_of_system_time`
**Why it happens:** Confusion between "when fact is valid" vs "when policy was active"
**How to avoid:**
- PolicyHead lookup uses `as_of_system_time` (system clock, not business clock)
- Fact filtering uses both clocks (existing `_is_valid_at_time()` logic)
- Test explicitly: "PolicyHead created at T2, query at as_of_system_time=T1 should not see it"
**Warning signs:** Tests use wrong time parameter for policy lookup.

### Pitfall 6: QueryResult.to_proof_bundle() Not Updated
**What goes wrong:** `to_proof_bundle()` doesn't include `policy_head_id`, breaking audit trail
**Why it happens:** Forgetting to update all serialization methods
**How to avoid:** Add `policy_head_id` to proof_bundle when present (under new "policy" key)
**Warning signs:** Proof bundle missing policy information when `policy_mode="promoted_only"`.

## Code Examples

Verified patterns from official sources and existing codebase:

### Adding policy_mode Parameter to query_facts()
```python
# Source: scholar.py lines 892-902 (existing signature)
# Extension point for policy_mode

def query_facts(
    self,
    requester_namespace: str,
    namespace: str,
    subject: Optional[str] = None,
    predicate: Optional[str] = None,
    object_value: Optional[str] = None,
    at_valid_time: Optional[str] = None,
    as_of_system_time: Optional[str] = None,
    requester_id: str = "anonymous",
    policy_mode: str = "all"  # NEW: "all" or "promoted_only"
) -> QueryResult:
    # ...existing default times logic (lines 920-922)...
    now = get_current_timestamp()
    valid_time = at_valid_time or now
    system_time = as_of_system_time or now

    # NEW: Policy-aware filtering
    policy_head_id = None
    promoted_rule_ids = None

    if policy_mode == "promoted_only":
        from .policyhead import get_policy_head_at_time, parse_policy_data
        policy_head = get_policy_head_at_time(self.chain, namespace, system_time)

        if policy_head is None:
            # No policy for namespace at this time - return empty result
            return QueryResult(
                facts=[],
                candidates=[],
                bridges_used=[],
                resolution_events=[],
                valid_time=valid_time,
                system_time=system_time,
                namespace_scope=namespace,
                requester_id=requester_id,
                authorization=AuthorizationBasis(
                    allowed=True,
                    reason="no_policy_head",
                    bridges_used=[]
                ),
                policy_head_id=None
            )

        policy_data = parse_policy_data(policy_head)
        promoted_rule_ids = set(policy_data["promoted_rule_ids"])
        policy_head_id = policy_head.cell_id

    # ...existing visibility check (lines 925-949)...

    # ...existing candidate gathering (lines 952-974)...

    # NEW: Filter by promoted rules if policy_mode="promoted_only"
    if promoted_rule_ids is not None:
        candidates = [
            c for c in candidates
            if c.logic_anchor.rule_id in promoted_rule_ids
        ]

    # ...existing conflict resolution (lines 977-993)...

    # ...existing result construction, with policy_head_id added...
    return QueryResult(
        # ...existing fields...
        policy_head_id=policy_head_id  # NEW
    )
```

### Extending QueryResult with policy_head_id
```python
# Source: scholar.py lines 97-127 (extend existing dataclass)

@dataclass
class QueryResult:
    """Result of a Scholar query"""
    # ...existing fields (lines 100-117)...
    facts: List[DecisionCell]
    candidates: List[DecisionCell]
    bridges_used: List[str]
    resolution_events: List[ResolutionEvent]
    valid_time: str
    system_time: str
    namespace_scope: str
    requester_id: str
    authorization: AuthorizationBasis = field(default_factory=lambda: AuthorizationBasis(
        allowed=False, reason="not_checked", bridges_used=[]
    ))

    # NEW: Policy tracking (SCH-03)
    policy_head_id: Optional[str] = None  # Cell ID of PolicyHead used for filtering
```

### Updating to_proof_bundle() for Policy Information
```python
# Source: scholar.py lines 128-200 (extend existing method)

def to_proof_bundle(self) -> Dict:
    # ...existing bundle construction...
    bundle = {
        # ...existing keys...
    }

    # NEW: Include policy information when present
    if self.policy_head_id is not None:
        bundle["policy"] = {
            "mode": "promoted_only",
            "policy_head_id": self.policy_head_id
        }

    return bundle
```

### Test Pattern: policy_mode="promoted_only"
```python
# Source: Derived from test_scholar.py patterns

def test_policy_mode_promoted_only():
    """SCH-01: Query with policy_mode='promoted_only' uses only promoted rules"""
    # Setup: Chain with Genesis, namespace, rules, facts, PolicyHead
    chain = create_chain(graph_name="TestGraph", root_namespace="corp", system_time=T0)

    # Create namespace
    ns = create_namespace_definition(
        namespace="corp.hr",
        owner="role:chro",
        graph_id=chain.graph_id,
        prev_cell_hash=chain.head.cell_id,
        system_time=T1
    )
    chain.append(ns)

    # Create two facts with different rule_ids
    fact_promoted = DecisionCell(...)  # rule_id="rule:salary_v2"
    fact_unpromoted = DecisionCell(...)  # rule_id="rule:salary_v1"
    chain.append(fact_promoted)
    chain.append(fact_unpromoted)

    # Create PolicyHead that only promotes rule:salary_v2
    policy_head = create_policy_head(
        namespace="corp.hr",
        promoted_rule_ids=["rule:salary_v2"],  # Only v2 is promoted
        graph_id=chain.graph_id,
        prev_cell_hash=chain.head.cell_id,
        system_time=T4
    )
    chain.append(policy_head)

    scholar = create_scholar(chain)

    # Query with policy_mode="promoted_only"
    result = scholar.query_facts(
        requester_namespace="corp.hr",
        namespace="corp.hr",
        subject="employee:jane",
        predicate="has_salary",
        at_valid_time=T5,
        as_of_system_time=T5,
        policy_mode="promoted_only"
    )

    # Should only return fact from promoted rule
    assert len(result.facts) == 1
    assert result.facts[0].logic_anchor.rule_id == "rule:salary_v2"
    assert result.policy_head_id == policy_head.cell_id  # SCH-03
```

### Test Pattern: Bitemporal Policy Query (SCH-02)
```python
def test_policy_mode_at_historic_time():
    """SCH-02: Query with as_of_system_time uses PolicyHead active at that time"""
    # Setup: Chain with PolicyHead v1 at T2, PolicyHead v2 at T4

    # PolicyHead v1: promotes ["rule:v1"]
    # PolicyHead v2: promotes ["rule:v1", "rule:v2"]

    # Query at as_of_system_time=T3 (between v1 and v2)
    # Should use PolicyHead v1, which only promotes rule:v1

    result = scholar.query_facts(
        # ...
        as_of_system_time=T3,  # Before PolicyHead v2
        policy_mode="promoted_only"
    )

    # Should use PolicyHead v1
    assert result.policy_head_id == policy_head_v1.cell_id
    # Facts from rule:v2 should be excluded
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| No policy filtering | `policy_mode` parameter | Phase 3 | Enables promoted-only queries |
| Implicit rules | Explicit rule promotion | v1.5 | Rules must be promoted to be "active" |
| Single timestamp | Bitemporal (`valid_time` + `system_time`) | v1.3 | Enables "what was true when we knew what" queries |
| Hard-coded rules | Logic anchor with rule_id | v1.3 | Every fact traceable to producing rule |

**Deprecated/outdated:**
- None - Phase 3 extends existing patterns, doesn't deprecate anything

## Open Questions

Things that couldn't be fully resolved:

1. **Behavior when no PolicyHead exists for namespace**
   - What we know: `get_policy_head_at_time()` returns `None` if no PolicyHead exists
   - What's unclear: Should `policy_mode="promoted_only"` return empty results or all results?
   - Recommendation: Return empty results with `authorization.reason="no_policy_head"`. This is safer (fail-closed). Document clearly.

2. **Policy filtering for child namespaces**
   - What we know: PolicyHead is per-exact-namespace (e.g., "corp.hr")
   - What's unclear: Does querying "corp.hr.compensation" use "corp.hr" PolicyHead?
   - Recommendation: Exact namespace match only in Phase 3. Namespace inheritance is future enhancement. Document explicitly.

3. **Performance impact of policy lookup per query**
   - What we know: `get_policy_head_at_time()` scans chain for PolicyHead cells
   - What's unclear: Is this a bottleneck for high-frequency queries?
   - Recommendation: Start simple (no caching). Profile if needed. PolicyHead cells are rare (policy changes infrequently).

4. **QueryResult.to_audit_text() and to_dot() updates**
   - What we know: These methods should reflect policy_head_id
   - What's unclear: Exact format for policy information in audit output
   - Recommendation: Add "Policy" section to audit text when policy_head_id is present. Lower priority than core functionality.

## Sources

### Primary (HIGH confidence)
- `src/decisiongraph/scholar.py` - Scholar class, query_facts(), QueryResult, existing patterns
- `src/decisiongraph/policyhead.py` - get_policy_head_at_time(), parse_policy_data()
- `src/decisiongraph/cell.py` - DecisionCell, LogicAnchor.rule_id
- `tests/test_scholar.py` - Existing query test patterns
- `tests/test_policyhead.py` - PolicyHead query test patterns
- `.planning/phases/01-policyhead-foundation/01-RESEARCH.md` - Phase 1 patterns
- `.planning/phases/02-witnessset-registry/02-RESEARCH.md` - Phase 2 patterns
- `.planning/STATE.md` - Project state, decisions, learnings

### Secondary (MEDIUM confidence)
- None needed - all patterns derived from existing codebase

### Tertiary (LOW confidence)
- None - this is an integration phase using verified existing patterns

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - All components already exist in codebase
- Architecture: HIGH - Extending existing Scholar pattern with verified PolicyHead queries
- Pitfalls: HIGH - Based on careful analysis of existing integration points

**Research date:** 2026-01-28
**Valid until:** 2026-02-28 (30 days - stable internal architecture)

**Key dependencies:**
- Phase 1 complete: PolicyHead infrastructure (`get_policy_head_at_time()`, `parse_policy_data()`)
- Phase 2 complete: WitnessSet/WitnessRegistry (not directly used in Phase 3, but part of overall v1.5)
- 671 tests passing baseline (517 existing + 101 Phase 1 + 53 Phase 2)

**Implementation scope estimate:**
- Modify: `scholar.py` (QueryResult dataclass + query_facts method)
- Create: `tests/test_scholar_policy.py` (focused policy-mode tests)
- Verify: All 671 existing tests still pass (backward compatibility)
