.PHONY: kube play down workspace clean certificate auth-codex

NAMESPACE=workspace
USERNS=--userns=keep-id:uid=1001,gid=0

# Generate deployment from Helm Chart
kube:
	@podman run -i --rm -v ./infrastructure:/infrastructure:Z -w /infrastructure --entrypoint sh docker.io/alpine/helm:latest -c 'helm template ${NAMESPACE} --dry-run=client --values ./values.yaml . > ./kube.yaml.tmp && mv ./kube.yaml.tmp ./kube.yaml'

# Run the deployment with Podman
play:
	@podman kube play --replace $(USERNS) ./infrastructure/kube.yaml
	@podman pod ls | grep ${NAMESPACE}

# Stop the deployment with Podman
down:
	@podman kube down --force ./infrastructure/kube.yaml
# 	@podman volume rm ${NAMESPACE}-gateway

# Build containers, Generate deployment and Run the deployment with Podman
workspace:
	@make down
	@make kube
	@make play

# Remove all volumes
clean:
	@podman volume ls --quiet --filter 'name=^${NAMESPACE}-' | xargs -r podman volume rm --force

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