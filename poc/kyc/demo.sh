#!/bin/bash
# =============================================================================
# DecisionGraph KYC Onboarding POC Demo
# =============================================================================
#
# Demonstrates corporate KYC onboarding decision workflow:
#   Case 1: Clean onboarding (Sterling Designs Ltd) → should APPROVE
#   Case 2: Problem onboarding (Maple Horizons) → should BLOCK/ESCALATE
#
# Usage: ./demo.sh [clean|problem|both]
#
# =============================================================================

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
WHITE='\033[1;37m'
NC='\033[0m'

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"
DEMO_TYPE="${1:-both}"

print_header() {
    echo -e "${CYAN}"
    echo "╔══════════════════════════════════════════════════════════════════════╗"
    echo "║                  DecisionGraph KYC Onboarding POC                    ║"
    echo "╚══════════════════════════════════════════════════════════════════════╝"
    echo -e "${NC}"
}

print_case_header() {
    local case_id=$1
    local entity=$2
    local status=$3
    echo -e "${WHITE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${YELLOW}Case: $case_id${NC}"
    echo -e "Entity: $entity"
    echo -e "Expected: $status"
    echo -e "${WHITE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
}

run_case() {
    local bundle_path=$1
    local case_id=$2

    set +e
    "$ROOT_DIR/dg" run-case \
        --case "$bundle_path" \
        --pack "$ROOT_DIR/packs/fincrime_canada.yaml" \
        --out "$SCRIPT_DIR/output/" 2>&1 | grep -E "^\[|^  |Signals|Mitigations|Score|VERDICT|Entities|Events"
    local exit_code=$?
    set -e

    echo ""
    local manifest="$SCRIPT_DIR/output/$case_id/manifest.json"
    if [ -f "$manifest" ]; then
        local verdict=$(jq -r '.verdict' "$manifest")
        local inherent=$(jq -r '.score.inherent_score' "$manifest")
        local mits=$(jq -r '.score.mitigation_sum' "$manifest")
        local residual=$(jq -r '.score.residual_score' "$manifest")
        local signals=$(jq -r '.signals_fired' "$manifest")
        local mits_count=$(jq -r '.mitigations_applied' "$manifest")

        echo -e "${BLUE}┌────────────────────────────────────────────┐${NC}"
        echo -e "${BLUE}│${NC} ${WHITE}DECISION SUMMARY${NC}                          ${BLUE}│${NC}"
        echo -e "${BLUE}├────────────────────────────────────────────┤${NC}"
        printf "${BLUE}│${NC} %-20s %20s ${BLUE}│${NC}\n" "Verdict:" "${RED}$verdict${NC}"
        printf "${BLUE}│${NC} %-20s %20s ${BLUE}│${NC}\n" "Inherent Score:" "$inherent"
        printf "${BLUE}│${NC} %-20s %20s ${BLUE}│${NC}\n" "Mitigations:" "$mits"
        printf "${BLUE}│${NC} %-20s %20s ${BLUE}│${NC}\n" "Residual Score:" "$residual"
        printf "${BLUE}│${NC} %-20s %20s ${BLUE}│${NC}\n" "Signals Fired:" "$signals"
        printf "${BLUE}│${NC} %-20s %20s ${BLUE}│${NC}\n" "Mitigations Applied:" "$mits_count"
        echo -e "${BLUE}└────────────────────────────────────────────┘${NC}"
    fi
    return $exit_code
}

run_clean_case() {
    print_case_header "ACT-KYC-2026-0001" "Sterling Designs Ltd (BC)" "${GREEN}APPROVE${NC}"
    echo ""
    echo "Profile Summary:"
    echo "  • Established BC corporation (2018)"
    echo "  • Interior Design Services (NAICS 541410)"
    echo "  • 2 UBOs: Marcus Sterling (60%), Elena Kowalski (40%)"
    echo "  • All screening: CLEAR"
    echo "  • All IDV: PASS"
    echo "  • Documents: 8/8 complete"
    echo ""
    echo -e "${BLUE}Running decision engine...${NC}"
    echo ""
    run_case "$SCRIPT_DIR/mapped/ACT-KYC-2026-0001_bundle.json" "ACT-KYC-2026-0001"
}

run_problem_case() {
    print_case_header "CSV-KYC-2026-0001" "Maple Horizons Imports Inc (ON)" "${RED}BLOCK/ESCALATE${NC}"
    echo ""
    echo "Profile Summary:"
    echo "  • Newly incorporated ON company (Nov 2024)"
    echo "  • Food Merchant Wholesalers (NAICS 418410)"
    echo "  • 3 UBOs: Viktor Petrov (35%), Dmitri Volkov (40%), UNKNOWN (25%)"
    echo ""
    echo -e "${RED}Red Flags:${NC}"
    echo "  ❌ Sanctions: 2 POSSIBLE MATCHES pending"
    echo "  ❌ PEP: 1 POSSIBLE MATCH pending (Russia Regional)"
    echo "  ❌ Adverse Media: CONFIRMED hit"
    echo "  ❌ IDV Failed: Dmitri Volkov (expired doc, liveness fail)"
    echo "  ❌ UBO-103: Not identified (25% ownership)"
    echo "  ❌ Registry: Directors mismatch, address discrepancy"
    echo "  ❌ Documents: 5/8 incomplete"
    echo ""
    echo -e "${BLUE}Running decision engine...${NC}"
    echo ""
    run_case "$SCRIPT_DIR/mapped/CSV-KYC-2026-0001_bundle.json" "CSV-KYC-2026-0001"
}

print_summary_table() {
    echo ""
    echo -e "${WHITE}═══════════════════════════════════════════════════════════════════════${NC}"
    echo -e "${WHITE}SUMMARY TABLE${NC}"
    echo -e "${WHITE}═══════════════════════════════════════════════════════════════════════${NC}"
    echo ""
    printf "%-22s %-18s %-8s %-8s %-8s %-8s\n" "Case" "Verdict" "Gate" "Signals" "Mits" "Score"
    printf "%-22s %-18s %-8s %-8s %-8s %-8s\n" "----------------------" "------------------" "--------" "--------" "--------" "--------"

    for case_dir in "$SCRIPT_DIR/output"/*/; do
        if [ -f "$case_dir/manifest.json" ]; then
            local case_id=$(basename "$case_dir")
            local verdict=$(jq -r '.verdict' "$case_dir/manifest.json")
            local gate=$(jq -r '.score.threshold_gate' "$case_dir/manifest.json")
            local signals=$(jq -r '.signals_fired' "$case_dir/manifest.json")
            local mits=$(jq -r '.mitigations_applied' "$case_dir/manifest.json")
            local score=$(jq -r '.score.residual_score' "$case_dir/manifest.json")
            printf "%-22s %-18s %-8s %-8s %-8s %-8s\n" "$case_id" "$verdict" "$gate" "$signals" "$mits" "$score"
        fi
    done
    echo ""
}

print_footer() {
    echo -e "${CYAN}"
    echo "╔══════════════════════════════════════════════════════════════════════╗"
    echo "║                           Demo Complete                              ║"
    echo "╚══════════════════════════════════════════════════════════════════════╝"
    echo -e "${NC}"
    echo "Output bundles: $SCRIPT_DIR/output/"
    echo ""
    echo "Files per case:"
    echo "  manifest.json   - Scores, signals, mitigations"
    echo "  report.txt      - Human-readable report"
    echo "  cells.jsonl     - Complete decision chain"
    echo "  bundle.zip      - Signed bundle for audit"
    echo ""
}

# Main
mkdir -p "$SCRIPT_DIR/output"
print_header

case "$DEMO_TYPE" in
    clean)
        run_clean_case
        ;;
    problem)
        run_problem_case
        ;;
    both)
        run_clean_case
        echo ""
        run_problem_case
        print_summary_table
        ;;
    *)
        echo "Usage: $0 [clean|problem|both]"
        exit 1
        ;;
esac

print_footer
