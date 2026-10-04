from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent


def test_helm_chart_metadata() -> None:
    chart_path = REPO_ROOT / "deploy" / "helm" / "procore-mcp" / "Chart.yaml"
    assert chart_path.exists(), f"Missing {chart_path}"

    with open(chart_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    assert data.get("apiVersion") == "v2"
    assert data.get("name") == "procore-mcp"
    assert data.get("type") == "application"
    assert "version" in data
    assert "appVersion" in data


def test_helm_values_configuration() -> None:
    values_path = REPO_ROOT / "deploy" / "helm" / "procore-mcp" / "values.yaml"
    assert values_path.exists(), f"Missing {values_path}"

    with open(values_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    assert "image" in data
    assert data.get("service", {}).get("port") == 8000
    sec_ctx = data.get("podSecurityContext", {})
    assert sec_ctx.get("runAsNonRoot") is True
    assert sec_ctx.get("runAsUser") == 10001

    # Invariants for enterprise resource safety
    res = data.get("resources", {})
    assert "limits" in res
    assert "requests" in res


def test_helm_templates_exist() -> None:
    tpl_dir = REPO_ROOT / "deploy" / "helm" / "procore-mcp" / "templates"
    assert tpl_dir.exists()
    assert (tpl_dir / "deployment.yaml").exists()
    assert (tpl_dir / "service.yaml").exists()
    assert (tpl_dir / "pvc.yaml").exists()


def test_plain_k8s_manifests() -> None:
    k8s_dir = REPO_ROOT / "deploy" / "k8s"
    assert k8s_dir.exists()

    dep_file = k8s_dir / "deployment.yaml"
    svc_file = k8s_dir / "service.yaml"
    pvc_file = k8s_dir / "pvc.yaml"

    assert dep_file.exists()
    assert svc_file.exists()
    assert pvc_file.exists()

    with open(dep_file, "r", encoding="utf-8") as f:
        dep_data = yaml.safe_load(f)

    assert dep_data.get("apiVersion") == "apps/v1"
    assert dep_data.get("kind") == "Deployment"
    spec = dep_data.get("spec", {}).get("template", {}).get("spec", {})
    pod_sec = spec.get("securityContext", {})
    assert pod_sec.get("runAsNonRoot") is True
    assert pod_sec.get("runAsUser") == 10001

    containers = spec.get("containers", [])
    assert len(containers) >= 1
    c = containers[0]
    ports = [p.get("containerPort") for p in c.get("ports", [])]
    assert 8000 in ports

    # Verify audit persistence mount
    vmounts = [vm.get("mountPath") for vm in c.get("volumeMounts", [])]
    assert "/data" in vmounts


def test_helm_lint_and_template() -> None:
    import shutil
    import subprocess

    helm_bin = shutil.which("helm")
    if not helm_bin:
        pytest.skip("helm not installed in test environment")

    chart_dir = str(REPO_ROOT / "deploy" / "helm" / "procore-mcp")

    # Run helm lint
    lint_res = subprocess.run([helm_bin, "lint", chart_dir], capture_output=True, text=True)
    assert lint_res.returncode == 0, f"helm lint failed:\n{lint_res.stderr}\n{lint_res.stdout}"

    # Run helm template
    template_res = subprocess.run(
        [helm_bin, "template", "test-release", chart_dir], capture_output=True, text=True
    )
    fail_msg = f"helm template failed:\n{template_res.stderr}\n{template_res.stdout}"
    assert template_res.returncode == 0, fail_msg
    assert "kind: Deployment" in template_res.stdout
    assert "kind: Service" in template_res.stdout
    assert "kind: PersistentVolumeClaim" in template_res.stdout
