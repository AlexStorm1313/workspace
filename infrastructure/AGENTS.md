# Infrastructure authoring

This file supplements the repository-root `AGENTS.md` for changes under
`infrastructure/`. Keep lifecycle/Podman operations in the root guide; keep chart
and resource-authoring conventions here. Avoid duplicating instructions in every
template directory unless that directory needs genuinely different rules.

## Chart structure and runtime

- `Chart.yaml`: static Helm chart metadata. Its name is not a workspace identity.
- `values.yaml`: service enablement, images, and other configuration defaults.
- `templates/deployments/`: workload templates.
- `templates/volumes/`: PVC templates mapped to Podman named volumes.
- `templates/configmaps/`: configuration resources when needed.
- `templates/_snippets.yaml`: shared pod/container security-context helpers.
- `configs/`, `secrets/`, `state/`: configuration and local runtime inputs. Inspect
  relevant paths only; do not enumerate or read secret contents unnecessarily.
- `kube.yaml`: generated output, not a source file. Never edit or commit it.

The target runtime is **Podman kube play**, not a Kubernetes cluster. Confirm
Podman support before introducing a resource kind, field, storage feature, or
controller behavior. A valid Kubernetes schema does not imply Podman support.
Do not assume Kubernetes Services, Ingress, RBAC, or namespace isolation work as
they would in a cluster.

Prefer Bash for shell commands when the selected image provides it. Minimal
images may only have `sh`; the illustrative example below uses that fallback. Do not
switch an image's entrypoint to Bash without confirming Bash is installed.

## Required namespace scoping

Multiple worktrees can deploy to the same Podman backend. **Every new stack-owned
top-level resource name must include `{{ .Release.Name }}` as its prefix.**
The Makefile passes `NAMESPACE` as the Helm release name; it is not
`metadata.namespace`. Never hardcode the current namespace, use `.Chart.Name`
as the identity, or rely on a Kubernetes Namespace to prevent collisions.

Use exactly three naming layers: **`{namespace}-{pod}-{container}`**.

- `{namespace}` is `{{ .Release.Name }}`, supplied through `NAMESPACE`.
- `{pod}` is the logical pod name, without its namespace prefix.
- `{container}` is the container's local name within that pod.

| Resource/reference | Pattern |
| --- | --- |
| Pod identity | `{namespace}-{pod}` |
| Application container identity | `{namespace}-{pod}-{container}` |
| Container-scoped PVC / claim reference | `{namespace}-{pod}-{container}` |
| Container-scoped ConfigMap / Secret and references | `{namespace}-{pod}-{container}` |
| Identity labels and selectors | Match the owning namespace-prefixed identity |

Do not introduce additional naming layers. Derive each name from its owning
pod/container and keep references identical. If a container needs multiple
resources of the same kind, agree on that naming extension before introducing
one. Preserve existing deployed names unless a migration is requested: renaming
a claim can disconnect data or cause recreation.

Keep all references consistent: Deployment selectors must match pod labels;
`claimName`, configuration references, and volume mounts must point to the exact
rendered names. Container-local identifiers are fine inside their own pod. They
do not need global prefixes, but a bare container alias is not a unique
cross-workspace identity.

Name prefixes do **not** isolate everything:

- Host ports still collide on the same host address. Do not add a fixed
  `hostPort` casually; make host bindings explicit and coordinate allocation.
- A fixed writable `hostPath` shares data across releases. Prefer scoped PVCs,
  or require a clearly scoped host path. Do not interpolate unchecked names into
  arbitrary host paths or cleanup commands.
- Shared networking is intentional where services need to communicate; do not
  create a per-release network by default just for naming uniqueness.
- Existing host Podman/SSH-agent sockets are intentionally shared capabilities,
  not resources created per release. Document any new shared-resource exception.
- Never clean up using a broad namespace-prefix regex. Discover and verify exact
  owned resource names before any destructive operation.

## Translating "create a deployment for X with Y" into resources

Start with the requested behavior rather than copying an entire existing app.
Inspect the selected image's documented entrypoint, user, configuration, writable
directories, listen addresses, and ports. Ask only for missing decisions that
affect data ownership, access, credentials, hardware, or external exposure.

| Requirement | Implementation pattern |
| --- | --- |
| One application | A gated template under `templates/deployments/`, following the existing Deployment structure and matching selectors/labels |
| Tightly coupled proxy, dashboard, or helper | Separate named containers in the same pod when they need a shared lifecycle/network or shared files |
| Independent dependency | A separate gated pod/deployment, with explicitly configured connection details |
| Persistent data | A scoped PVC and matching claim reference; mount only the directories that need persistence |
| Static non-secret configuration | Files under `configs/`, embedded in a gated ConfigMap and mounted read-only |
| Credentials or TLS material | Local secret inputs and scoped Secret references; never plaintext credentials in committed values or ConfigMaps |
| One-time preparation before startup | An init container mounting the same data volume as the application |
| Browser/API access | Internal application listener, with optional proxy routing; host ports only when requested |
| GPU, device, or host integration | Explicit host prerequisites and narrowly scoped device/socket mounts, with justified security exceptions |

Keep related values in `services.<pod>`: `enabled`, `image`, and the settings
actually required by the request. Add separate image settings for independently
selected sidecars rather than assuming every container runs the application
image. Use the shared `deployments.containers.pullPolicy` for application,
sidecar, and init images unless a specific exception is requested. For a
hyphenated values key, use `index`, for example
`{{ (index .Values.services "{pod}").image }}`.

Gate all resources owned by a service with the same enablement condition.
Values alone do not create resources. If a dependency is separately optional,
make that dependency explicit instead of leaving dangling required references.
Do not use `optional: true` to hide a configuration file that the app needs to
start. The direct Pod example below illustrates the naming and mount wiring;
it does not require converting existing Deployments to Pods.

## Configuration and Helm rendering

Keep application configuration in `configs/` rather than large inline strings in
deployment templates. A container-scoped ConfigMap can embed a file like this.
Replace `{pod}` and `{container}` placeholders before using these illustrative
snippets; `.Release.Name` supplies `{namespace}` during Helm rendering:

```yaml
{{ if (index .Values.services "{pod}").enabled }}
apiVersion: v1
kind: ConfigMap
metadata:
  name: {{ .Release.Name }}-{pod}-{container}
data:
  app.conf: |
{{ .Files.Get "configs/{pod}/app.conf" | nindent 4 }}
{{ end }}
```

Wire it through `volumes[].configMap.name`, then mount the `app.conf` key at the
application's required path with `subPath: app.conf` and `readOnly: true`.
Prefer a file mount when mounting the whole directory would hide files shipped
in the image. For multiple configuration files, one ConfigMap can contain
multiple keys. `.Files.Glob` with `base` and `.Files.Get` is suitable for a
directory of config files; preserve the chart root using `$` inside a range.
Ensure every source file exists: `.Files.Get` can silently return empty content.

**Loading a file is not templating it.** `.Files.Get` and `.Files.Glob` do not
expand `{{ .Release.Name }}` inside file contents. If trusted chart-owned config
needs release-specific addresses, explicitly render it with
`tpl (.Files.Get "configs/{pod}/app.conf") .`, or generate the relevant text
in the ConfigMap template. Never apply `tpl` to arbitrary user/secret input.
Likewise, `${VARIABLE}` is only expanded if an explicitly configured runtime
entrypoint performs substitution; it is not automatically a Helm feature.
Do not invent environment variables without wiring their values into the pod.
Quote string-valued environment settings, including numeric-looking values.

## Storage and startup preparation

- Distinguish persistent application state, replaceable cache, static config,
  and temporary files. Do not persist an entire image filesystem by default.
- A single scoped PVC can hold multiple directories mounted with `subPath`.
  Create required subdirectories before application startup using an idempotent
  init container (`mkdir -p`); mount the volume root in that initializer.
- Seed image defaults only when needed and without overwriting existing user
  data. Avoid unconditional copy/delete steps that could overwrite user changes
  or lose persistent data on repeated startup.
- Keep init containers narrowly scoped to the required volume. For provisioning
  that starts a temporary server, use bounded readiness waits, propagate every
  background task's failure, and trap signals/exit to stop child processes.
  Downloads or model provisioning can make creation slow; make them explicit
  requirements rather than surprising default startup work.
- A named claim is an identity, not proof of a backup or retention policy.
  Follow this repository's PVC declaration convention rather than relying on
  implicit volume creation. Never migrate existing data implicitly.
- Do not copy absolute checkout paths, home directories, host UIDs, or device
  locations from another machine. Use explicit configuration for needed host
  paths, and distinguish intentionally shared inputs from per-worktree state.

## Networking, proxies, and sidecars

- Containers in a pod share its network namespace: use `127.0.0.1` for their
  communication and allocate distinct listening ports. A listener bound only to
  loopback is not directly reachable from other pods; a colocated proxy can
  expose it intentionally.
- Cross-pod connections use confirmed namespace-qualified pod DNS names on the
  intended shared network. Derive addresses from the release and pod identity,
  not a hardcoded release from a sample. Runtime Deployment-name transformations
  are discovery details, not additional authoring naming layers.
- A proxy integration includes the backend address/port, routing hostname,
  enabled config resource, and mounts. Parameterize external domains and TLS
  inputs separately from the internal namespace. Hostnames alone do not create
  DNS records, network aliases, certificate coverage, or host port mappings.
- For WebSockets, streaming, or SSE, deliberately configure upgrade headers,
  forwarded headers, buffering, and timeouts as the app requires. For dynamic
  backends, use the proxy image's supported DNS resolver setup rather than
  assuming backend addresses remain fixed across recreation.
- Preserve authentication and trusted-origin boundaries. Do not copy disabled
  authentication, fixed sample passwords, permissive origin rewriting, disabled
  SSH host-key verification, or token-bearing request logging from examples.
- Init/probe order is not cross-pod readiness orchestration. Configure dependency
  retries/timeouts and supported health checks based on the real application.

## Image compatibility and host capabilities

Reuse the local security helpers and preserve their existing restrictions.
The shared root filesystem currently remains writable (`readOnlyRootFilesystem:
false`) for compatibility with existing workloads. Do not enable read-only roots
globally without auditing writes (including Hermes under `/opt/hermes` and gateway
temporary files) and providing explicit writable mounts. Do not weaken other
security restrictions as part of that work.

Some images require an initial root process to drop privileges, or need an init
such as `tini` for signal forwarding and child reaping. Verify that behavior
against the image, including Podman's user mapping, before overriding its user
or entrypoint. Shared process namespaces affect PID 1 behavior; enable them only
for an actual requirement. Scope and explain security exceptions per container.

For GPU access, distinguish character devices from directory mounts, verify the
host devices/drivers exist, and do not create missing device paths. Privileged
mode is not a generic GPU fix. Host Podman and SSH-agent sockets grant broad host
capabilities; attach them only to containers that need them, not every sidecar.

## Example: add an optional service with persistent data

Add configuration to the existing `services:` mapping in `values.yaml` (do not
create a second `services:` key). Default new services to disabled unless their
activation is explicitly requested:

```yaml
services:
  "{pod}":
    enabled: false
    image: "{image}"
```

The snippets are illustrative, not ready to render. Replace `{pod}` and
`{container}` with the intended logical names and `{image}` with the selected
image reference. The image placeholder is configuration, not a naming layer.
Create the direct Pod template under `templates/pods/{pod}.yaml` (create that
directory if needed). Use `{namespace}-{pod}-{container}` consistently:

```yaml
{{ if (index .Values.services "{pod}").enabled }}
apiVersion: v1
kind: Pod
metadata:
  name: {{ .Release.Name }}-{pod}
  labels:
    app: {{ .Release.Name }}-{pod}
spec:
  {{ include "pod.securityContext" . | indent 2 }}
  containers:
    - name: {container}
      {{ include "container.securityContext" . | indent 6 }}
      image: {{ (index .Values.services "{pod}").image | quote }}
      imagePullPolicy: {{ .Values.deployments.containers.pullPolicy }}
      command: ["sh", "-c", "while :; do sleep 3600; done"]
      volumeMounts:
        - name: data
          mountPath: /data
  volumes:
    - name: data
      persistentVolumeClaim:
        claimName: {{ .Release.Name }}-{pod}-{container}
{{ end }}
```

Create `templates/volumes/{pod}.yaml` with the **same enablement condition**:

```yaml
{{ if (index .Values.services "{pod}").enabled }}
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: {{ .Release.Name }}-{pod}-{container}
spec: {}
{{ end }}
```

`spec: {}` follows this repository's Podman PVC convention; it is not a portable
Kubernetes storage configuration. Reuse the security helpers rather than
silently relaxing privileges. Check that the real application supports UID 1001,
group 0, and the existing security context. If read-only roots are proposed,
audit and mount all required writable paths first. Add probes only when
supported by the runtime and application.

The pod identity is `{namespace}-{pod}`; its application container
and PVC identities are `{namespace}-{pod}-{container}`. The local volume name
`data` connects the mount to the claim declaration; it is not another global
naming layer. For existing Deployment templates, Podman can transform runtime
names: confirm them through discovery rather than adding naming layers to this
convention. This documentation example does not migrate existing templates.

`make validate` is available from the repository root as an optional check, not a
required authoring or deployment step. It lints the chart and schema-checks the
existing `kube.yaml` without regenerating or overwriting it or starting/stopping
the stack. If an updated manifest is wanted, `make kube NAMESPACE="{namespace}"`
generates it; replace the namespace placeholder and preserve any older manifest
needed for teardown. Validation does not verify naming isolation, Podman
compatibility, or readiness; review scoping and references when authoring.

Keep local secrets out of examples, generated output shared with others, and Git.
Do not weaken root `.gitignore` rules or assume `.helmignore` alone protects
credentials. Scope Secret names and references exactly like other resources.
