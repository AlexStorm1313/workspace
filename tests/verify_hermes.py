#!/usr/bin/env python3
"""Render/lint and test disposable Hermes/nginx containers; never deploy workspace.

Requires Python/PyYAML, Podman and cached alpine/helm, nginx and localhost/core.
No host mounts, host ports, external network, or existing container changes.
"""
import io
from pathlib import Path
import subprocess
import tarfile
import uuid

import yaml


ROOT = Path(__file__).resolve().parents[1]


def podman(*args, data=None):
    result = subprocess.run(
        ["podman", *args], input=data, stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if result.returncode:
        print(result.stderr.decode())
        result.check_returncode()
    return result.stdout + result.stderr if args[0] == "logs" else result.stdout


def archive(files):
    stream = io.BytesIO()
    with tarfile.open(fileobj=stream, mode="w") as tar:
        for name, content in files.items():
            entry = tarfile.TarInfo(name)
            entry.size = len(content)
            tar.addfile(entry, io.BytesIO(content))
    return stream.getvalue()


def render(*options):
    chart = ROOT / "infrastructure"
    files = {
        "chart/" + str(p.relative_to(chart)): p.read_bytes()
        for p in chart.rglob("*") if p.is_file()
        and p.name not in {"kube.yaml", "kube.yaml.tmp"}
    }
    command = 'mkdir /tmp/chart && tar -xf - -C /tmp && helm lint /tmp/chart >&2 && helm template workspace /tmp/chart "$@"'
    output = podman(
        "run", "--rm", "--pull=never", "--network=none", "-i",
        "--entrypoint", "sh", "docker.io/alpine/helm:latest", "-ec", command,
        "sh", *options, data=archive(files),
    )
    return [doc for doc in yaml.safe_load_all(output) if doc]


def main():
    docs = render()
    resources = {(d["kind"], d["metadata"]["name"]): d for d in docs}
    spec = resources["Deployment", "workspace-hermes"]["spec"]["template"]["spec"]
    containers = {c["name"]: c for c in spec["containers"]}
    assert containers["dashboard"]["args"] == [
        "hermes", "dashboard", "--host", "127.0.0.1", "--port", "9119", "--no-open",
    ]
    assert containers["gateway"]["args"] == ["hermes", "gateway", "run"]
    proxy = containers["dashboard-proxy"]
    assert proxy["securityContext"] == {"runAsNonRoot": False, "runAsUser": 0, "runAsGroup": 0}
    assert proxy["volumeMounts"][0]["subPath"] == "nginx.conf"
    assert proxy["volumeMounts"][0]["readOnly"] is True
    volume = next(v for v in spec["volumes"] if v["name"] == proxy["volumeMounts"][0]["name"])
    assert not volume["configMap"].get("optional", False)
    config = resources["ConfigMap", volume["configMap"]["name"]]["data"]["nginx.conf"]
    ports = resources["Deployment", "workspace-gateway"]["spec"]["template"]["spec"]["containers"][0]["ports"]
    assert all(p["hostIP"] == "127.0.0.1" for p in ports)
    route = resources["ConfigMap", "workspace-gateway-templates"]["data"]["hermes.conf.template"]
    assert "workspace-hermes-pod:9120" in route
    assert "access_log off;" in route
    disabled = render("--set", "services.hermes.enabled=false")
    assert not any(d["metadata"]["name"] == "workspace-hermes" for d in disabled)
    print("PASS: Helm lint/render, loopback publishing, sidecar wiring, disabled service")

    suffix = uuid.uuid4().hex[:10]
    backend, nginx = "hermes-test-" + suffix, "hermes-nginx-test-" + suffix
    created = []
    try:
        podman(
            "run", "-d", "--pull=never", "--name", backend, "--network=none",
            "--entrypoint", "hermes",
            containers["dashboard"]["image"], "dashboard", "--host", "127.0.0.1",
            "--port", "9119", "--no-open",
        )
        created.append(backend)
        podman("create", "--pull=never", "--user", "0:0", "--name", nginx, "--network=container:" + backend,
               proxy["image"])
        created.append(nginx)
        podman("cp", "-", nginx + ":/etc/nginx/conf.d",
               data=archive({"default.conf": config.encode()}))
        podman("start", nginx)
        podman("exec", nginx, "nginx", "-t")
        # Exercise the real installed dashboard with browser-style requests.
        checks = r'''
import base64, http.client, os, re, socket, time
HOST = "hermes.workspace.localhost:8443"
ORIGIN = "https://" + HOST
def request(path, headers=None):
    c = http.client.HTTPConnection("127.0.0.1", 9120, timeout=10)
    c.request("GET", path, headers={"Host": HOST, **(headers or {})})
    r = c.getresponse()
    result = r.status, r.read().decode()
    c.close()
    return result
for _ in range(90):
    try:
        status, html = request("/")
        if status == 200:
            break
    except OSError:
        pass
    time.sleep(1)
else:
    raise AssertionError("dashboard did not become ready")
token = re.search(r'window\.__HERMES_SESSION_TOKEN__\s*=\s*"([^"]+)"', html).group(1)
assert request("/", {"Host": "evil.example"})[0] == 403
assert request("/", {"Origin": "https://evil.example"})[0] == 403
assert request("/", {"Origin": "null"})[0] == 403
assert request("/", {"Origin": ORIGIN})[0] == 200
assert request("/api/sessions")[0] == 401
assert request("/api/sessions", {"X-Hermes-Session-Token": "wrong"})[0] == 401
assert request("/api/sessions", {"Origin": ORIGIN, "X-Hermes-Session-Token": token})[0] == 200
def ws(token, origin=ORIGIN):
    s = socket.create_connection(("127.0.0.1", 9120), timeout=10)
    headers = ["GET /api/ws?token=" + token + " HTTP/1.1", "Host: " + HOST,
               "Connection: Upgrade", "Upgrade: websocket", "Sec-WebSocket-Version: 13",
               "Sec-WebSocket-Key: " + base64.b64encode(os.urandom(16)).decode()]
    if origin is not None:
        headers.append("Origin: " + origin)
    s.sendall(("\r\n".join(headers) + "\r\n\r\n").encode())
    response = s.recv(4096).split(b"\r\n", 1)[0]
    s.close()
    return response
assert b"101" in ws(token), "valid browser WebSocket rejected"
assert b"403" in ws("wrong"), "invalid WS token accepted"
assert b"403" in ws(token, "https://evil.example"), "foreign WS Origin accepted"
assert b"403" in ws(token, None), "originless WS accepted"
print("PASS: real Hermes HTML/token, HTTP API auth, Host/Origin rejection, browser WebSocket auth")
'''
        print(podman("exec", "-i", backend, "python3", "-", data=checks.encode()).decode().strip())
    except Exception:
        for name in created:
            print(podman("logs", name).decode())
        raise
    finally:
        for name in reversed(created):
            podman("rm", "-f", name)


if __name__ == "__main__":
    main()
