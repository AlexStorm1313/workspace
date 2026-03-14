.PHONY: build kube play down workspace install upgrade uninstall certificate

NAMESPACE=workspace

# Generate deployment from Helm Chart
kube:
	@podman run --privileged -it --rm -v ./:/apps -w /apps docker.io/alpine/helm:latest template ${NAMESPACE} --dry-run=client --values values.yaml --values values.podman.yaml . > kube.yaml

# Run the deployment with Podman
play:
	@podman kube play --replace kube.yaml

# Stop the deployment with Podman
down:
	@podman kube down kube.yaml

# Build containers, Generate deployment and Run the deployment with Podman
workspace:
	@make kube
	@make play

# Generate a Certificate
certificate:
	@podman run -it --rm \
	-e DOMAIN=localhost \
	-e COUNTRY=US \
	-e STATE=workspace \
	-e CITY=workspace \
	-e ORGANIZATION=workspace \
	-v ./secrets:/certs:Z \
	docker.io/alpine/openssl:latest req -x509 -noenc -days 365 -newkey rsa:2048 -keyout /certs/tls.key -out /certs/tls.crt -subj "/C=US/ST=workspace/L=workspace/O=workspace/CN=localhost" -addext "subjectAltName=DNS:localhost,DNS:*.localhost"

expose-podman-api:
	@podman system service --time=0 tcp://0.0.0.0:2375