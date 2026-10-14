#!/usr/bin/env bash
# Shallow checkout of REF (a branch, tag or commit SHA) of a git repository.
#   git-checkout.sh <url> <ref> <dir>
# (git clone -b cannot take a commit SHA, which CI uses to pin what "latest" means.)
set -euo pipefail
URL="${1:?url}"; REF="${2:?ref}"; DIR="${3:?dir}"
mkdir -p "${DIR}"
git -C "${DIR}" init -q
git -C "${DIR}" remote add origin "${URL}"
git -C "${DIR}" fetch -q --depth 1 origin "${REF}"
git -C "${DIR}" checkout -q FETCH_HEAD
