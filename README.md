# Project Deployment Guide

This project uses a Makefile to automate container building, deployment, and management using Podman and Helm. It supports both local development using Podman and deployment to OKD/OpenShift clusters.

## Prerequisites

- [Podman](https://podman.io/) installed for container management
- [Helm](https://helm.sh/) for Kubernetes package management
- Access to an OKD/OpenShift cluster (for cluster deployment)

## Environment Variables

Before using the Makefile, set the following environment variables as needed:

- `NAMESPACE`: Workspace namespace (default: workspace)
- `OKD_LOGIN_TOKEN`: Authentication token for OKD/OpenShift registry
- `OKD_REGISTERY_URL`: URL of the OKD/OpenShift registry
- `KUBECONFIG_PATH`: Path to your Kubernetes configuration file

## Available Commands

### Local Development Commands

- `make build`
  - Builds local containers using Podman
  - Note: Container build commands are commented out in the Makefile and need to be customized

- `make kube`
  - Generates Kubernetes deployment files from Helm charts
  - Creates `kube.yaml` using values from `values.yaml` and `values.podman.yaml`

- `make play`
  - Deploys the application locally using Podman
  - Uses the generated `kube.yaml` file

- `make down`
  - Stops the local deployment
  - Forcefully removes all resources defined in `kube.yaml`

- `make workspace`
  - Convenience command that runs `build`, `kube`, and `play` in sequence
  - Complete local development setup in one command

### OKD/OpenShift Cluster Commands

- `make push`
  - Builds containers locally
  - Logs into the OKD/OpenShift registry
  - Pushes containers to the registry
  - Note: Push commands are commented out and need to be customized

- `make install`
  - Installs the Helm chart on the OKD/OpenShift cluster
  - Uses values from `values.yaml` and `values.okd.yaml`
  - Automatically pushes containers to the registry

- `make upgrade`
  - Pushes updated containers to the registry
  - Upgrades the existing Helm chart deployment
  - Uses values from `values.yaml` and `values.okd.yaml`

- `make uninstall`
  - Removes the Helm chart deployment from the cluster

### Utility Commands

- `make cert`
  - Copies the SSL certificate from the proxy container
  - Extracts from `/etc/nginx/certificates/certificate.crt`
  - Saves to the local directory

## Configuration Files

The project expects the following configuration files:

- `values.yaml`: Base Helm values
- `values.podman.yaml`: Podman-specific configuration values
- `values.okd.yaml`: OKD/OpenShift-specific configuration values

## Usage Examples

1. Local development workflow:
```bash
# Start the complete local environment
make workspace

# When finished, tear down the environment
make down
```

2. Cluster deployment workflow:
```bash
# Initial deployment to OKD/OpenShift
make install

# Update existing deployment
make upgrade

# Remove deployment
make uninstall
```

## Notes

- Container build and push commands are commented out in the Makefile and need to be customized according to your project's requirements
- The Makefile uses Podman instead of Docker for container operations
- All Helm operations are executed through Podman to ensure consistency
- The project assumes a proxy container with SSL certificates for HTTPS support

## Security

- Make sure to properly secure your `OKD_LOGIN_TOKEN` and other sensitive environment variables
- The proxy certificate is exposed through the `cert` command - ensure this aligns with your security requirements