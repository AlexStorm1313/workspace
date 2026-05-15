.PHONY: build kube play down workspace install upgrade uninstall certificate credentials

NAMESPACE=workspace

# Generate deployment from Helm Chart
kube:
	@podman run -it --rm -v ./infrastructure:/infrastructure:Z -w /infrastructure docker.io/alpine/helm:latest template ${NAMESPACE} --dry-run=client --values ./values.yaml . > ./infrastructure/kube.yaml

# Run the deployment with Podman
play:
	@podman kube play --replace ./infrastructure/kube.yaml
	@podman pod ls | grep ${NAMESPACE}

# Stop the deployment with Podman
down:
	@podman kube down ./infrastructure/kube.yaml

# Build containers, Generate deployment and Run the deployment with Podman
workspace:
	@make kube
	@make play

expose-podman-api:
	@podman system service --time=0 tcp://0.0.0.0:2375

jappa:
	@cp ~/.ssh/id_ed25519 ./shared/secrets/codium/id_privatekey

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

credentials:
	@podman run --rm -it \
	--name codex-debug \
	-p 1455:1455 \
	--user 0:0 \
	-v ./infrastructure/secrets/codex:/workspace/.config/codex:Z \
	docker.io/photoprism/codex:latest

opencode:
	@podman exec -it workspace-opencode-pod-opencode-server opencode

openclaw:
	@podman exec -it workspace-openclaw-pod-openclaw bash