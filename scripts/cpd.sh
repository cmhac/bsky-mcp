#!/usr/bin/env bash
# Copy/paste detection with PMD CPD. Fails on duplicated blocks of 50 or more tokens.
# Downloads a pinned PMD release into .pmd/ on first run and verifies its checksum.
set -euo pipefail

PMD_VERSION="7.28.0"
PMD_SHA256="f974ba571f7bc01c73fffe11bade25fbc1f438698f9e9c00e416e8d65e9fbac2"
MIN_TOKENS="50"

repo_root="$(git rev-parse --show-toplevel)"
cache_dir="${repo_root}/.pmd"
pmd_home="${cache_dir}/pmd-bin-${PMD_VERSION}"
zip_path="${cache_dir}/pmd-dist-${PMD_VERSION}-bin.zip"
url="https://github.com/pmd/pmd/releases/download/pmd_releases%2F${PMD_VERSION}/pmd-dist-${PMD_VERSION}-bin.zip"

if ! command -v java >/dev/null 2>&1; then
  echo "cpd: Java is required (17 or newer). Install a JDK and retry." >&2
  exit 2
fi

if [[ ! -x "${pmd_home}/bin/pmd" ]]; then
  mkdir -p "${cache_dir}"
  echo "cpd: downloading PMD ${PMD_VERSION}" >&2
  curl -fsSL -o "${zip_path}" "${url}"
  actual="$(sha256sum "${zip_path}" | awk '{print $1}')"
  if [[ "${actual}" != "${PMD_SHA256}" ]]; then
    echo "cpd: checksum mismatch for ${zip_path} (got ${actual})" >&2
    rm -f "${zip_path}"
    exit 2
  fi
  unzip -q -o "${zip_path}" -d "${cache_dir}"
  rm -f "${zip_path}"
fi

dirs=()
for d in src tests scripts; do
  if [[ -d "${repo_root}/${d}" ]]; then
    dirs+=(--dir "${repo_root}/${d}")
  fi
done

exec "${pmd_home}/bin/pmd" cpd \
  --minimum-tokens "${MIN_TOKENS}" \
  --language python \
  "${dirs[@]}"
