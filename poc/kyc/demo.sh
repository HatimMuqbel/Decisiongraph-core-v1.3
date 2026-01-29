#!/bin/bash
# =============================================================================
# DecisionGraph KYC POC Demo Script
# =============================================================================
#
# Usage: ./demo.sh [low|pep|corp|all]
#
# Demonstrates the KYC onboarding decision pipeline:
# 1. Load customer profile with screening and verification results
# 2. Run decision engine with Canadian FinCrime rules
# 3. Display risk assessment and verdict
#
# =============================================================================

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"

# Default to all demos
DEMO_TYPE="${1:-all}"

echo -e "${CYAN}"
echo "============================================================================"
echo "  DecisionGraph KYC Onboarding POC"
echo "============================================================================"
echo -e "${NC}"

# Function to display case summary
display_summary() {
    local CASE_DIR="$1"
    local CASE_NAME="$2"

    if [ -f "$CASE_DIR/manifest.json" ]; then
        VERDICT=$(jq -r '.verdict' "$CASE_DIR/manifest.json")
        INHERENT=$(jq -r '.score.inherent_score' "$CASE_DIR/manifest.json")
        MITIGATION=$(jq -r '.score.mitigation_sum' "$CASE_DIR/manifest.json")
        RESIDUAL=$(jq -r '.score.residual_score' "$CASE_DIR/manifest.json")
        SIGNALS=$(jq -r '.signals_fired' "$CASE_DIR/manifest.json")
        MITIGATIONS=$(jq -r '.mitigations_applied' "$CASE_DIR/manifest.json")

        echo -e "${GREEN}$CASE_NAME${NC}"
        echo -e "${YELLOW}Verdict: $VERDICT${NC}"
        echo "  Inherent Score:      $INHERENT"
        echo "  Mitigations:         $MITIGATION"
        echo "  Residual Score:      $RESIDUAL"
        echo "  Signals Fired:       $SIGNALS"
        echo "  Mitigations Applied: $MITIGATIONS"
    fi
}

# Function to run low-risk individual demo
run_low_risk_demo() {
    echo -e "${YELLOW}>>> Case 1: Low-Risk Individual Onboarding${NC}"
    echo ""
    echo "Customer: Michael Chen"
    echo "Profile:  Canadian, Software Engineer, No PEP status"
    echo "Risk:     Low"
    echo ""

    set +e
    "$ROOT_DIR/dg" run-case \
        --case "$SCRIPT_DIR/low_risk_bundle.json" \
        --pack "$ROOT_DIR/packs/fincrime_canada.yaml" \
        --out "$SCRIPT_DIR/output/" 2>&1 | grep -E "^\[|^  |Signals|Mitigations|Score|VERDICT"
    EXIT_CODE=$?
    set -e

    echo ""
    display_summary "$SCRIPT_DIR/output/KYC-2026-001" "KYC-2026-001"
    echo ""
}

# Function to run PEP demo
run_pep_demo() {
    echo -e "${YELLOW}>>> Case 2: Domestic PEP Onboarding${NC}"
    echo ""
    echo "Customer: Elizabeth Warren-Smith"
    echo "Profile:  Member of Parliament, Domestic PEP"
    echo "Risk:     High (requires EDD)"
    echo ""

    set +e
    "$ROOT_DIR/dg" run-case \
        --case "$SCRIPT_DIR/pep_bundle.json" \
        --pack "$ROOT_DIR/packs/fincrime_canada.yaml" \
        --out "$SCRIPT_DIR/output/" 2>&1 | grep -E "^\[|^  |Signals|Mitigations|Score|VERDICT"
    EXIT_CODE=$?
    set -e

    echo ""
    display_summary "$SCRIPT_DIR/output/KYC-2026-002" "KYC-2026-002"
    echo ""
}

# Function to run high-risk corporate demo
run_corp_demo() {
    echo -e "${YELLOW}>>> Case 3: High-Risk Corporate Onboarding${NC}"
    echo ""
    echo "Entity:   Global Trading Holdings Ltd"
    echo "Profile:  BVI company, Commodity Trading, Unknown UBO"
    echo "Risk:     Critical (multiple red flags)"
    echo ""

    set +e
    "$ROOT_DIR/dg" run-case \
        --case "$SCRIPT_DIR/high_risk_corp_bundle.json" \
        --pack "$ROOT_DIR/packs/fincrime_canada.yaml" \
        --out "$SCRIPT_DIR/output/" 2>&1 | grep -E "^\[|^  |Signals|Mitigations|Score|VERDICT"
    EXIT_CODE=$?
    set -e

    echo ""
    display_summary "$SCRIPT_DIR/output/KYC-2026-003" "KYC-2026-003"
    echo ""
}

# Create output directory
mkdir -p "$SCRIPT_DIR/output"

# Run demos based on argument
case "$DEMO_TYPE" in
    low)
        run_low_risk_demo
        ;;
    pep)
        run_pep_demo
        ;;
    corp)
        run_corp_demo
        ;;
    all)
        run_low_risk_demo
        echo -e "${CYAN}------------------------------------------------------------${NC}"
        echo ""
        run_pep_demo
        echo -e "${CYAN}------------------------------------------------------------${NC}"
        echo ""
        run_corp_demo
        ;;
    *)
        echo "Usage: $0 [low|pep|corp|all]"
        exit 1
        ;;
esac

echo -e "${CYAN}"
echo "============================================================================"
echo "  KYC POC Demo Complete"
echo "============================================================================"
echo -e "${NC}"
echo "Output bundles: $SCRIPT_DIR/output/"
echo ""
echo "Key files per case:"
echo "  - manifest.json   : Risk scores, signals, mitigations"
echo "  - report.txt      : Human-readable assessment"
echo "  - cells.jsonl     : Complete decision chain"
echo "  - bundle.zip      : Signed bundle for audit"
echo ""
