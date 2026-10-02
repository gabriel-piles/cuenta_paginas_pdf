formatter:
	. .venv/bin/activate; command black --line-length 125 .

# Dynamic version: vYYYY.DDD.R where DDD = day-of-year, R = tag revision for
# that year+day (0, 1, 2, ...) — e.g. v2026.275.0.
tag:
	#!/usr/bin/env bash
	set -euo pipefail
	year=$(date +%Y)
	day=$(date +%j)
	rev=0
	while git rev-parse -q --verify "refs/tags/v${year}.${day}.${rev}" >/dev/null 2>&1; do
		rev=$((rev + 1))
	done
	tag="v${year}.${day}.${rev}"
	git tag "${tag}"
	git push origin "${tag}"