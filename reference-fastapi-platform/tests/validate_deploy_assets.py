import json
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


def load_documents(path: Path):
    with path.open() as handle:
        return [document for document in yaml.safe_load_all(handle) if document]


def main() -> None:
    compose = yaml.safe_load((ROOT / "docker-compose.yml").read_text())
    required_services = {"postgres", "redis", "api", "worker", "alertmanager", "prometheus", "grafana"}
    assert required_services.issubset(compose["services"]), "Compose stack is missing required services"
    assert "private_uploads" in compose["volumes"], "Compose stack must use private upload storage"
    assert "redis_data" in compose["volumes"], "Compose stack is missing Redis data storage"
    assert "alertmanager_data" in compose["volumes"], "Compose stack is missing Alertmanager state storage"

    manifest_dir = ROOT / "deploy" / "kubernetes"
    resources = []
    for filename in ("00-foundation.yaml", "01-postgres.yaml", "02-api-worker.yaml", "03-edge-and-scaling.yaml", "05-redis.yaml", "06-alertmanager.yaml"):
        resources.extend(load_documents(manifest_dir / filename))
    kinds = {(item["kind"], item["metadata"]["name"]) for item in resources}
    expected = {
        ("Namespace", "synth-now"),
        ("StatefulSet", "synth-now-postgres"),
        ("Deployment", "synth-now-api"),
        ("Deployment", "synth-now-worker"),
        ("Service", "synth-now-api"),
        ("Ingress", "synth-now-api"),
        ("HorizontalPodAutoscaler", "synth-now-api"),
        ("HorizontalPodAutoscaler", "synth-now-worker"),
        ("PodDisruptionBudget", "synth-now-worker"),
        ("Service", "synth-now-worker-metrics"),
        ("StatefulSet", "synth-now-redis"),
        ("Deployment", "synth-now-alertmanager"),
        ("Service", "synth-now-alertmanager"),
    }
    assert expected.issubset(kinds), "Kubernetes package is missing required resources"

    kustomization = yaml.safe_load((manifest_dir / "kustomization.yaml").read_text())
    generated_files = {entry for generator in kustomization["configMapGenerator"] for entry in generator["files"]}
    assert "migrations/001_preset_ingestion_and_audio_vectors.sql" in generated_files
    assert "alertmanager/alertmanager.yml" in generated_files
    assert "alertmanager/pagerduty.tmpl" in generated_files
    assert (manifest_dir / "migrations" / "001_preset_ingestion_and_audio_vectors.sql").exists()

    dockerfile = (ROOT / "Dockerfile").read_text()
    assert "USER synthnow" in dockerfile
    assert "uvicorn" in dockerfile

    monitoring = ROOT / "deploy" / "monitoring"
    alerts_text = (monitoring / "alerts.yml").read_text()
    assert "synthnow_vector_search_duration_seconds" in alerts_text
    assert "SynthNowVectorSearchLatencyCritical" in alerts_text
    assert "SynthNowAudioQueueCritical" in alerts_text
    alertmanager_text = (monitoring / "alertmanager" / "alertmanager.yml").read_text()
    assert "pagerduty-critical-routing-key" in alertmanager_text
    assert "severity=\"critical\"" in alertmanager_text
    alertmanager = yaml.safe_load(alertmanager_text)
    receiver_names = {receiver["name"] for receiver in alertmanager["receivers"]}
    assert {"pagerduty-critical", "pagerduty-warning"}.issubset(receiver_names)
    assert any("severity=\"critical\"" in matcher for route in alertmanager["route"]["routes"] for matcher in route["matchers"])
    dashboard = json.loads((monitoring / "grafana" / "dashboards" / "synth-now-operations.json").read_text())
    assert dashboard["uid"] == "synth-now-operations"
    assert len(dashboard["panels"]) >= 6
    worker_monitor_text = (manifest_dir / "04-monitoring-operator.yaml").read_text()
    assert "synth-now-worker" in worker_monitor_text
    adapter_rules = (manifest_dir / "prometheus-adapter-rules.yaml").read_text()
    assert "synthnow_api_rps" in adapter_rules
    assert "synthnow_audio_job_queue_depth" in adapter_rules
    assert (ROOT / "docs" / "surge_autoscaling.md").exists()
    assert (ROOT / "docs" / "disaster_recovery_multi_region.md").exists()

    workflows = ROOT / ".github" / "workflows"
    for workflow_name in ("ci.yml", "release-image.yml", "deploy-kubernetes.yml"):
        workflow_text = (workflows / workflow_name).read_text()
        assert "permissions:" in workflow_text
    assert "PYTHONPATH=.:sdk pytest -q" in (workflows / "ci.yml").read_text()
    assert "dry_run" in (workflows / "deploy-kubernetes.yml").read_text()
    print("Deployment, monitoring, and CI asset structural validation passed")


if __name__ == "__main__":
    main()
