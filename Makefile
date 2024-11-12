.PHONY: build kube play down workspace install upgrade uninstall cert

NAMESPACE=workspace

# OKD_LOGIN_TOKEN=sha256~800aG_QUJ6WO-GxtpFdSs4IXpkWJf1fu2foLTox3GgQ
# OKD_REGISTERY_URL=
KUBECONFIG_PATH=~/.kube/config
# KUBECONFIG_PATH=/home/alexstorm13/Development/okd-tooling/output/sno/4.15.0-0.okd-2024-03-10-010116/auth_bak/kubeconfig

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
	podman kube down --force kube.yaml

# Build containers, Generate deployment and Run the deployment with Podman
workspace:
	make build
	make kube
	make play

# Push local containers to the OKD/OpenShift registery
push:
	make build
	podman login -u kubeadmin -p ${OKD_LOGIN_TOKEN} ${OKD_REGISTERY_URL} --tls-verify=false

	@# podman push localhost/${NAMESPACE}-pod-container:tag ${OKD_REGISTERY_URL}/${NAMESPACE}-pod-container:tag --tls-verify=false

# Install the Helm Chart on the OKD/OpenShift cluster
install:
	podman run --privileged -it --rm -v ${KUBECONFIG_PATH}:/root/.kube/config -v ./:/apps -w /apps alpine/helm:latest --namespace=appfusion install ${NAMESPACE} --values values.yaml --values ./values.okd.yaml .
	make push

# Upgrade the Helm Chart on the OKD/OpenShift cluster
upgrade:
	make push
	podman run --privileged -it --rm -v ${KUBECONFIG_PATH}:/root/.kube/config -v ./:/apps -w /apps alpine/helm:latest --namespace=appfusion upgrade ${NAMESPACE} --values values.yaml --values ./values.okd.yaml .

# Uninstall the Helm Chart on the OKD/OpenShift cluster
uninstall:
	podman run --privileged -it --rm -v ${KUBECONFIG_PATH}:/root/.kube/config -v ./:/apps -w /apps alpine/helm:latest --namespace=appfusion uninstall ${NAMESPACE}

# Copy the certificate from the proxy container
cert:
	podman cp ${NAMESPACE}-proxy-pod-proxy:/etc/nginx/certificates/certificate.crt ./secret