#!/usr/bin/env bash
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright 2026 Serverless Ventures LLC
# Read-only inventory of the Stoke cluster for the Stoke profile.
# Uses only "kubectl get" and "flux get". Writes private/STOKE_INVENTORY.md, which is
# git-ignored: it describes a real cluster and must never be committed.
# Usage: scripts/stoke-inventory.sh [OUTPUT]   (honors KUBECONFIG; default output above)
set -euo pipefail
cd "$(dirname "$0")/.."

OUT="${1:-private/STOKE_INVENTORY.md}"
UNKNOWN="UNKNOWN: run against the cluster"
mkdir -p "$(dirname "$OUT")"

have_cluster() {
  command -v kubectl > /dev/null 2>&1 || return 1
  local cfg="${KUBECONFIG:-$HOME/.kube/config}"
  [[ -n "$cfg" && -f "${cfg%%:*}" ]] || return 1
  kubectl get --raw /version --request-timeout=5s > /dev/null 2>&1
}

kget() {
  kubectl get "$@" --request-timeout=10s 2> /dev/null || true
}

# Each check prints "found|class" where class is one of REUSE, UPGRADE, INSTALL, NOT NEEDED.
check_kubernetes() {
  local v arch
  v="$(kget --raw /version | jq -r '.gitVersion // empty' 2> /dev/null || true)"
  arch="$(kget nodes -o jsonpath='{.items[*].status.nodeInfo.architecture}' | tr ' ' '\n' | sort -u | tr '\n' ' ')"
  if [[ -n "$v" ]]; then echo "$v, arch: ${arch:-unknown}|REUSE"; else echo "not reachable|INSTALL"; fi
}

check_flux() {
  local controllers
  controllers="$(kget deploy -n flux-system -o name | sed 's|.*/||' | tr '\n' ' ')"
  if [[ -z "$controllers" ]]; then echo "flux-system not found|INSTALL"; return; fi
  if command -v flux > /dev/null 2>&1; then
    flux get sources oci -A > /dev/null 2>&1 || true
  fi
  if [[ "$controllers" == *source-controller* && "$controllers" == *helm-controller* && "$controllers" == *kustomize-controller* ]]; then
    echo "$controllers|REUSE"
  else
    echo "partial: $controllers|UPGRADE"
  fi
}

check_llm_gateway() {
  local svc
  svc="$(kget svc -A -o json | jq -r '.items[] | select(.metadata.name | test("aibrix|gateway|vllm|llm"; "i")) | "\(.metadata.name).\(.metadata.namespace).svc:\(.spec.ports[0].port)"' | head -n 3 | tr '\n' ' ')"
  if [[ -n "$svc" ]]; then
    echo "candidate services: $svc(list served models from the gateway /v1/models by hand)|REUSE"
  else
    echo "no gateway service found|INSTALL"
  fi
}

check_prometheus() {
  if kget crd servicemonitors.monitoring.coreos.com -o name | grep -q .; then
    echo "ServiceMonitor CRD present|REUSE"
  else
    echo "monitoring.coreos.com CRDs missing|INSTALL"
  fi
}

check_storage() {
  local classes
  classes="$(kget storageclass -o json | jq -r '.items[] | .metadata.name + (if .metadata.annotations["storageclass.kubernetes.io/is-default-class"] == "true" then " (default)" else "" end)' | tr '\n' ' ')"
  if [[ -n "$classes" ]]; then echo "$classes|REUSE"; else echo "no storage class|INSTALL"; fi
}

check_ingress() {
  local found
  found="$(kget ingressclass -o name | sed 's|.*/||' | tr '\n' ' ')"
  if kget deploy -A -o name | grep -qi tailscale; then found="${found}tailscale"; fi
  if [[ -n "$found" ]]; then echo "$found|REUSE"; else echo "no ingress class or tailscale operator|INSTALL"; fi
}

check_secrets() {
  local found=""
  if kget crd externalsecrets.external-secrets.io -o name | grep -q .; then found="External Secrets "; fi
  if kget deploy -A -o name | grep -qi sops; then found="${found}SOPS "; fi
  if kget kustomizations.kustomize.toolkit.fluxcd.io -A -o json | jq -e '[.items[].spec.decryption // empty] | length > 0' > /dev/null 2>&1; then
    found="${found}Flux SOPS decryption"
  fi
  if [[ -n "$found" ]]; then echo "$found|REUSE"; else echo "none found: plain Secrets created by the owner|NOT NEEDED"; fi
}

check_netpol() {
  local cni
  cni="$(kget pods -n kube-system -o name | grep -Eio 'calico|cilium|flannel|canal|weave' | sort -u | tr '\n' ' ')"
  case "$cni" in
    *calico* | *cilium* | *canal*) echo "CNI: $cni(enforces NetworkPolicy)|REUSE" ;;
    *) echo "CNI: ${cni:-unknown} (k3s embeds a NetworkPolicy controller unless disabled; verify)|REUSE" ;;
  esac
}

check_postgres_operator() {
  local op
  op="$(kget crd -o name | grep -Eio 'postgres[a-z.-]*|cnpg[a-z.-]*' | sort -u | tr '\n' ' ')"
  echo "${op:-none}|NOT NEEDED"
}

check_gpu() {
  local found
  found="$(kget crd -o name | grep -Eio 'nvidia[a-z.-]*|ray\.io' | sort -u | tr '\n' ' ')"
  echo "${found:-none}|NOT NEEDED"
}

ROWS=(
  "Kubernetes (k3s, ARM64)|a namespace|check_kubernetes"
  "Flux v2 (source, helm, kustomize controllers)|OCIRepository, HelmRelease, Kustomization|check_flux"
  "LLM gateway in front of vLLM (AIBrix)|an OpenAI-compatible base URL and a model name|check_llm_gateway"
  "kube-prometheus-stack|ServiceMonitor, PrometheusRule, dashboard ConfigMap|check_prometheus"
  "Storage class|a 10Gi PVC for Postgres|check_storage"
  "Ingress or tailnet exposure|one HTTP route, private|check_ingress"
  "Secret management (SOPS or External Secrets)|2 Secrets per namespace|check_secrets"
  "NetworkPolicy enforcement|default deny plus allowances|check_netpol"
  "Postgres operator|none: the bundled StatefulSet is enough|check_postgres_operator"
  "GPU Operator, KubeRay|nothing|check_gpu"
)

connected=0
if have_cluster; then connected=1; fi

{
  echo "# Stoke Inventory"
  echo
  echo "Generated $(date -u +%Y-%m-%dT%H:%M:%SZ) by scripts/stoke-inventory.sh (read-only)."
  echo "PRIVATE: describes a real cluster. Never commit this file."
  echo
  echo "| Component | Found | Super Trends needs | Class |"
  echo "|---|---|---|---|"
  for row in "${ROWS[@]}"; do
    IFS='|' read -r component needs fn <<< "$row"
    if [[ "$connected" -eq 1 ]]; then
      IFS='|' read -r found class <<< "$("$fn")"
    else
      found="$UNKNOWN"
      class="$UNKNOWN"
    fi
    echo "| $component | $found | $needs | $class |"
  done
} > "$OUT"

if [[ "$connected" -eq 1 ]]; then
  echo "Wrote $OUT from the current kubeconfig context."
else
  echo "No reachable cluster (kubeconfig missing or unreachable). Wrote $OUT with every row UNKNOWN."
fi
