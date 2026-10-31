# Workspace

A configured local development workspace using **Helm templates** and
**Podman kube play**, based on the [Skel](https://github.com/AlexStorm1313/skel)
starter. Helm only renders YAML; no Kubernetes cluster or Helm release is used.

## What's included

- `containers/core`: container build sources (Git submodule).
- `infrastructure/values.yaml`: service enablement, images, and shared values.
- `infrastructure/templates/`: workloads, configuration, secrets, and security helpers.
- `infrastructure/configs/` and `infrastructure/state/`: project configuration and state.
- `infrastructure/kube.yaml`: locally generated manifest, ignored by Git.
- `Makefile`: rendering, optional validation, resource discovery, TLS, and lifecycle.

The configured stack enables workspace, gateway, Hermes, Ollama, and OpenCode;
other workload templates are available but disabled by default. This is **not an
empty starter**. Review host paths, sockets, ports, images, credentials, GPU
requirements, and service settings before running on another machine. Initialize
the `containers/core` submodule if you need its build sources; images are not
automatically built by the Makefile.

## Requirements

GNU Make, Bash, and a working Podman configuration with registry access are
required. Helm and kubeconform run in disposable containers. The recipes use
Linux-oriented SELinux mount labels and `--userns=keep-id:uid=1001,gid=0`.

Use the same user and Podman connection as the existing stack. Do not switch to
rootful Podman to work around access problems.

## Render and optionally validate

Run from the repository root:

```bash
make kube NAMESPACE=workspace
make validate NAMESPACE=workspace
```

`kube` checks the gateway TLS pair first. If both files are absent, it generates
a self-signed certificate; an incomplete pair fails without replacement. It then
renders to a temporary file and replaces `infrastructure/kube.yaml` only after
successful rendering. It does not start the stack. Preserve any existing manifest
needed for teardown before rendering a different deployment identity.

`validate` lints the chart and schema-checks the **existing** manifest without
regenerating it or operating on stack resources. It may download tool images and
schemas. It does not prove that the manifest matches current sources, that Podman
supports it, or that applications are ready. Never share generated manifests or
logs without reviewing them for secrets.

### Image pull policy

`deployments.containers.pullPolicy` remains in chart values. Make defaults
`IMAGE_PULL_POLICY` to `IfNotPresent`, overriding that value for rendering/linting.
Environment or command-line overrides support `Always`, `IfNotPresent`, and `Never`:

```bash
make kube IMAGE_PULL_POLICY=Always
```

## Commands and effects

| Command | Effect |
| --- | --- |
| `make` / `make kube` | Prepare TLS if absent and render the manifest; no startup. |
| `make validate` | Lint and schema-check; no rendering or deployment. |
| `make resources` | List prefix-matching pods, volumes, and networks. |
| `make play` | Create/replace resources without starting, configure gateway networking, then start matching pods. No implicit `down` or render. |
| `make down` | Tear down the existing manifest without `--force`; skip if missing. |
| `make workspace` | Sequentially prepare TLS, run `down`, render, then `play`. |
| `make tls` | Check the TLS pair; generate only when both files are absent. |
| `make certificate` | Explicitly generate a self-signed certificate. |
| `make mkcert` | Generate development TLS and update Chromium's local CA database. |
| `make clean` | Force-remove prefix-matched volumes; **can destroy application data**. |

Lifecycle commands change running resources. Do not use them or `clean` as
validation. Run lifecycle commands serially; `workspace` retains ordered recursive
Make calls. Startup messages do not establish readiness; inspect container state
and application logs separately.

## Identity and networking

`NAMESPACE=workspace` is the default **resource-name prefix**, passed as Helm's
release name, not a Kubernetes namespace or isolation boundary. Ordinary shell
environment variables do not override this Make assignment; use a Make argument.

Existing gateway routing and the alias setup reference `workspace` explicitly.
`play` preserves the sequence: create with `--start=false`, inspect the gateway,
configure its network alias, then start pods. Merely changing `NAMESPACE` does
not make this stack independent: coordinate gateway configuration, aliases, host
ports, paths, sockets, and deployed names before deploying another worktree.
`down` targets names in the existing manifest, not a newly supplied prefix.

`resources` uses literal substring matching, not exact ownership verification.
Confirm exact names before operating on resources; shared networks may not
contain the prefix. Never remove resources solely on a broad prefix match.

## Security and configuration

Edit chart sources rather than generated YAML. Keep credentials out of committed
values and ConfigMaps. Ignore rules protect designated secret paths and generated
manifests, not every possible secret location. Preserve existing deployed names,
claims, submodule configuration, and local state when adapting the starter.

Shared container security helpers retain `readOnlyRootFilesystem: false` for
existing runtime compatibility, with privilege escalation disabled, capabilities
dropped, and other existing restrictions unchanged. Read-only roots require a
separate writable-path audit and explicit mounts; they are not enabled by this
upstream integration.

See [stack operations](AGENTS.md) and
[infrastructure authoring](infrastructure/AGENTS.md) for additional guidance.

## License

[MIT](LICENSE).
