# Terratest, CI, and Incident Response Research Notes

Terratest is a Go library for infrastructure testing with first-class Terraform/AWS support. Its documented pattern is to write `_test.go` tests, deploy test infrastructure using Terraform, validate real resources, and undeploy after the test. Synth Now uses this only against an isolated staging account, uniquely named resources, a dedicated state prefix, a controlled allow-destroy flag, and a mandatory cleanup defer. Source: https://terratest.gruntwork.io/

GitHub Actions OIDC can exchange workflow identity for short-lived cloud credentials instead of storing long-lived cloud credentials as repository secrets. The AWS trust policy must match the approved workflow/repository/environment claims, and the workflow requests `id-token: write` only in jobs that use OIDC. Source: https://docs.github.com/en/actions/concepts/security/openid-connect

NIST SP 800-61 Rev. 3, published April 2025, recommends incorporating incident response into cybersecurity risk management to improve preparation, detection, response, and recovery. The Synth Now incident runbook therefore includes readiness, triage, containment, eradication/recovery, communication, evidence handling, post-incident improvement, and recurring exercises. Source: https://csrc.nist.gov/pubs/sp/800/61/r3/final
