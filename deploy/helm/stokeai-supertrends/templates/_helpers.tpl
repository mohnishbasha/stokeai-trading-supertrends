{{- /*
SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
Copyright 2026 Serverless Ventures LLC
*/ -}}
{{- define "st.fullname" -}}
{{- .Release.Name | trunc 53 | trimSuffix "-" -}}
{{- end -}}

{{- define "st.postgresName" -}}
{{ include "st.fullname" . }}-postgres
{{- end -}}

{{- define "st.labels" -}}
app.kubernetes.io/name: stokeai-supertrends
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
helm.sh/chart: {{ printf "%s-%s" .Chart.Name .Chart.Version | quote }}
{{- end -}}

{{- define "st.selector" -}}
app.kubernetes.io/name: stokeai-supertrends
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end -}}

{{/* Application image: a digest wins over the tag; global.imageRegistry prefixes it (air-gap). */}}
{{- define "st.image" -}}
{{- $registry := .Values.global.imageRegistry | default "" -}}
{{- $prefix := ternary (printf "%s/" (trimSuffix "/" $registry)) "" (ne $registry "") -}}
{{- if .Values.image.digest -}}
{{ $prefix }}{{ .Values.image.repository }}@{{ .Values.image.digest }}
{{- else -}}
{{ $prefix }}{{ .Values.image.repository }}:{{ .Values.image.tag | default .Chart.AppVersion }}
{{- end -}}
{{- end -}}

{{- define "st.postgresImage" -}}
{{- $registry := .Values.global.imageRegistry | default "" -}}
{{- $prefix := ternary (printf "%s/" (trimSuffix "/" $registry)) "" (ne $registry "") -}}
{{ $prefix }}{{ .Values.postgres.image.repository }}:{{ .Values.postgres.image.tag }}{{ if .Values.postgres.image.digest }}@{{ .Values.postgres.image.digest }}{{ end }}
{{- end -}}

{{/* The Secret the pods read: an existing one, or the one generated for the bundled Postgres. */}}
{{- define "st.secretName" -}}
{{- .Values.secrets.existingSecret | default (printf "%s-credentials" (include "st.fullname" .)) -}}
{{- end -}}

{{- define "st.generateSecret" -}}
{{- if and .Values.postgres.enabled (not .Values.secrets.existingSecret) -}}true{{- end -}}
{{- end -}}

{{- define "st.allowedHosts" -}}
{{- $n := include "st.fullname" . -}}
{{- $hosts := concat .Values.api.allowedHosts (list $n (printf "%s.%s" $n .Release.Namespace) (printf "%s.%s.svc" $n .Release.Namespace) (printf "%s.%s.svc.cluster.local" $n .Release.Namespace)) -}}
{{ join "," $hosts }}
{{- end -}}

{{/* Settings shared by every pod that runs the application image. */}}
{{- define "st.env" -}}
- name: SUPERTRENDS_ENV
  value: {{ .Values.env | quote }}
- name: SUPERTRENDS_MARKET_PROVIDER
  value: {{ .Values.providers.market | quote }}
- name: SUPERTRENDS_FUNDAMENTALS_PROVIDER
  value: {{ .Values.providers.fundamentals | quote }}
- name: SUPERTRENDS_MASSIVE_BASE_URL
  value: {{ .Values.providers.massiveBaseUrl | quote }}
- name: SUPERTRENDS_PROVIDER_RATE_PER_MIN
  value: {{ .Values.providers.ratePerMinute | quote }}
- name: SUPERTRENDS_NARRATIVE_PROVIDER
  value: {{ .Values.llm.narrativeProvider | quote }}
- name: SUPERTRENDS_LLM_TIMEOUT_SECONDS
  value: {{ .Values.llm.timeoutSeconds | quote }}
{{- if .Values.llm.baseUrl }}
- name: SUPERTRENDS_LLM_BASE_URL
  value: {{ .Values.llm.baseUrl | quote }}
{{- end }}
{{- if .Values.llm.model }}
- name: SUPERTRENDS_LLM_MODEL
  value: {{ .Values.llm.model | quote }}
{{- end }}
- name: SUPERTRENDS_ALLOWED_HOSTS
  value: {{ include "st.allowedHosts" . | quote }}
{{- end -}}

{{- define "st.envFrom" -}}
- secretRef:
    name: {{ include "st.secretName" . }}
{{- end -}}

{{- define "st.scheduling" -}}
{{- with .Values.nodeSelector }}
nodeSelector: {{ toYaml . | nindent 2 }}
{{- end }}
{{- with .Values.tolerations }}
tolerations: {{ toYaml . | nindent 2 }}
{{- end }}
{{- with .Values.affinity }}
affinity: {{ toYaml . | nindent 2 }}
{{- end }}
{{- end -}}
