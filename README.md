# Workspace

A local, containerized development workspace. The Helm chart in
`infrastructure/` renders a Kubernetes manifest that Podman runs with
`podman kube play`.

The default configuration enables the shared gateway, OpenCode, Hermes, and
workspace server. Hermes uses a loopback-only dashboard behind a dedicated nginx
sidecar on the shared TLS edge.
Configure enabled services and their images in
`infrastructure/values.yaml`.

## Requirements

- Podman with rootless containers enabled
- `make`
- Git and GitHub SSH access to initialize the `containers/core` submodule
- Network access to pull container images
- A host development directory and the Podman and GCR SSH sockets expected by
  the OpenCode and VSCodium deployments

## First-Time Setup

Initialize the core image submodule:

```sh
git submodule update --init --recursive
```

Review `infrastructure/values.yaml` before rendering the chart. In particular,
replace the default `deployments.volumeMounts[0].mountPath` value with a
directory that exists on your host.

OpenCode and VSCodium also mount these host sockets:

```text
/run/user/1000/podman/podman.sock
/run/user/1000/gcr/ssh
```

Update the deployment templates or disable the affected services if those
paths do not apply to your system.

The gateway requires TLS files at:

```text
infrastructure/secrets/gateway/tls.crt
infrastructure/secrets/gateway/tls.key
```

They are intentionally untracked. `make workspace` / `make kube` automatically
generate a self-signed pair if neither file exists, preserving existing files.
An incomplete pair is an error rather than silently replacing a key. You can
also explicitly generate a pair directly where the chart expects it:

```sh
make certificate
```

## Usage

Render the Helm chart into `infrastructure/kube.yaml`:

```sh
make kube
```

Run or replace the locally rendered deployment:

```sh
make play
```

Stop any existing deployment, render the chart, and start it:

```sh
make workspace
```

Stop the deployment while preserving persistent volumes:

```sh
make down
```

Remove all Podman volumes whose names begin with `workspace-`:

```sh
make clean
```

The Makefile also provides `make mkcert` for a locally trusted certificate and
the configured Ungoogled Chromium NSS database (restart the browser afterward).

## Accessing Services

The gateway publishes HTTP on `127.0.0.1:8080` and HTTPS on `127.0.0.1:8443`
(IPv4 loopback only, not LAN/public interfaces). With the
default gateway configuration, enabled services are available over HTTPS at:

- `https://opencode.workspace.localhost:8443`
- `https://hermes.workspace.localhost:8443`
- `https://codium.workspace.localhost:8443`
- `https://redis-insight.workspace.localhost:8443`
- `https://scalar.workspace.localhost:8443` when Scalar is enabled and its
  deployment template has been corrected

## Configuration

### Hermes passwordless local dashboard

The shared gateway routes `hermes.workspace.localhost` to the Hermes pod's nginx
sidecar on port 9120, which proxies to `127.0.0.1:9119`. Hermes binds to loopback
for passwordless access. Leave `dashboard.public_url` and
`HERMES_DASHBOARD_PUBLIC_URL` unset; `--insecure` is not an authentication bypass.
No messaging permissions or provider credentials are changed by this setup.

The sidecar validates the original Host and same-origin browser Origin for
HTTP port 8080 / HTTPS port 8443 before translating them to loopback for Hermes's
Host and WebSocket checks. Missing Origins are allowed for ordinary HTTP, not
WebSocket upgrades. Session-token headers and WebSocket/download query tokens
are preserved, not synthesized. Access logging is disabled for this route at
both proxy hops to avoid recording query credentials. Uploads are limited to
100 MiB at the sidecar.

**Security boundary:** both shared gateway host ports are explicitly published
on IPv4 loopback, affecting all shared routes. Do not change these to wildcard
bindings or forward/tunnel the route to an untrusted network without adding
authentication. Host/Origin checks are not authentication: anyone able to fetch
the dashboard receives its session capability. The sidecar has no published host
port, but trusted pod-network peers can reach its unauthenticated port 9120.
The former Fedora/public Hermes hostnames are intentionally not supported.
Existing running resources are unchanged until you explicitly render/redeploy;
their current wildcard host bindings remain a risk until then.

Compatibility was checked against Hermes v0.22.2, commit
`d923a5eb487a17c0a68801bba9ef0f56c81040a8`. The core image installs mutable upstream
Hermes, so recheck proxy compatibility after upgrades. MCP OAuth callbacks that
derive a URL from the backend request may use `http://127.0.0.1:9119` and are not
made externally usable by this local dashboard proxy. Provider authentication
(including Nous credentials) remains separate from dashboard access.

Run `python3 tests/verify_hermes.py` to lint/render the chart (including disabled
Hermes), check sidecar wiring and loopback host publishing, validate nginx, and
exercise the installed dashboard's HTML, API tokens and WebSocket authentication
with browser-style Host/Origin headers. Requires Python 3, PyYAML, Podman and
cached Helm/nginx/core images. Tests use disposable containers with no external
network, host mounts or published ports and remove them afterward. They do not
deploy the manifest or test an actual browser, TLS trust, model responses or MCP
OAuth. The pre-existing OpenClaw notes below describe the former setup.

### OpenClaw networking (Podman)

The shared generic TLS edge routes OpenClaw traffic to
`workspace-openclaw-pod:8080`, where an nginx sidecar proxies to the gateway at
`127.0.0.1:18789`. The sidecar preserves the public `Host` and `Origin` while
dropping standard forwarding and identity headers, avoiding proxy attribution.
OpenClaw binds to loopback with `gateway.auth.mode: "none"`; no trusted proxies
or identity authentication are configured. There is no manual token or pairing
step. A fresh signed Control UI device completed the disposable WebSocket test
without token or pairing approval. Browser device identity in a secure HTTPS
context is still required; an actual browser session has not been tested.
With a generated self-signed certificate the browser needs the usual
local TLS exception; use `make mkcert` for a locally trusted certificate.
`openclaw.workspace.{localhost,fedora-workstation,alexbrasser.com}` are allowed
HTTPS origins on port 8443. The
existing localhost certificate does not cover the other two hostnames.
The former Codex callback hostname is not routed; provider login, if needed, is separate from
Gateway/browser authentication. The starting config contains only Gateway
settings: no model providers or agent defaults. Configure a provider/model
separately before using chat; UI access does not provision a model.
Machine-node enrollment and a separate MCP-app/widget sandbox origin are not
configured by this browser-access setup (the sandbox's port `18790` is not
proxied or published). Doctor reports these as optional setup warnings.

Both shared proxy host ports remain bound to loopback. No fixed IP or private
bridge is configured; existing live networks were not changed or deleted.
The sidecar has no host-published port, but pod-network peers can reach its
unauthenticated port 8080. Outer safeguards remain the operator's responsibility.

OpenClaw alone uses the official `ghcr.io/openclaw/openclaw:latest` image
rather than the core image. The locally inspected image reports 2026.10.4;
`latest` is mutable, not a version/digest pin.
The inspected core image contained OpenClaw 2026.9.2
on Node 22.23.1/system SQLite 3.51.2, which OpenClaw refuses for WAL safety.
The official entrypoint performs state migrations. The existing state volume and
`/home/core/.openclaw` path are retained via `OPENCLAW_STATE_DIR`. A separate
`workspace-openclaw-home` volume provides a writable home for UID 1001 and retains
the entrypoint's sibling `.openclaw.update-captures` migration backups; it does not
replace or relocate existing state. Core-image-only tools are not included in
this image. The single source of truth for the minimal inline `openclaw.json` is
`infrastructure/templates/configmaps/openclaw.yaml`. The init container runs as
UID 1001 / GID 0 and copies that seed only when
`/home/core/.openclaw/openclaw.json` is missing. Existing configuration, backups,
and health baselines are left untouched; no config-update script is required.
Edit the persistent config for an existing installation. Chart seed changes
apply only to fresh state, not on every startup. Do not force a smaller seed over
old configuration: OpenClaw's health recovery can restore an old backup.
`make workspace` re-renders, replaces pods, and re-executes the
initializer; `make play` alone uses the last rendered manifest.
Existing sessions, paired devices, credentials, and other state are not reset.
`make down` preserves volumes (no `--force`); `make clean` deletes them.

### Manually reset only OpenClaw state

**This permanently loses OpenClaw chats, credentials, model configuration, paired
devices, and other state.** Back up anything needed first. Read-only inspection
confirmed that `workspace-openclaw-pod` mounts `workspace-openclaw-openclaw` at
`/home/core/.openclaw`. To discard that state and start with the minimal seed:

```sh
podman pod stop workspace-openclaw-pod
podman pod rm workspace-openclaw-pod
podman volume rm workspace-openclaw-openclaw
make workspace
```

`podman rm` removes containers, not named persistent volumes;
`podman volume rm` removes the specifically named volume. Do not use `make clean`
for this reset: it deletes all workspace volumes. Keep `workspace-openclaw-home`
(writable home and sibling migration captures) and all unrelated volumes.
`make workspace` stops/replaces workspace pods but preserves their volumes,
renders the updated chart, and starts the workspace. The commands above are
manual instructions; no live reset or restart was performed for this change.

OpenClaw retains its SQLite boot-history restart breaker: after 3 unclean boots
within 5 minutes it suppresses provider/channel auto-start and drains the time
window. Do not delete state or reset the breaker manually. No live restarts have
been performed.

Upstream evidence:
- [Control UI pairing policy at the inspected revision](https://github.com/openclaw/openclaw/blob/383c124cc32ffee3f8e56f549b88da94d269a4af/src/gateway/server/ws-connection/connect-policy.ts)
- [Gateway authentication](https://docs.openclaw.ai/gateway/authentication)
- [Official images and automatic state migrations](https://docs.openclaw.ai/install/docker)
- [Inspected release 2026.10.4](https://github.com/openclaw/openclaw/releases/tag/v2026.10.4)
- [Podman network/static IP and host-IP support](https://docs.podman.io/en/latest/markdown/podman-kube-play.1.html)

Verification: `python3 tests/verify_openclaw.py` renders and lints, checks fresh
initialization and byte-for-byte preservation of existing configuration, backups,
and health baselines on reruns, validates the seeded config, then checks a
disposable gateway/nginx handshake using a fresh
signed device without token or pairing. It does not test an actual browser.
Requires Python 3, PyYAML, Podman and locally cached chart images (Helm, nginx,
and the configured OpenClaw image). It uses no host mounts, published ports, or
workspace state and removes its disposable containers afterward.

`infrastructure/values.yaml` controls service enablement, images, image pull
policy, and host directory mounts. Service-specific tool and gateway
configuration is under `infrastructure/configs/`, except OpenClaw's inline config
in `infrastructure/templates/configmaps/openclaw.yaml`.

The rendered manifest and application state use Podman persistent volumes.
`make down` leaves those volumes intact so state survives a restart; `make
clean` permanently removes them.

## Core Image

The `containers/core` Git submodule contains the Containerfile for the image
used by OpenCode and VSCodium. Build a local copy with:

```sh
make -C containers/core build
```

The default chart references `ghcr.io/alexstorm1313/core:latest`. Change the
service image values if you want the chart to use a locally built image.

## Structure

- `infrastructure/` - Helm chart, configuration, secrets directory, and
  generated Kubernetes manifest
- `infrastructure/values.yaml` - workspace service and mount configuration
- `infrastructure/configs/` - gateway and tool configuration files
- `containers/core/` - core container image Git submodule
- `Makefile` - local workspace lifecycle commands

## Notes

- `infrastructure/kube.yaml` is generated by `make kube` and is not tracked.
- `workspace` is the Helm release name used in generated resource names; the
  chart does not set a Kubernetes namespace.
- `podman kube play` applies the rendered local manifest; this project does not
  deploy the chart to a Kubernetes cluster.
