# Codebase Concerns

**Analysis Date:** 2026-01-27

## Tech Debt

**Conflict Resolution Logic Redundancy in Scholar:**
- Issue: The `_pick_winner()` method in `scholar.py` (lines 479-582) contains multiple redundant sorting implementations. The function sorts candidates 3 times with different key functions, then manually iterates through candidates to pick a winner using sequential comparisons.
- Files: `src/decisiongraph/scholar.py` lines 479-582
- Impact: Code complexity makes it hard to verify correctness. Maintenance risk if resolution logic needs to change. The multiple sort attempts and manual loop are inefficient for large candidate sets.
- Fix approach: Consolidate into single sort with clear key function. Replace manual comparison loop with a single `max()` call using the proper_sort_key, or keep only the manual comparison loop and remove dead sorting code.

**Bridge Validity Checking Not Implemented:**
- Issue: Line 326 in `scholar.py` contains a TODO comment: "Check bridge validity at as_of_system_time". The `check_visibility()` method checks if a bridge exists and is not revoked, but does NOT validate the bridge's temporal validity (valid_from/valid_to times).
- Files: `src/decisiongraph/scholar.py` line 326
- Impact: Cross-namespace access via bridges is not properly filtered by time. A query using an outdated as_of_system_time may grant access via a bridge that wasn't valid at that point in history.
- Fix approach: Before returning VisibilityResult with bridge access, check if `bridge_cell.fact.valid_from <= system_time < bridge_cell.fact.valid_to` (or valid_to is None). Reject if temporal check fails.

## Known Gaps

**No Authorization Context in Scholar Queries:**
- Issue: The `query_facts()` method checks namespace visibility (via bridges) but does NOT verify role-based access control or permissions at query time.
- Files: `src/decisiongraph/scholar.py` lines 588-704
- Impact: A requester can query any visible namespace without needing appropriate read permissions. Permission enforcement is optional/advisory only. If access control is critical, this is a security gap.
- Mitigation: Access control is documented as a design choice (namespace bridges are the primary mechanism). Role-based checks can be added in a higher layer if needed.

**Traverse Function May Infinitely Loop with Circular Relationships:**
- Issue: The `traverse()` method (lines 710-768) uses a `visited` set to prevent re-visiting subjects. However, if entity relationships form a cycle (A->B->C->A), the function will correctly stop revisiting. BUT if new relationships are added during traversal (multi-threaded scenario), or if relationships change between recursive calls, the visited set becomes stale.
- Files: `src/decisiongraph/scholar.py` lines 710-768
- Impact: Low in current single-threaded context. High if Scholar is used concurrently and chain is being appended to during traversal. Paths returned may be incomplete or incorrect.
- Mitigation: Visited set is local to each traverse() call, so no cross-call pollution. For concurrent use, document that chain must be frozen during traversal, or implement copy-on-read snapshots.

**No Validation of Namespace Parent Relationships:**
- Issue: When creating namespaces like "corp.hr.compensation", the code does NOT verify that parent namespaces ("corp", "corp.hr") exist in the registry.
- Files: `src/decisiongraph/namespace.py` lines 108-164
- Impact: Allows orphaned namespaces in the data. This violates namespace hierarchy semantics but doesn't break functionality (queries still work). Makes the system harder to reason about.
- Fix approach: In `create_namespace_definition()`, validate that all parent namespaces are registered, or auto-register them.

**Bitemporal Query Filtering Not Comprehensive:**
- Issue: The `_is_valid_at_time()` method (lines 390-419 in scholar.py) filters facts by valid_time and system_time. However, it does NOT handle edge cases:
  - What if valid_from > system_time? (Fact is dated in the future relative to query time)
  - What if valid_to is before system_time? (Fact expired before being recorded)
- Files: `src/decisiongraph/scholar.py` lines 390-419
- Impact: Subtle bugs in time-travel queries. Queries at specific points in history may return unexpected results if timestamps are invalid.
- Fix approach: Add validation in Fact.__post_init__() to ensure valid_from <= system_time, or document the expected behavior clearly.

## Performance Concerns

**Index Lookups Not Optimized for Large Namespaces:**
- Issue: The ScholarIndex (lines 176-240 in scholar.py) provides lookups by key, namespace, and subject, but indexes are simple Dict[key, List[cell_id]]. When a namespace has millions of facts, scanning "by_namespace" or "by_ns_subject" lists is O(n).
- Files: `src/decisiongraph/scholar.py` lines 176-240, 243-259
- Impact: Query performance degrades linearly with namespace size. Large deployments will see slow "get all facts in namespace" queries.
- Improvement path: Add secondary indexes (e.g., by system_time or valid_time ranges). Consider sorted lists or B-tree structure for range queries. Implement pagination/streaming for large result sets.

**Conflict Resolution Creates O(n log n) Sort for Every Query:**
- Issue: For every query, `_resolve_conflicts()` sorts ALL candidate facts (line 497). If a predicate has thousands of conflicting values, this becomes expensive.
- Files: `src/decisiongraph/scholar.py` lines 425-477
- Impact: Latency increases with conflict count. Repeated queries for the same facts re-sort every time.
- Improvement path: Cache sort results keyed by candidate cell_ids. Implement incremental resolution when new facts are added (insert into sorted order rather than re-sorting).

**Query Results Not Paginated:**
- Issue: `query_facts()` returns entire result set in memory. No limit parameter. If a namespace query matches millions of facts, memory usage explodes.
- Files: `src/decisiongraph/scholar.py` lines 588-704
- Impact: Large deployments will hit memory limits. No protection against DOS queries that request all facts.
- Improvement path: Add optional `limit` and `offset` parameters to `query_facts()`. Return paginated QueryResult with has_more flag.

**Proof Bundle Generation Sorts Everything:**
- Issue: `to_proof_bundle()` (lines 110-161 in scholar.py) sorts fact_cell_ids, candidate_cell_ids, bridges_used, and resolution_events. This is O(n log n) overhead per query.
- Files: `src/decisiongraph/scholar.py` lines 110-161
- Impact: Every query response has proof generation overhead. At scale, this adds latency.
- Improvement path: Sort once during query construction, not in to_proof_bundle(). Or make proof_bundle() generation lazy/optional.

## Architectural Issues

**No Transaction/Rollback Mechanism:**
- Issue: Once a cell is appended to the chain, it cannot be removed or modified. If a batch of cells is appended and later one is found to be invalid (due to a rule change or discovered tampering), the entire chain state is compromised.
- Files: `src/decisiongraph/chain.py` (design)
- Impact: No recovery mechanism for invalid states. In production, discovered errors cannot be undone.
- Mitigation: This is by design (immutable append-only log). Workaround: Use OVERRIDE or REVOCATION cells to mark data as invalid. Or implement a separate "trusted state" snapshot.

**No Concurrent Access Control:**
- Issue: The Chain and Scholar objects are not thread-safe. Multiple threads appending cells or querying simultaneously will have race conditions.
- Files: `src/decisiongraph/chain.py` (Chain class), `src/decisiongraph/scholar.py` (Scholar class)
- Impact: Data corruption or incorrect query results in multi-threaded deployments.
- Mitigation: None in current code. Document that chain/scholar must be wrapped with locks, or redesign with RwLock semantics.

**Namespace Visibility Not Transitive:**
- Issue: If A can access B via bridge, and B can access C via bridge, Scholar.check_visibility() does NOT authorize A to access C transitively.
- Files: `src/decisiongraph/scholar.py` lines 288-341
- Impact: Transitive relationships must be explicitly bridged. This is actually good for security but can lead to surprise "access denied" errors.
- Mitigation: Document clearly. Consider adding optional transitive_bridges parameter to check_visibility().

## Security Considerations

**Bridge Expiry Not Enforced:**
- Issue: When `create_bridge_rule()` sets a `valid_to` timestamp on a bridge, Scholar never checks it. Bridges don't actually expire.
- Files: `src/decisiongraph/namespace.py` line 260, `src/decisiongraph/scholar.py` line 326 (TODO)
- Current mitigation: `create_bridge_revocation()` allows explicit revocation, but it's manual.
- Recommendation: Implement temporal filtering in Scholar.check_visibility() before returning bridge (see "Known Gaps" section). Also add a cleanup process to identify and log expired bridges.

**No Signature Verification Implemented:**
- Issue: Proof.signature and Proof.signer_key_id fields exist but are never verified. Cells can claim any signer_id without cryptographic proof.
- Files: `src/decisiongraph/cell.py` lines 330-351, `src/decisiongraph/genesis.py` (bootstrap_mode bypasses signature)
- Current mitigation: bootstrap_mode=True allows Genesis creation without signature for initial deployment.
- Risk: If a system relies on signatures for audit trails, current implementation provides no actual verification.
- Recommendation: Implement HMAC-SHA256 or RSA signature verification. Make it mandatory for production (bootstrap_mode=False).

**Namespace Metadata Stored as String:**
- Issue: In `create_namespace_definition()` (lines 139-147), namespace metadata is serialized to string and stored in Fact.object field.
- Files: `src/decisiongraph/namespace.py` lines 139-147
- Impact: No schema validation. Metadata can be corrupted and is not separately queryable.
- Recommendation: Store metadata as separate Evidence items or use a structured format with validation.

## Fragile Areas

**Cell ID Computation Logic (Critical):**
- Files: `src/decisiongraph/cell.py` lines 381-422
- Why fragile: compute_cell_id() includes graph_id in the hash (line 409). If graph_id ever changes or is computed differently in different places, all cell_ids become invalid. Multiple code paths generate graph_ids (genesis.py and cell.py).
- Safe modification: Do NOT change the fields included in seal_string. Do NOT change hash algorithm (SHA-256). Verify all graph_id generation uses same function.
- Test coverage: Test shows cell_id determinism (test_core.py), but test uses old version field. Regenerate all tests after any version change.

**Bridge Visibility Logic (Critical):**
- Files: `src/decisiongraph/scholar.py` lines 318-341
- Why fragile: Logic walks parent namespaces to find bridges. If parent namespace logic changes (is_namespace_prefix(), get_parent_namespace()), visibility breaks.
- Safe modification: Add tests for each parent walk scenario. Test with deeply nested namespaces (corp.hr.compensation.us.ny).
- Test coverage: test_scholar.py has basic bridge tests but not deep nesting or parent walk edge cases.

**Conflict Resolution Ordering (Critical):**
- Files: `src/decisiongraph/scholar.py` lines 479-582
- Why fragile: Multiple sort implementations that must all agree. The manual comparison loop (lines 541-561) is the source of truth but is hard to verify. Changing sort key order breaks determinism.
- Safe modification: Replace all three sort implementations with single authoritative one. Document sort order clearly.
- Test coverage: Determinism tested in test_scholar.py but only with 2 conflicting facts. Test with 10+ conflicts to ensure consistency.

**Bitemporal Time Filtering (Critical):**
- Files: `src/decisiongraph/scholar.py` lines 390-419
- Why fragile: Assumes timestamps are well-formed and monotonic. Edge cases with future-dated facts or valid_to < valid_from not handled.
- Safe modification: Add comprehensive timestamp validation. Test with edge case: valid_from = "2099-01-01", system_time = "2026-01-27", query for "2026-01-27". Expect no results.
- Test coverage: No dedicated bitemporal filtering tests. Add test_scholar.py tests for time_travel scenarios.

## Test Coverage Gaps

**No Tests for Large Dataset Scaling:**
- What's not tested: Performance with 1000+ cells in a single namespace. Index lookup performance. Query result size limits.
- Files: `src/decisiongraph/scholar.py` (index, query_facts)
- Risk: Performance regressions not caught. Deployments may hit memory limits unexpectedly.
- Priority: Medium - add benchmark tests.

**No Tests for Complex Namespace Hierarchies:**
- What's not tested: 5+ level deep namespace hierarchies (corp.a.b.c.d). Parent-child visibility with multiple levels. Bridge inheritance through parents.
- Files: `src/decisiongraph/scholar.py` (visible_namespaces, check_visibility)
- Risk: Edge cases in parent namespace walk not caught. Visibility logic may fail for deeply nested structures.
- Priority: High - add parametrized tests with varying nesting levels.

**No Tests for Bitemporal Edge Cases:**
- What's not tested: valid_from > system_time (fact from future). valid_to in past (already expired). Overlapping valid_to/valid_from across facts.
- Files: `src/decisiongraph/scholar.py` (_is_valid_at_time, query_facts)
- Risk: Time-based queries return unexpected results. Hard to debug in production.
- Priority: High - add dedicated time-based test suite.

**No Concurrent Access Tests:**
- What's not tested: Multiple threads calling query_facts() simultaneously. Append and query racing.
- Files: `src/decisiongraph/chain.py`, `src/decisiongraph/scholar.py`
- Risk: Data corruption not detected until production. Hard to reproduce.
- Priority: High - add threading tests or document thread-safety as not supported.

**No JSON Serialization Round-Trip Tests:**
- What's not tested: Chain.to_json() -> from_json() preserves all data. Cell serialization/deserialization. Namespace metadata string serialization.
- Files: `src/decisiongraph/chain.py` lines 511-529
- Risk: Data loss during export/import. JSON format drift breaks compatibility.
- Priority: Medium - add round-trip tests for all cell types.

--- 

*Concerns audit: 2026-01-27*
