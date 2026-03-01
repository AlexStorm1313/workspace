.PHONY: build kube play down workspace install upgrade uninstall cert

NAMESPACE=workspace
KUBECONFIG_PATH=~/.kube/config

# Build local containers
build:
	@# podman build -t localhost/${NAMESPACE}-pod-container containers/pod/container

# Generate deployment from Helm Chart
kube:
	rm -rf kube.yaml
	podman run --privileged -it --rm -v ./:/apps -w /apps docker.io/alpine/helm:latest template ${NAMESPACE} --dry-run --values values.yaml --values values.podman.yaml . > kube.yaml

# Run the deployment with Podman
play:
	podman kube play --replace kube.yaml

# Stop the deployment with Podman
down:
	podman kube down kube.yaml

# Build containers, Generate deployment and Run the deployment with Podman
workspace:
	make build
	make kube
	make play

# Copy the certificate from the proxy container
cert:
	podman cp ${NAMESPACE}-proxy-pod-proxy:/etc/nginx/certificates/certificate.crt ./secret