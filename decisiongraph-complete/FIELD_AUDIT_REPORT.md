# FIELD_AUDIT_REPORT

Scope: Banking/AML pipeline only. Sources include the seed generator, fingerprint schemas, similarity scoring, and report rendering.

## PART 1: SEED GENERATOR FIELD INVENTORY

Fields emitted by the seed generator for banking cases.

| Field path | Data type | Possible values | Where set (line) | Used for fingerprint matching? | Displayed in evidence table? |
|---|---|---|---|---|---|
| precedent_id | string (UUID) | generated UUID | [decisiongraph-complete/src/decisiongraph/aml_seed_generator.py](decisiongraph-complete/src/decisiongraph/aml_seed_generator.py#L494) | no | no |
| case_id_hash | string (sha256 hex) | generated hash | [decisiongraph-complete/src/decisiongraph/aml_seed_generator.py](decisiongraph-complete/src/decisiongraph/aml_seed_generator.py#L495) | no | no |
| jurisdiction_code | string | CA | [decisiongraph-complete/src/decisiongraph/aml_seed_generator.py](decisiongraph-complete/src/decisiongraph/aml_seed_generator.py#L496) | no | no |
| fingerprint_hash | string (sha256 hex) | generated hash | [decisiongraph-complete/src/decisiongraph/aml_seed_generator.py](decisiongraph-complete/src/decisiongraph/aml_seed_generator.py#L497) | no | no |
| fingerprint_schema_id | string | decisiongraph:aml:*:v1 | [decisiongraph-complete/src/decisiongraph/aml_seed_generator.py](decisiongraph-complete/src/decisiongraph/aml_seed_generator.py#L498) | yes | no |
| exclusion_codes | list[string] | RC-* codes | [decisiongraph-complete/src/decisiongraph/aml_seed_generator.py](decisiongraph-complete/src/decisiongraph/aml_seed_generator.py#L499) | yes | no |
| reason_codes | list[string] | RC-* codes | [decisiongraph-complete/src/decisiongraph/aml_seed_generator.py](decisiongraph-complete/src/decisiongraph/aml_seed_generator.py#L500) | yes | no |
| reason_code_registry_id | string | decisiongraph:aml:reason_codes:v1 | [decisiongraph-complete/src/decisiongraph/aml_seed_generator.py](decisiongraph-complete/src/decisiongraph/aml_seed_generator.py#L501) | no | no |
| outcome_code | string enum | pay/deny/escalate | [decisiongraph-complete/src/decisiongraph/aml_seed_generator.py](decisiongraph-complete/src/decisiongraph/aml_seed_generator.py#L502) | yes | no |
| certainty | string enum | high | [decisiongraph-complete/src/decisiongraph/aml_seed_generator.py](decisiongraph-complete/src/decisiongraph/aml_seed_generator.py#L503) | no | no |
| anchor_facts | list[AnchorFact] | field_id/value/label objects | [decisiongraph-complete/src/decisiongraph/aml_seed_generator.py](decisiongraph-complete/src/decisiongraph/aml_seed_generator.py#L454-L472) | yes | no |
| policy_pack_hash | string (sha256 hex) | fincrime_canada_v2026 | [decisiongraph-complete/src/decisiongraph/aml_seed_generator.py](decisiongraph-complete/src/decisiongraph/aml_seed_generator.py#L505) | no | no |
| policy_pack_id | string | fincrime_canada | [decisiongraph-complete/src/decisiongraph/aml_seed_generator.py](decisiongraph-complete/src/decisiongraph/aml_seed_generator.py#L506) | no | no |
| policy_version | string | 2026.02.01 | [decisiongraph-complete/src/decisiongraph/aml_seed_generator.py](decisiongraph-complete/src/decisiongraph/aml_seed_generator.py#L507) | no | no |
| decision_level | string enum | manager | [decisiongraph-complete/src/decisiongraph/aml_seed_generator.py](decisiongraph-complete/src/decisiongraph/aml_seed_generator.py#L508) | no | no |
| decided_at | string (ISO 8601) | generated timestamp | [decisiongraph-complete/src/decisiongraph/aml_seed_generator.py](decisiongraph-complete/src/decisiongraph/aml_seed_generator.py#L509) | no | no |
| decided_by_role | string | aml_analyst | [decisiongraph-complete/src/decisiongraph/aml_seed_generator.py](decisiongraph-complete/src/decisiongraph/aml_seed_generator.py#L510) | no | no |
| source_type | string | seed | [decisiongraph-complete/src/decisiongraph/aml_seed_generator.py](decisiongraph-complete/src/decisiongraph/aml_seed_generator.py#L511) | no | no |
| scenario_code | string | scenario name | [decisiongraph-complete/src/decisiongraph/aml_seed_generator.py](decisiongraph-complete/src/decisiongraph/aml_seed_generator.py#L512) | no | no |
| seed_category | string | aml | [decisiongraph-complete/src/decisiongraph/aml_seed_generator.py](decisiongraph-complete/src/decisiongraph/aml_seed_generator.py#L513) | no | no |
| disposition_basis | string enum | MANDATORY/DISCRETIONARY | [decisiongraph-complete/src/decisiongraph/aml_seed_generator.py](decisiongraph-complete/src/decisiongraph/aml_seed_generator.py#L514) | yes | no |
| reporting_obligation | string enum | NO_REPORT/FILE_STR/FILE_LCTR/FILE_TPR | [decisiongraph-complete/src/decisiongraph/aml_seed_generator.py](decisiongraph-complete/src/decisiongraph/aml_seed_generator.py#L515) | yes | no |
| customer.type | string enum | individual/corporation | [decisiongraph-complete/src/decisiongraph/aml_seed_generator.py](decisiongraph-complete/src/decisiongraph/aml_seed_generator.py#L71) | yes | no |
| customer.pep | boolean | true/false | [decisiongraph-complete/src/decisiongraph/aml_seed_generator.py](decisiongraph-complete/src/decisiongraph/aml_seed_generator.py#L72) | yes | no |
| customer.relationship_length | string enum | new/established | [decisiongraph-complete/src/decisiongraph/aml_seed_generator.py](decisiongraph-complete/src/decisiongraph/aml_seed_generator.py#L73) | yes | no |
| screening.sanctions_match | boolean | true/false | [decisiongraph-complete/src/decisiongraph/aml_seed_generator.py](decisiongraph-complete/src/decisiongraph/aml_seed_generator.py#L74) | yes | no |
| txn.cross_border | boolean | true/false | [decisiongraph-complete/src/decisiongraph/aml_seed_generator.py](decisiongraph-complete/src/decisiongraph/aml_seed_generator.py#L75) | yes | no |
| txn.destination_country_risk | string enum | low/medium/high | [decisiongraph-complete/src/decisiongraph/aml_seed_generator.py](decisiongraph-complete/src/decisiongraph/aml_seed_generator.py#L76) | yes | no |
| txn.amount_band | string enum | under_3k/3k_10k/10k_25k/25k_100k/100k_500k/500k_1m/over_1m | [decisiongraph-complete/src/decisiongraph/aml_seed_generator.py](decisiongraph-complete/src/decisiongraph/aml_seed_generator.py#L185), [decisiongraph-complete/src/decisiongraph/aml_seed_generator.py](decisiongraph-complete/src/decisiongraph/aml_seed_generator.py#L465-L467) | yes | no |
| txn.type | string enum | wire/cash/eft/cheque/crypto | [decisiongraph-complete/src/decisiongraph/aml_seed_generator.py](decisiongraph-complete/src/decisiongraph/aml_seed_generator.py#L184), [decisiongraph-complete/src/decisiongraph/aml_seed_generator.py](decisiongraph-complete/src/decisiongraph/aml_seed_generator.py#L470-L472) | yes | no |

## 1. CANONICAL BANKING FIELD REGISTRY

Master registry of fields seen across seed generation, fingerprinting, and report evidence. Line references point to the layer where the field is set or mapped.

| Canonical name | Seed generator name | Fingerprint dimension name | Report display name | Human-readable description | Data type and allowed values | Required for matching? | Insurance contamination? |
|---|---|---|---|---|---|---|---|
| precedent_id | precedent_id ([decisiongraph-complete/src/decisiongraph/aml_seed_generator.py](decisiongraph-complete/src/decisiongraph/aml_seed_generator.py#L494)) | - | - | Precedent UUID | string (UUID) | no | no |
| case_id_hash | case_id_hash ([decisiongraph-complete/src/decisiongraph/aml_seed_generator.py](decisiongraph-complete/src/decisiongraph/aml_seed_generator.py#L495)) | - | - | Privacy-preserving case hash | string (sha256 hex) | no | no |
| jurisdiction_code | jurisdiction_code ([decisiongraph-complete/src/decisiongraph/aml_seed_generator.py](decisiongraph-complete/src/decisiongraph/aml_seed_generator.py#L496)) | - | - | Jurisdiction code (used for weighting) | string (ISO country) | no | no |
| fingerprint_hash | fingerprint_hash ([decisiongraph-complete/src/decisiongraph/aml_seed_generator.py](decisiongraph-complete/src/decisiongraph/aml_seed_generator.py#L497)) | - | - | Seed fingerprint hash | string (sha256 hex) | no | no |
| fingerprint_schema_id | fingerprint_schema_id ([decisiongraph-complete/src/decisiongraph/aml_seed_generator.py](decisiongraph-complete/src/decisiongraph/aml_seed_generator.py#L498)) | schema_id | - | Fingerprint schema selector | string (decisiongraph:aml:*:v1) | yes | no |
| exclusion_codes | exclusion_codes ([decisiongraph-complete/src/decisiongraph/aml_seed_generator.py](decisiongraph-complete/src/decisiongraph/aml_seed_generator.py#L499)) | rules_overlap | - | Reason code list used for overlap | list[string] (RC-*) | yes | yes (insurance term) |
| reason_codes | reason_codes ([decisiongraph-complete/src/decisiongraph/aml_seed_generator.py](decisiongraph-complete/src/decisiongraph/aml_seed_generator.py#L500)) | rules_overlap | - | Reason code list used for overlap | list[string] (RC-*) | yes | no |
| reason_code_registry_id | reason_code_registry_id ([decisiongraph-complete/src/decisiongraph/aml_seed_generator.py](decisiongraph-complete/src/decisiongraph/aml_seed_generator.py#L501)) | - | - | Reason code registry ID | string | no | no |
| outcome_code | outcome_code ([decisiongraph-complete/src/decisiongraph/aml_seed_generator.py](decisiongraph-complete/src/decisiongraph/aml_seed_generator.py#L502)) | outcome | - | Precedent outcome code | string enum pay/deny/escalate | yes | yes (insurance outcome labels) |
| certainty | certainty ([decisiongraph-complete/src/decisiongraph/aml_seed_generator.py](decisiongraph-complete/src/decisiongraph/aml_seed_generator.py#L503)) | - | - | Decision certainty | string enum high/medium/low | no | no |
| policy_pack_hash | policy_pack_hash ([decisiongraph-complete/src/decisiongraph/aml_seed_generator.py](decisiongraph-complete/src/decisiongraph/aml_seed_generator.py#L505)) | - | - | Policy pack hash | string (sha256 hex) | no | no |
| policy_pack_id | policy_pack_id ([decisiongraph-complete/src/decisiongraph/aml_seed_generator.py](decisiongraph-complete/src/decisiongraph/aml_seed_generator.py#L506)) | - | - | Policy pack identifier | string | no | no |
| policy_version | policy_version ([decisiongraph-complete/src/decisiongraph/aml_seed_generator.py](decisiongraph-complete/src/decisiongraph/aml_seed_generator.py#L507)) | - | - | Policy version | string | no | no |
| decision_level | decision_level ([decisiongraph-complete/src/decisiongraph/aml_seed_generator.py](decisiongraph-complete/src/decisiongraph/aml_seed_generator.py#L508)) | decision_weight | - | Decision authority level (used for weighting) | string enum adjuster/manager/tribunal/court | no | yes (adjuster term) |
| decided_at | decided_at ([decisiongraph-complete/src/decisiongraph/aml_seed_generator.py](decisiongraph-complete/src/decisiongraph/aml_seed_generator.py#L509)) | recency_weight | - | Decision timestamp (used for weighting) | string (ISO 8601) | no | no |
| decided_by_role | decided_by_role ([decisiongraph-complete/src/decisiongraph/aml_seed_generator.py](decisiongraph-complete/src/decisiongraph/aml_seed_generator.py#L510)) | - | - | Decision-maker role | string | no | no |
| source_type | source_type ([decisiongraph-complete/src/decisiongraph/aml_seed_generator.py](decisiongraph-complete/src/decisiongraph/aml_seed_generator.py#L511)) | - | - | Seed/prod source flag | string | no | no |
| scenario_code | scenario_code ([decisiongraph-complete/src/decisiongraph/aml_seed_generator.py](decisiongraph-complete/src/decisiongraph/aml_seed_generator.py#L512)) | - | - | Seed scenario id | string | no | no |
| seed_category | seed_category ([decisiongraph-complete/src/decisiongraph/aml_seed_generator.py](decisiongraph-complete/src/decisiongraph/aml_seed_generator.py#L513)) | - | - | Seed category | string | no | no |
| disposition_basis | disposition_basis ([decisiongraph-complete/src/decisiongraph/aml_seed_generator.py](decisiongraph-complete/src/decisiongraph/aml_seed_generator.py#L514)) | disposition_basis | - | Mandatory vs discretionary | string enum MANDATORY/DISCRETIONARY/UNKNOWN | yes | no |
| reporting_obligation | reporting_obligation ([decisiongraph-complete/src/decisiongraph/aml_seed_generator.py](decisiongraph-complete/src/decisiongraph/aml_seed_generator.py#L515)) | reporting | - | Reporting obligation | string enum NO_REPORT/FILE_STR/FILE_LCTR/FILE_TPR/UNKNOWN | yes | no |
| customer.type | customer.type ([decisiongraph-complete/src/decisiongraph/aml_seed_generator.py](decisiongraph-complete/src/decisiongraph/aml_seed_generator.py#L71)) | customer.type | Customer entity type ([decisiongraph-complete/service/routers/report/render_md.py](decisiongraph-complete/service/routers/report/render_md.py#L312-L319)) | Customer entity type | string enum individual/corporation/mixed | yes | no |
| customer.pep | customer.pep ([decisiongraph-complete/src/decisiongraph/aml_seed_generator.py](decisiongraph-complete/src/decisiongraph/aml_seed_generator.py#L72)) | customer.pep | - | PEP boolean for matching | boolean | yes | no |
| customer.relationship_length | customer.relationship_length ([decisiongraph-complete/src/decisiongraph/aml_seed_generator.py](decisiongraph-complete/src/decisiongraph/aml_seed_generator.py#L73)) | customer.relationship_length | - | Relationship duration band | string enum new/established | yes | no |
| screening.sanctions_match | screening.sanctions_match ([decisiongraph-complete/src/decisiongraph/aml_seed_generator.py](decisiongraph-complete/src/decisiongraph/aml_seed_generator.py#L74)) | screening.sanctions_match | - | Sanctions match boolean | boolean | yes | no |
| txn.cross_border | txn.cross_border ([decisiongraph-complete/src/decisiongraph/aml_seed_generator.py](decisiongraph-complete/src/decisiongraph/aml_seed_generator.py#L75)) | txn.cross_border | Transaction cross-border indicator ([decisiongraph-complete/service/routers/report/render_md.py](decisiongraph-complete/service/routers/report/render_md.py#L309-L316)) | Cross-border transaction flag | boolean | yes | no |
| txn.destination_country_risk | txn.destination_country_risk ([decisiongraph-complete/src/decisiongraph/aml_seed_generator.py](decisiongraph-complete/src/decisiongraph/aml_seed_generator.py#L76)) | txn.destination_country_risk | - | Destination country risk band | string enum low/medium/high | yes | no |
| txn.amount_band | txn.amount_band ([decisiongraph-complete/src/decisiongraph/aml_seed_generator.py](decisiongraph-complete/src/decisiongraph/aml_seed_generator.py#L185), [decisiongraph-complete/src/decisiongraph/aml_seed_generator.py](decisiongraph-complete/src/decisiongraph/aml_seed_generator.py#L465-L467)) | txn.amount_band | Transaction amount band ([decisiongraph-complete/service/routers/report/render_md.py](decisiongraph-complete/service/routers/report/render_md.py#L316-L321)) | Banded transaction amount | string enum under_3k/3k_10k/10k_25k/25k_100k/100k_500k/500k_1m/over_1m | yes | no |
| txn.type | txn.type ([decisiongraph-complete/src/decisiongraph/aml_seed_generator.py](decisiongraph-complete/src/decisiongraph/aml_seed_generator.py#L184), [decisiongraph-complete/src/decisiongraph/aml_seed_generator.py](decisiongraph-complete/src/decisiongraph/aml_seed_generator.py#L470-L472)) | txn.type | - | Transaction channel | string enum wire/cash/eft/cheque/crypto | yes | no |
| facts.sanctions_result | - | - | facts.sanctions_result (raw) ([decisiongraph-complete/src/decisiongraph/decision_pack.py](decisiongraph-complete/src/decisiongraph/decision_pack.py#L485-L494)) | Screening result in evaluation trace | string enum MATCH/NO_MATCH/PENDING | no | no |
| facts.adverse_media_mltf | - | - | facts.adverse_media_mltf (raw) ([decisiongraph-complete/src/decisiongraph/decision_pack.py](decisiongraph-complete/src/decisiongraph/decision_pack.py#L485-L494)) | Adverse media ML/TF flag | boolean | no | no |
| suspicion.has_intent | - | - | suspicion.has_intent (raw) ([decisiongraph-complete/src/decisiongraph/decision_pack.py](decisiongraph-complete/src/decisiongraph/decision_pack.py#L485-L494)) | Suspicion element: intent | boolean | no | no |
| suspicion.has_deception | - | - | suspicion.has_deception (raw) ([decisiongraph-complete/src/decisiongraph/decision_pack.py](decisiongraph-complete/src/decisiongraph/decision_pack.py#L485-L494)) | Suspicion element: deception | boolean | no | no |
| suspicion.has_sustained_pattern | - | - | suspicion.has_sustained_pattern (raw) ([decisiongraph-complete/src/decisiongraph/decision_pack.py](decisiongraph-complete/src/decisiongraph/decision_pack.py#L485-L494)) | Suspicion element: sustained pattern | boolean | no | no |
| obligations.count | - | - | obligations.count (raw) ([decisiongraph-complete/src/decisiongraph/decision_pack.py](decisiongraph-complete/src/decisiongraph/decision_pack.py#L485-L494)) | Count of regulatory obligations | integer | no | no |
| mitigations.count | - | - | mitigations.count (raw) ([decisiongraph-complete/src/decisiongraph/decision_pack.py](decisiongraph-complete/src/decisiongraph/decision_pack.py#L485-L494)) | Count of mitigations | integer | no | no |
| typology.maturity | - | - | typology.maturity (raw) ([decisiongraph-complete/src/decisiongraph/decision_pack.py](decisiongraph-complete/src/decisiongraph/decision_pack.py#L485-L494)) | Typology maturity | string enum NONE/FORMING/ESTABLISHED/CONFIRMED | no | no |
| indicator.<code> | - | - | indicator.<code> (raw) ([decisiongraph-complete/service/main.py](decisiongraph-complete/service/main.py#L685-L690)) | Input indicator corroboration | boolean | no | no |
| customer.pep_flag | - | - | Customer PEP status ([decisiongraph-complete/service/routers/report/render_md.py](decisiongraph-complete/service/routers/report/render_md.py#L312-L319)) | Customer PEP flag from report bridge | boolean or Y/N string | no | no |
| risk.high_risk_jurisdiction | - | - | Customer domicile jurisdiction risk ([decisiongraph-complete/service/routers/report/render_md.py](decisiongraph-complete/service/routers/report/render_md.py#L309-L312)) | High-risk jurisdiction flag | boolean | no | no |
| txn.method | - | - | Payment method ([decisiongraph-complete/service/routers/report/render_md.py](decisiongraph-complete/service/routers/report/render_md.py#L316-L318)) | Transaction method in reports | string | no | no |
| txn.destination_country | - | - | Transaction destination jurisdiction ([decisiongraph-complete/service/routers/report/render_md.py](decisiongraph-complete/service/routers/report/render_md.py#L309-L313)) | Transaction destination country | string (ISO country) | no | no |
| flag.structuring_suspected | - | - | Structuring indicator (transaction pattern) ([decisiongraph-complete/service/routers/report/render_md.py](decisiongraph-complete/service/routers/report/render_md.py#L319-L323)) | Structuring flag | boolean | no | no |
| flag.sanctions_proximity | - | - | Sanctions screening proximity ([decisiongraph-complete/service/routers/report/render_md.py](decisiongraph-complete/service/routers/report/render_md.py#L319-L323)) | Sanctions proximity flag | boolean | no | no |
| flag.adverse_media | - | - | Adverse media indicator ([decisiongraph-complete/service/routers/report/render_md.py](decisiongraph-complete/service/routers/report/render_md.py#L319-L323)) | Adverse media flag | boolean | no | no |
| flag.rapid_movement | - | - | Rapid fund movement indicator ([decisiongraph-complete/service/routers/report/render_md.py](decisiongraph-complete/service/routers/report/render_md.py#L321-L323)) | Rapid movement flag | boolean | no | no |
| flag.shell_entity | - | - | Shell entity indicator ([decisiongraph-complete/service/routers/report/render_md.py](decisiongraph-complete/service/routers/report/render_md.py#L322-L323)) | Shell entity flag | boolean | no | no |
| flag.cross_border | - | - | Cross-border flag (transaction-level) ([decisiongraph-complete/service/routers/report/render_md.py](decisiongraph-complete/service/routers/report/render_md.py#L311-L314)) | Cross-border flag (alternate namespace) | boolean | no | no |
| flag.pep | - | - | PEP flag (customer-level) ([decisiongraph-complete/service/routers/report/render_md.py](decisiongraph-complete/service/routers/report/render_md.py#L314-L316)) | PEP flag (alternate namespace) | boolean | no | no |
| flag.layering | - | - | - | Layering flag | boolean | no | no |
| flag.funnel_account | - | - | - | Funnel account flag | boolean | no | no |
| flag.third_party_unexplained | - | - | - | Third-party flag | boolean | no | no |
| flag.false_source | - | - | - | False source flag | boolean | no | no |
| flag.evasion | - | - | - | Evasion flag | boolean | no | no |
| flag.sar_pattern | - | - | - | SAR pattern flag | boolean | no | no |
| flag.crypto | - | - | - | Crypto flag | boolean | no | no |
| flag.high_value | - | - | - | High value flag | boolean | no | no |
| flag.new_account | - | - | - | New account flag | boolean | no | no |
| flag.cash_intensive | - | - | - | Cash intensive flag | boolean | no | no |
| flag.dormant_reactivated | - | - | - | Dormant reactivation flag | boolean | no | no |
| txn.originator_country_risk | - | txn.originator_country_risk | - | Originator country risk | string enum low/medium/high | no | no |
| txn.round_amount | - | txn.round_amount | - | Round amount indicator | boolean | no | no |
| txn.just_below_threshold | - | txn.just_below_threshold | - | Just-below threshold indicator | boolean | no | no |
| txn.multiple_same_day | - | txn.multiple_same_day | - | Multiple same-day txns | boolean | no | no |
| txn.rapid_movement | - | txn.rapid_movement | - | Rapid movement indicator | boolean | no | no |
| txn.pattern_matches_profile | - | txn.pattern_matches_profile | - | Pattern matches profile | boolean | no | no |
| txn.third_party_involved | - | txn.third_party_involved | - | Third party involvement | boolean | no | no |
| customer.risk_level | - | customer.risk_level | - | Customer risk level | string enum low/medium/high | no | no |
| customer.pep_type | - | customer.pep_type | - | PEP type | string enum domestic/foreign/rca | no | no |
| customer.high_risk_industry | - | customer.high_risk_industry | - | High-risk industry flag | boolean | no | no |
| crypto.exchange_regulated | - | crypto.exchange_regulated | - | Regulated exchange flag | boolean | no | no |
| crypto.wallet_type | - | crypto.wallet_type | - | Wallet type | string enum hosted/unhosted | no | no |
| crypto.mixer_indicators | - | crypto.mixer_indicators | - | Mixer/tumbler indicators | boolean | no | no |
| screening.adverse_media | - | screening.adverse_media | - | Adverse media flag | boolean | no | no |
| customer.jurisdiction | - | customer.jurisdiction | - | Customer jurisdiction | string | no | no |
| customer.tax_residency | - | customer.tax_residency | - | Customer tax residency | string | no | no |
| customer.pep_level | - | customer.pep_level | - | PEP level | string enum head_of_state/senior_official/etc | no | no |
| customer.rca | - | customer.rca | - | Related/close associate | boolean | no | no |
| customer.industry_type | - | customer.industry_type | - | Industry type | string | no | no |
| customer.cash_intensive | - | customer.cash_intensive | - | Cash-intensive business | boolean | no | no |
| kyc.id_verified | - | kyc.id_verified | - | ID verified | boolean | no | no |
| kyc.id_type | - | kyc.id_type | - | ID type | string | no | no |
| kyc.id_expired | - | kyc.id_expired | - | ID expired | boolean | no | no |
| kyc.address_verified | - | kyc.address_verified | - | Address verified | boolean | no | no |
| kyc.address_proof_type | - | kyc.address_proof_type | - | Address proof type | string | no | no |
| kyc.beneficial_owners_identified | - | kyc.beneficial_owners_identified | - | UBO identified | boolean | no | no |
| kyc.ubo_over_25_pct | - | kyc.ubo_over_25_pct | - | UBO over 25 percent | boolean | no | no |
| kyc.source_of_wealth_documented | - | kyc.source_of_wealth_documented | - | Source of wealth documented | boolean | no | no |
| kyc.source_of_funds_documented | - | kyc.source_of_funds_documented | - | Source of funds documented | boolean | no | no |
| kyc.business_activity_verified | - | kyc.business_activity_verified | - | Business activity verified | boolean | no | no |
| shell.nominee_directors | - | shell.nominee_directors | - | Nominee directors | boolean | no | no |
| shell.registered_agent_only | - | shell.registered_agent_only | - | Registered agent only | boolean | no | no |
| shell.no_physical_presence | - | shell.no_physical_presence | - | No physical presence | boolean | no | no |
| shell.complex_structure | - | shell.complex_structure | - | Complex structure | boolean | no | no |
| edd.required | - | edd.required | - | EDD required | boolean | no | no |
| edd.complete | - | edd.complete | - | EDD complete | boolean | no | no |
| edd.senior_approval | - | edd.senior_approval | - | Senior approval | boolean | no | no |
| screening.pep_match | - | screening.pep_match | - | PEP screening match | boolean | no | no |
| screening.adverse_media_severity | - | screening.adverse_media_severity | - | Adverse media severity | string enum low/medium/high | no | no |
| txn.cash_involved | - | txn.cash_involved | - | Cash involved flag | boolean | no | no |
| txn.cash_amount_band | - | txn.cash_amount_band | - | Cash amount band | string | no | no |
| suspicious.indicator_count | - | suspicious.indicator_count | - | Suspicious indicator count | integer banded | no | no |
| suspicious.structuring | - | suspicious.structuring | - | Structuring indicators | boolean | no | no |
| suspicious.unusual_pattern | - | suspicious.unusual_pattern | - | Unusual pattern | boolean | no | no |
| suspicious.third_party | - | suspicious.third_party | - | Third-party indicator | boolean | no | no |
| suspicious.layering | - | suspicious.layering | - | Layering indicator | boolean | no | no |
| suspicious.source_unclear | - | suspicious.source_unclear | - | Source unclear | boolean | no | no |
| suspicious.purpose_unclear | - | suspicious.purpose_unclear | - | Purpose unclear | boolean | no | no |
| terrorist.property_indicators | - | terrorist.property_indicators | - | Terrorist property indicators | boolean | no | no |
| terrorist.listed_entity | - | terrorist.listed_entity | - | Listed entity flag | boolean | no | no |
| terrorist.associated_entity | - | terrorist.associated_entity | - | Associated entity flag | boolean | no | no |
| prior.sars_filed | - | prior.sars_filed | - | Prior SARs filed | integer banded | no | no |
| prior.lctr_filed | - | prior.lctr_filed | - | Prior LCTRs filed | integer | no | no |
| prior.account_closures | - | prior.account_closures | - | Prior account closures | integer | no | no |
| match.type | - | match.type | - | Screening match type | string | no | no |
| match.list_source | - | match.list_source | - | Screening list source | string | no | no |
| match.score_band | - | match.score_band | - | Match score band | string enum low/medium/high/exact | no | no |
| match.name_match_type | - | match.name_match_type | - | Name match type | string enum exact/fuzzy/alias/partial | no | no |
| match.secondary_identifiers | - | match.secondary_identifiers | - | Secondary identifiers matched | boolean | no | no |
| entity.type | - | entity.type | - | Entity type | string | no | no |
| entity.jurisdiction | - | entity.jurisdiction | - | Entity jurisdiction | string | no | no |
| ownership.direct_pct_band | - | ownership.direct_pct_band | - | Direct ownership percent band | string | no | no |
| ownership.indirect_pct_band | - | ownership.indirect_pct_band | - | Indirect ownership percent band | string | no | no |
| ownership.aggregated_over_50 | - | ownership.aggregated_over_50 | - | Aggregated ownership over 50 percent | boolean | no | no |
| ownership.chain_depth | - | ownership.chain_depth | - | Ownership chain depth | integer | no | no |
| delisted.status | - | delisted.status | - | Delisted status | boolean | no | no |
| delisted.date_band | - | delisted.date_band | - | Delisted date band | string | no | no |
| secondary.exposure | - | secondary.exposure | - | Secondary sanctions exposure | boolean | no | no |
| secondary.jurisdiction | - | secondary.jurisdiction | - | Secondary sanctions jurisdiction | string | no | no |
| trigger.type | - | trigger.type | - | Monitoring trigger type | string | no | no |
| activity.volume_change_band | - | activity.volume_change_band | - | Volume change band | string | no | no |
| activity.value_change_band | - | activity.value_change_band | - | Value change band | string | no | no |
| activity.new_pattern | - | activity.new_pattern | - | New pattern flag | boolean | no | no |
| activity.new_jurisdiction | - | activity.new_jurisdiction | - | New jurisdiction flag | boolean | no | no |
| activity.new_counterparty_type | - | activity.new_counterparty_type | - | New counterparty type | string | no | no |
| review.type | - | review.type | - | Review type | string | no | no |
| review.risk_change | - | review.risk_change | - | Risk change | string | no | no |
| review.kyc_refresh_needed | - | review.kyc_refresh_needed | - | KYC refresh needed | boolean | no | no |
| profile.address_change | - | profile.address_change | - | Address change | boolean | no | no |
| profile.bo_change | - | profile.bo_change | - | Beneficial owner change | boolean | no | no |
| profile.industry_change | - | profile.industry_change | - | Industry change | boolean | no | no |
| profile.jurisdiction_change | - | profile.jurisdiction_change | - | Jurisdiction change | boolean | no | no |
| dormant.months_inactive | - | dormant.months_inactive | - | Dormancy months | integer banded | no | no |
| dormant.reactivation_pattern | - | dormant.reactivation_pattern | - | Reactivation pattern | string | no | no |
| exit.reason | - | exit.reason | - | Exit reason | string | no | no |
| exit.sar_related | - | exit.sar_related | - | Exit SAR-related | boolean | no | no |

## 2. INCONSISTENCY LIST

- amount_bucket vs txn.amount_band: docs reference amount_bucket but seeds/matching use txn.amount_band ([decisiongraph-complete/docs/PRECEDENT_SCORING.md](decisiongraph-complete/docs/PRECEDENT_SCORING.md#L452), [decisiongraph-complete/src/decisiongraph/aml_seed_generator.py](decisiongraph-complete/src/decisiongraph/aml_seed_generator.py#L185)). Canonical: txn.amount_band.
- channel vs txn.type vs txn.method: matching uses txn.type ([decisiongraph-complete/service/main.py](decisiongraph-complete/service/main.py#L1888-L1891)), report evidence uses txn.method ([decisiongraph-complete/service/routers/report/render_md.py](decisiongraph-complete/service/routers/report/render_md.py#L316-L318)), input uses transaction.method ([decisiongraph-complete/schemas/input.case.schema.json](decisiongraph-complete/schemas/input.case.schema.json#L93-L133)). Canonical: txn.type.
- corridor vs txn.cross_border vs txn.destination_country_risk vs txn.destination_country: matching uses txn.cross_border/txn.destination_country_risk ([decisiongraph-complete/service/main.py](decisiongraph-complete/service/main.py#L1891-L1905)), reports display txn.destination_country ([decisiongraph-complete/service/routers/report/render_md.py](decisiongraph-complete/service/routers/report/render_md.py#L309-L313)). Canonical: txn.cross_border + txn.destination_country_risk.
- customer_type vs customer.type vs entity.type: matching uses customer.type with fallback entity.type ([decisiongraph-complete/service/main.py](decisiongraph-complete/service/main.py#L1843-L1847)). Canonical: customer.type.
- pep vs customer.pep vs customer.pep_flag vs flag.pep vs risk.pep/screen.pep_match (BYOC) ([decisiongraph-complete/service/template_loader.py](decisiongraph-complete/service/template_loader.py#L277-L303), [decisiongraph-complete/service/routers/report/render_md.py](decisiongraph-complete/service/routers/report/render_md.py#L312-L316)). Canonical: customer.pep (boolean); derive customer.pep_flag only for display.
- screening.sanctions_match vs facts.sanctions_result vs flag.sanctions_proximity vs screen.sanctions_match: matching uses screening.sanctions_match (seed) ([decisiongraph-complete/src/decisiongraph/aml_seed_generator.py](decisiongraph-complete/src/decisiongraph/aml_seed_generator.py#L74)); reports use facts.sanctions_result from decision_pack ([decisiongraph-complete/src/decisiongraph/decision_pack.py](decisiongraph-complete/src/decisiongraph/decision_pack.py#L485-L494)). Canonical: screening.sanctions_match (boolean) plus facts.sanctions_result (status string) as a separate field.
- customer.relationship_length vs customer.relationship_months: fingerprint banding rule uses customer.relationship_months while schema expects customer.relationship_length ([decisiongraph-complete/src/decisiongraph/aml_fingerprint.py](decisiongraph-complete/src/decisiongraph/aml_fingerprint.py#L424-L455), [decisiongraph-complete/src/decisiongraph/aml_fingerprint.py](decisiongraph-complete/src/decisiongraph/aml_fingerprint.py#L470-L540)). Canonical: customer.relationship_length.
- txn.amount_band vs txn.amount: banding rule expects txn.amount but schema uses txn.amount_band ([decisiongraph-complete/src/decisiongraph/aml_fingerprint.py](decisiongraph-complete/src/decisiongraph/aml_fingerprint.py#L400-L430), [decisiongraph-complete/src/decisiongraph/aml_fingerprint.py](decisiongraph-complete/src/decisiongraph/aml_fingerprint.py#L470-L540)). Canonical: txn.amount_band.
- reason_codes vs exclusion_codes: AML uses reason codes but registry still uses exclusion_codes for overlap search ([decisiongraph-complete/service/main.py](decisiongraph-complete/service/main.py#L1820-L1828)). Canonical: reason_codes.

## 3. MISSING/ORPHANED FIELDS

### Seeds but not in fingerprint schema

- None found. All seed anchor facts are present in the txn schema relevant_facts list.

### Fingerprint schema fields not in seeds (matching has sparse data)

- Transaction schema: txn.originator_country_risk, txn.round_amount, txn.just_below_threshold, txn.multiple_same_day, txn.rapid_movement, txn.pattern_matches_profile, txn.third_party_involved, customer.risk_level, customer.pep_type, customer.high_risk_industry, crypto.exchange_regulated, crypto.wallet_type, crypto.mixer_indicators, screening.adverse_media ([decisiongraph-complete/src/decisiongraph/aml_fingerprint.py](decisiongraph-complete/src/decisiongraph/aml_fingerprint.py#L470-L540)).
- KYC schema: customer.jurisdiction, customer.tax_residency, customer.pep_level, customer.rca, customer.industry_type, customer.cash_intensive, kyc.* fields, shell.* fields, edd.* fields, screening.pep_match, screening.adverse_media_severity ([decisiongraph-complete/src/decisiongraph/aml_fingerprint.py](decisiongraph-complete/src/decisiongraph/aml_fingerprint.py#L544-L640)).
- Reporting schema: txn.cash_involved, txn.cash_amount_band, suspicious.* fields, terrorist.* fields, prior.* fields ([decisiongraph-complete/src/decisiongraph/aml_fingerprint.py](decisiongraph-complete/src/decisiongraph/aml_fingerprint.py#L656-L740)).
- Screening schema: match.*, entity.*, ownership.*, delisted.*, secondary.* fields ([decisiongraph-complete/src/decisiongraph/aml_fingerprint.py](decisiongraph-complete/src/decisiongraph/aml_fingerprint.py#L748-L820)).
- Monitoring schema: trigger.*, activity.*, review.*, profile.*, dormant.*, exit.* fields ([decisiongraph-complete/src/decisiongraph/aml_fingerprint.py](decisiongraph-complete/src/decisiongraph/aml_fingerprint.py#L860-L930)).

### Report evidence fields not in seeds

- facts.sanctions_result, facts.adverse_media_mltf, suspicion.*, obligations.count, mitigations.count, typology.maturity, indicator.* from decision_pack ([decisiongraph-complete/src/decisiongraph/decision_pack.py](decisiongraph-complete/src/decisiongraph/decision_pack.py#L485-L494)).
- customer.pep_flag, txn.method, txn.destination_country, risk.high_risk_jurisdiction from report bridge ([decisiongraph-complete/report_bridge.py](decisiongraph-complete/report_bridge.py#L109-L136)).

### Fingerprint schema fields not in evidence

- All schema-only fields listed above are not emitted into evaluation_trace evidence_used and therefore never appear in the Evidence Considered table.

## 4. CONTAMINATION LIST

| File and line | Contaminating term | Banking replacement | Affects |
|---|---|---|---|
| [decisiongraph-complete/src/decisiongraph/aml_seed_generator.py](decisiongraph-complete/src/decisiongraph/aml_seed_generator.py#L56) | outcome pay/deny/escalate | disposition ALLOW/EDD/BLOCK | storage + matching |
| [decisiongraph-complete/src/decisiongraph/aml_seed_generator.py](decisiongraph-complete/src/decisiongraph/aml_seed_generator.py#L499) | exclusion_codes | reason_codes or signal_codes | matching + storage |
| [decisiongraph-complete/src/decisiongraph/judgment.py](decisiongraph-complete/src/decisiongraph/judgment.py#L269-L286) | outcome_code pay/deny/partial/escalate | disposition/reporting fields | storage + matching |
| [decisiongraph-complete/src/decisiongraph/judgment.py](decisiongraph-complete/src/decisiongraph/judgment.py#L285-L289) | decision_level adjuster | analyst/manager/executive | matching weight |
| [decisiongraph-complete/service/main.py](decisiongraph-complete/service/main.py#L951-L955) | verdict mapped to pay/deny/escalate | disposition ALLOW/EDD/BLOCK | matching |
| [decisiongraph-complete/service/main.py](decisiongraph-complete/service/main.py#L1820-L1828) | find_by_exclusion_codes | find_by_reason_codes | matching |
| [decisiongraph-complete/src/decisiongraph/judgment.py](decisiongraph-complete/src/decisiongraph/judgment.py#L153-L170) | insurance docstrings (claim/exclusion) | AML reason codes | documentation |

## 5. RECOMMENDED CANONICAL SCHEMA

Proposed single schema for evidence, fingerprints, matching, and report display. All layers should map to these names.

```yaml
customer:
  type: string  # individual/corporation/mixed
  pep: boolean
  pep_type: string  # domestic/foreign/rca
  relationship_length: string  # new/recent/established/long_term
  risk_level: string  # low/medium/high

screening:
  sanctions_match: boolean
  adverse_media: boolean
  adverse_media_severity: string

txn:
  type: string  # wire/cash/eft/cheque/crypto
  amount_band: string  # under_3k/.../over_1m
  cross_border: boolean
  destination_country_risk: string  # low/medium/high
  destination_country: string  # ISO country for display

risk:
  high_risk_jurisdiction: boolean

flags:
  structuring_suspected: boolean
  sanctions_proximity: boolean
  adverse_media: boolean
  rapid_movement: boolean
  shell_entity: boolean
  cross_border: boolean
  pep: boolean

suspicion:
  has_intent: boolean
  has_deception: boolean
  has_sustained_pattern: boolean

obligations:
  count: integer

mitigations:
  count: integer

typology:
  maturity: string

indicator:
  <code>: boolean
```

## 6. PART 6: MISSING FIELDS VS REPORTED "MISSING FEATURES"

The report guidance lists missing features: amount_bucket, channel, corridor, customer_type, relationship_length, pep ([decisiongraph-complete/docs/PRECEDENT_SCORING.md](decisiongraph-complete/docs/PRECEDENT_SCORING.md#L452)).

- Present in seeds under different names:
  - amount_bucket -> txn.amount_band ([decisiongraph-complete/src/decisiongraph/aml_seed_generator.py](decisiongraph-complete/src/decisiongraph/aml_seed_generator.py#L185))
  - channel -> txn.type ([decisiongraph-complete/src/decisiongraph/aml_seed_generator.py](decisiongraph-complete/src/decisiongraph/aml_seed_generator.py#L184))
  - corridor -> txn.cross_border + txn.destination_country_risk ([decisiongraph-complete/src/decisiongraph/aml_seed_generator.py](decisiongraph-complete/src/decisiongraph/aml_seed_generator.py#L75-L76))
  - customer_type -> customer.type ([decisiongraph-complete/src/decisiongraph/aml_seed_generator.py](decisiongraph-complete/src/decisiongraph/aml_seed_generator.py#L71))
  - relationship_length -> customer.relationship_length ([decisiongraph-complete/src/decisiongraph/aml_seed_generator.py](decisiongraph-complete/src/decisiongraph/aml_seed_generator.py#L73))
  - pep -> customer.pep ([decisiongraph-complete/src/decisiongraph/aml_seed_generator.py](decisiongraph-complete/src/decisiongraph/aml_seed_generator.py#L72))

- Truly missing from seeds:
  - None of the above. The mismatch is naming/normalization across layers, not absence in seed data.

## PART 2: FINGERPRINT SCHEMA INVENTORY (SUMMARY)

### Similarity component dimensions (scored)

Weights and evaluability come from the similarity scoring pipeline ([decisiongraph-complete/service/main.py](decisiongraph-complete/service/main.py#L1424-L1966)).

| Dimension | Maps to evidence field | Weight | Required for matching? |
|---|---|---|---|
| rules_overlap | reason_codes/exclusion_codes | 0.30 | yes |
| gate_match | gate1_allowed + gate2_str_required | 0.25 | yes |
| typology_overlap | reason codes -> typology tokens | 0.15 | no (optional) |
| amount_bucket | txn.amount_band | 0.10 | no (optional) |
| channel_method | txn.type | 0.07 | no (optional) |
| corridor_match | txn.cross_border or txn.destination_country_risk | 0.08 | no (optional) |
| pep_match | customer.pep | 0.05 | no (optional) |
| customer_profile | customer.type + customer.relationship_length | 0.05 | no (optional) |
| geo_risk | txn.destination_country_risk | 0.05 | no (optional) |

### Fingerprint schema definitions (hash-only dimensions)

All schema fields below are used to build fingerprint hashes and exact-match checks; they are not individually weighted in similarity scoring.

- Transaction schema fields: [decisiongraph-complete/src/decisiongraph/aml_fingerprint.py](decisiongraph-complete/src/decisiongraph/aml_fingerprint.py#L470-L540)
- KYC schema fields: [decisiongraph-complete/src/decisiongraph/aml_fingerprint.py](decisiongraph-complete/src/decisiongraph/aml_fingerprint.py#L544-L640)
- Reporting schema fields: [decisiongraph-complete/src/decisiongraph/aml_fingerprint.py](decisiongraph-complete/src/decisiongraph/aml_fingerprint.py#L656-L740)
- Screening schema fields: [decisiongraph-complete/src/decisiongraph/aml_fingerprint.py](decisiongraph-complete/src/decisiongraph/aml_fingerprint.py#L748-L820)
- Monitoring schema fields: [decisiongraph-complete/src/decisiongraph/aml_fingerprint.py](decisiongraph-complete/src/decisiongraph/aml_fingerprint.py#L860-L930)

## PART 3: REPORT EVIDENCE TABLE MAPPING

Evidence rendering is driven by `_EVIDENCE_SCOPE_LABELS` in [decisiongraph-complete/service/routers/report/render_md.py](decisiongraph-complete/service/routers/report/render_md.py#L309-L335).

| Field path shown | Scope/description shown | Description source | Description equals field path? |
|---|---|---|---|
| risk.high_risk_jurisdiction | Customer domicile jurisdiction risk | hardcoded map | no |
| txn.destination_country | Transaction destination jurisdiction | hardcoded map | no |
| txn.cross_border | Transaction cross-border indicator | hardcoded map | no |
| flag.cross_border | Cross-border flag (transaction-level) | hardcoded map | no |
| customer.type | Customer entity type | hardcoded map | no |
| customer.pep_flag | Customer PEP status | hardcoded map | no |
| flag.pep | PEP flag (customer-level) | hardcoded map | no |
| txn.amount_band | Transaction amount band | hardcoded map | no |
| txn.method | Payment method | hardcoded map | no |
| flag.structuring_suspected | Structuring indicator (transaction pattern) | hardcoded map | no |
| flag.sanctions_proximity | Sanctions screening proximity | hardcoded map | no |
| flag.adverse_media | Adverse media indicator | hardcoded map | no |
| flag.rapid_movement | Rapid fund movement indicator | hardcoded map | no |
| flag.shell_entity | Shell entity indicator | hardcoded map | no |
| risk.risk_score | Overall risk score | hardcoded map | no |
| facts.sanctions_result | facts.sanctions_result | default to field path | yes |
| facts.adverse_media_mltf | facts.adverse_media_mltf | default to field path | yes |
| suspicion.has_intent | suspicion.has_intent | default to field path | yes |
| suspicion.has_deception | suspicion.has_deception | default to field path | yes |
| suspicion.has_sustained_pattern | suspicion.has_sustained_pattern | default to field path | yes |
| obligations.count | obligations.count | default to field path | yes |
| mitigations.count | mitigations.count | default to field path | yes |
| typology.maturity | typology.maturity | default to field path | yes |
| indicator.<code> | indicator.<code> | default to field path | yes |

Fields with description == field path need human-readable labels.
