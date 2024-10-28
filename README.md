# Development Environment Setup

This repository contains a Makefile for managing a development environment that runs on both Podman locally and OKD (OpenShift Origin Community Distribution) in production. The environment consists of multiple containerized services including a workspace, Ollama, database, and proxy components.

## Prerequisites

Before using this Makefile, ensure you have the following:

- Podman installed
- Access to an OKD cluster (for production deployment)
- Helm
- The following configuration files:
  - Kubernetes config (`~/.kube/config`)
  - OKD login token
  - WakaTime config (optional)

## Environment Variables

The Makefile uses several configurable paths and variables:

```makefile
NAMESPACE=workspace
KUBECONFIG_PATH=~/.kube/config
OKD_LOGIN_TOKEN=sha256~Wply36AX2gRsZltbfB91u0WtgvUBaWG20Jn08NfvGLs
OKD_REGISTERY_URL=default-route-openshift-image-registry.apps.sno.okd/pdfusion
```

## Available Commands

### Local Development

- `make build`: Builds locally defined container images using Podman

- `make kube`: Generates Kubernetes manifests using Helm
  - Creates a `kube.yaml` file with all resource definitions

- `make play`: Deploys the environment locally using Podman Kube
  - Uses the generated `kube.yaml` file

- `make down`: Tears down the local environment
  - Forcefully removes all deployed resources

- `make workspace`: Convenience command that runs build, kube, and play in sequence
  - Complete local environment setup

### Production Deployment

- `make push`: Builds and pushes images to the OKD registry
  - Logs in to the registry using the configured token
  - Pushes workspace and database images

- `make install`: Installs the environment in OKD using Helm
  - Uses values.yaml and values.okd.yaml for configuration
  - Automatically pushes images

- `make upgrade`: Updates an existing installation
  - Pushes new images
  - Upgrades the Helm release

- `make uninstall`: Removes the environment from OKD
  - Uninstalls the Helm release

### Utilities

- `make cert`: Extracts the root certificate from the proxy container
  - Copies it to the local directory

## Directory Structure

The project expects the following directory structure:

```
.
├── containers/
│   ├── workspace/
│   ├── ollama/
│   ├── database/
│   └── proxy/
├── values.yaml
├── values.podman.yaml
├── values.okd.yaml
└── Makefile
```

## Usage Examples

1. To set up a local development environment:
```bash
make workspace
```

2. To deploy to OKD:
```bash
make install
```

3. To update the production environment:
```bash
make upgrade
```

4. To tear down the local environment:
```bash
make down
```

## Notes

- The Makefile uses Podman instead of Docker for container operations
- The environment can be deployed both locally and to OKD
- Configuration is managed through Helm values files
- Sensitive files (SSH keys, kubeconfig) are temporarily copied during build and then removed
- The proxy container provides SSL certificates for secure communications

## Security Considerations

- SSH keys and Kubernetes configuration files are only temporarily present during builds
- OKD authentication is handled via token
- SSL certificates are managed through the proxy container
- Ensure proper access controls are in place for the OKD registry

## Troubleshooting

If you encounter issues:
1. Ensure all prerequisites are installed
2. Verify the paths to configuration files
3. Check that the OKD token is valid
4. Ensure proper network access to the OKD registry
5. Verify the namespace doesn't conflict with existing deployments
