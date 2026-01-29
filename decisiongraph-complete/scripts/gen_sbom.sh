#!/bin/bash
#
# DecisionGraph: SBOM Generator
#
# Generates Software Bill of Materials in SPDX format.
# Requires: pip-licenses, spdx-tools (optional)
#
# Usage:
#   ./scripts/gen_sbom.sh
#   ./scripts/gen_sbom.sh --output release/SBOM.spdx.json
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"
OUTPUT_DIR="${REPO_ROOT}/release"
OUTPUT_FILE="${OUTPUT_DIR}/SBOM.spdx.json"

# Parse args
while [[ $# -gt 0 ]]; do
    case $1 in
        --output)
            OUTPUT_FILE="$2"
            shift 2
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

mkdir -p "$(dirname "$OUTPUT_FILE")"

echo "Generating SBOM for DecisionGraph..."
echo "Output: ${OUTPUT_FILE}"

# Check if pip-licenses is available
if ! command -v pip-licenses &> /dev/null; then
    echo "Installing pip-licenses..."
    pip install pip-licenses --quiet
fi

# Get package info
VERSION=$(python -c "from src.decisiongraph.decision_pack import ENGINE_VERSION; print(ENGINE_VERSION)" 2>/dev/null || echo "2.1.1")
TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
COMMIT=$(git rev-parse HEAD 2>/dev/null || echo "unknown")

# Generate licenses list
LICENSES=$(pip-licenses --format=json 2>/dev/null || echo "[]")

# Build SPDX-lite JSON
cat > "$OUTPUT_FILE" << EOF
{
  "spdxVersion": "SPDX-2.3",
  "dataLicense": "CC0-1.0",
  "SPDXID": "SPDXRef-DOCUMENT",
  "name": "DecisionGraph-SBOM",
  "documentNamespace": "https://decisiongraph.io/sbom/${VERSION}",
  "creationInfo": {
    "created": "${TIMESTAMP}",
    "creators": [
      "Tool: gen_sbom.sh",
      "Organization: DecisionGraph"
    ],
    "licenseListVersion": "3.19"
  },
  "packages": [
    {
      "SPDXID": "SPDXRef-Package-decisiongraph",
      "name": "decisiongraph",
      "versionInfo": "${VERSION}",
      "downloadLocation": "https://github.com/decisiongraph/core",
      "filesAnalyzed": false,
      "licenseConcluded": "NOASSERTION",
      "licenseDeclared": "NOASSERTION",
      "copyrightText": "NOASSERTION",
      "comment": "AML/KYC Decision Engine"
    }
  ],
  "relationships": [
    {
      "spdxElementId": "SPDXRef-DOCUMENT",
      "relatedSpdxElement": "SPDXRef-Package-decisiongraph",
      "relationshipType": "DESCRIBES"
    }
  ],
  "_metadata": {
    "generator": "gen_sbom.sh",
    "commit": "${COMMIT}",
    "dependencies": ${LICENSES}
  }
}
EOF

echo "SBOM generated: ${OUTPUT_FILE}"
echo "  Version: ${VERSION}"
echo "  Commit:  ${COMMIT}"
