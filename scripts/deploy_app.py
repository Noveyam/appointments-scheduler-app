"""Deploy this CodeBuild source revision using concrete application manifests."""

import ipaddress
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile


ACCOUNT = "766158721264"
REGION = "us-east-1"
REPOSITORY = "containers-image-repository"
NAMESPACE = "default"
ROOT = Path(__file__).resolve().parents[1]
MANIFESTS = (
    ("appointments-deployment.yml", "Deployment", "appointments-deployment"),
    ("appointments-service.yml", "Service", "appointments-service"),
    ("appointments-ingress.yml", "Ingress", "appointments-ingress"),
)


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def read_json(*command):
    output = subprocess.check_output(command, text=True, timeout=45)
    return json.loads(output)


def aws(*arguments):
    return read_json(
        "aws", *arguments, "--region", REGION, "--output", "json",
        "--cli-connect-timeout", "10", "--cli-read-timeout", "30",
    )


def kube(*arguments, request_timeout="30s"):
    return [
        "kubectl", "--kubeconfig", os.environ["KUBECONFIG"],
        "--namespace", NAMESPACE, f"--request-timeout={request_timeout}",
        *map(str, arguments),
    ]


def render_manifests(directory, image, dns, cidr):
    """Validate all three rendered objects before any apply operation."""
    replacements = {"__LOAD_BALANCER_DNS__": dns, "__CLIENT_CIDR__": cidr}
    for filename, kind, name in MANIFESTS:
        text = (ROOT / "manifests" / filename).read_text()
        if kind == "Deployment":
            require(text.count("__LOAD_BALANCER_DNS__") == 1,
                    "Deployment must contain one ALB hostname marker.")
            text, count = re.subn(
                r'(?m)^(\s+image:\s*)"[^"\n]+@__IMAGE_DIGEST__"$',
                lambda match: f'{match[1]}"{image}"', text,
            )
            require(count == 1, "Deployment must contain one image marker.")
        if kind == "Ingress":
            require(text.count("__CLIENT_CIDR__") == 1,
                    "Ingress must contain one client CIDR marker.")
        for marker, value in replacements.items():
            text = text.replace(marker, value)
        require(not re.search(r"__[A-Z0-9_]+__", text),
                f"Unresolved marker in {filename}.")
        path = directory / filename
        path.write_text(text)
        obj = read_json(*kube(
            "create", "--dry-run=client", "--validate=false",
            "-f", path, "-o", "json",
        ))
        metadata = obj["metadata"]
        require(
            (obj["kind"], metadata["name"], metadata.get("namespace", NAMESPACE))
            == (kind, name, NAMESPACE),
            f"Unexpected resource identity in {filename}.",
        )
        if kind == "Deployment":
            pod_spec = obj["spec"]["template"]["spec"]
            containers = pod_spec["containers"]
            require(len(containers) == 1 and containers[0]["name"] == "appointments",
                    "Expected only the appointments container.")
            container = containers[0]
            env = {item["name"]: item for item in container["env"]}
            require(container["image"] == image, "Rendered image mismatch.")
            require(pod_spec["serviceAccountName"] == "appointments-sa",
                    "Application service account must be preserved.")
            require(pod_spec["nodeSelector"]["kubernetes.io/arch"] == "amd64",
                    "The image requires amd64 workers.")
            require(env["POD_IP"]["valueFrom"]["fieldRef"]["fieldPath"] == "status.podIP",
                    "POD_IP health-check host support must be preserved.")
            require(
                env["DJANGO_ALLOWED_HOSTS"]["value"]
                == f"localhost,127.0.0.1,$(POD_IP),{dns}",
                "Rendered allowed hosts mismatch.",
            )
        if kind == "Service":
            require(obj["spec"]["type"] == "NodePort", "Service must remain NodePort.")
        if kind == "Ingress":
            require(
                metadata["annotations"]["alb.ingress.kubernetes.io/inbound-cidrs"]
                == cidr,
                "Rendered Ingress must preserve the existing client CIDR.",
            )


def main():
    require(os.environ.get("CODEBUILD_BUILD_ID", "").startswith("DeployPods:"),
            "Run this helper in the DeployPods CodeBuild project.")
    require(os.environ.get("AWS_DEFAULT_REGION") == REGION, "Unexpected build region.")
    require(bool(os.environ.get("KUBECONFIG")), "An explicit build kubeconfig is required.")
    revision = os.environ.get("CODEBUILD_RESOLVED_SOURCE_VERSION", "")
    require(re.fullmatch(r"[0-9a-f]{40}", revision), "A full source commit SHA is required.")
    require(aws("sts", "get-caller-identity")["Account"] == ACCOUNT,
            "Unexpected AWS account.")
    details = aws(
        "ecr", "describe-images", "--repository-name", REPOSITORY,
        "--image-ids", f"imageTag={revision}",
    )["imageDetails"]
    require(len(details) == 1, "Expected exactly one source-SHA image.")
    detail = details[0]
    digest = detail["imageDigest"]
    require(re.fullmatch(r"sha256:[0-9a-f]{64}", digest), "Invalid image digest.")
    require(detail.get("imageManifestMediaType") in {
        "application/vnd.docker.distribution.manifest.v2+json",
        "application/vnd.oci.image.manifest.v1+json",
    }, "Expected a single image manifest; review any image index before deployment.")
    image = f"{ACCOUNT}.dkr.ecr.{REGION}.amazonaws.com/{REPOSITORY}:{revision}@{digest}"
    ingress = read_json(*kube("get", "ingress", "appointments-ingress", "-o", "json"))
    addresses = ingress.get("status", {}).get("loadBalancer", {}).get("ingress", [])
    require(len(addresses) == 1 and "hostname" in addresses[0],
            "The existing application Ingress must have one ALB hostname.")
    dns = addresses[0]["hostname"]
    require(re.fullmatch(r"[a-z0-9-]+\.us-east-1\.elb\.amazonaws\.com", dns),
            "Unexpected ALB hostname.")
    cidr = ingress["metadata"]["annotations"]["alb.ingress.kubernetes.io/inbound-cidrs"]
    network = ipaddress.ip_network(cidr, strict=True)
    require(network.version == 4 and network.prefixlen == 32,
            "The existing client restriction must be one IPv4 /32.")
    print(f"Deploying source {revision}\nImage {image}", flush=True)
    with tempfile.TemporaryDirectory(prefix="deploypods-") as temporary:
        directory = Path(temporary)
        render_manifests(directory, image, dns, cidr)
        subprocess.run(kube("apply", "-f", directory), check=True, timeout=120)
    subprocess.run(
        kube("rollout", "status", "deployment/appointments-deployment",
             "--timeout=300s", request_timeout="330s"),
        check=True, timeout=345,
    )
    deployment = read_json(*kube("get", "deployment", "appointments-deployment", "-o", "json"))
    desired = deployment["spec"].get("replicas", 1)
    require(desired > 0 and deployment["status"].get("readyReplicas") == desired,
            "Deployment replicas are not ready.")
    require(deployment["spec"]["template"]["spec"]["containers"][0]["image"] == image,
            "Deployment no longer requests this build's image.")
    pods = read_json(*kube("get", "pods", "-l", "app=appointments", "-o", "json"))["items"]
    active = [pod for pod in pods if not pod["metadata"].get("deletionTimestamp")]
    require(len(active) == desired, "Unexpected number of active application pods.")
    for pod in active:
        require(any(c["type"] == "Ready" and c["status"] == "True"
                    for c in pod["status"].get("conditions", [])), "A pod is not Ready.")
        require(pod["spec"]["containers"][0]["image"] == image, "Pod image mismatch.")
        statuses = [c for c in pod["status"].get("containerStatuses", [])
                    if c["name"] == "appointments"]
        require(len(statuses) == 1 and statuses[0]["ready"], "Container is not ready.")
        image_id = statuses[0].get("imageID", "")
        require(image_id.endswith("@" + digest), "Running imageID digest mismatch.")
        print(f"{pod['metadata']['name']} {image_id}", flush=True)
    print(f"Verified source {revision}\nApplication URL: http://{dns}/", flush=True)


if __name__ == "__main__":
    main()
