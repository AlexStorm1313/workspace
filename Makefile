.PHONY: kube play down workspace clean certificate mkcert

NAMESPACE=workspace
USERNS=--userns=keep-id:uid=1001,gid=0

# Generate deployment from Helm Chart
kube:
	@podman run -i --rm -v ./infrastructure:/infrastructure:Z -w /infrastructure --entrypoint sh docker.io/alpine/helm:latest -c 'helm template ${NAMESPACE} --dry-run=client --values ./values.yaml . > ./kube.yaml.tmp && mv ./kube.yaml.tmp ./kube.yaml'

# Run the deployment with Podman
play:
	@podman kube play --replace $(USERNS) ./infrastructure/kube.yaml
	@GATEWAY_INFRA=$$(podman pod inspect --format '{{.InfraContainerID}}' workspace-gateway-pod); \
	podman network disconnect --force podman-default-kube-network $$GATEWAY_INFRA; \
	podman network connect \
		--alias website.appfusion.workspace-gateway-pod \
		podman-default-kube-network $$GATEWAY_INFRA
	@podman pod ls | grep ${NAMESPACE}

# Stop the deployment with Podman
down:
	@podman kube down --force ./infrastructure/kube.yaml

# Build containers, Generate deployment and Run the deployment with Podman
workspace:
	@make down
	@make kube
	@make play

# Remove all volumes
clean:
	@podman volume ls --quiet --filter 'name=^${NAMESPACE}-' | xargs -r podman volume rm --force

# Generate a local development TLS certificate for localhost subdomains
certificate:
	@mkdir -p ./infrastructure/secrets/gateway
	@umask 077; podman run --rm \
	-v ./infrastructure/secrets/gateway:/certs:Z \
	docker.io/alpine/openssl:latest req -x509 -noenc -sha256 -days 365 -newkey rsa:2048 -keyout /certs/tls.key -out /certs/tls.crt -subj "/C=US/ST=workspace/L=workspace/O=workspace/CN=localhost" -addext "subjectAltName=DNS:localhost,DNS:*.localhost,DNS:*.workspace.localhost"

# Generate a locally trusted TLS certificate and trust its CA in Ungoogled Chromium.
# Restart Chromium after running this target to load the updated NSS database.
mkcert:
	@podman run --rm --userns=keep-id --security-opt label=disable \
		-v ./infrastructure/secrets/gateway:/certs \
		-v "$$HOME/.local/share:/mkcert-data" \
		-v "$$HOME/.var/app/io.github.ungoogled_software.ungoogled_chromium:/chromium-data" \
		-e CAROOT=/mkcert-data/mkcert \
		--entrypoint sh docker.io/alpine/mkcert:latest -ec '\
			mkdir -p /mkcert-data/mkcert /chromium-data/data/pki/nssdb; \
			mkcert -cert-file /certs/tls.crt -key-file /certs/tls.key localhost "*.localhost" "*.workspace.localhost"; \
			if [ ! -f /chromium-data/data/pki/nssdb/cert9.db ]; then certutil -d sql:/chromium-data/data/pki/nssdb -N --empty-password; fi; \
			certutil -d sql:/chromium-data/data/pki/nssdb -D -n "mkcert local development CA" 2>/dev/null || true; \
			certutil -d sql:/chromium-data/data/pki/nssdb -A -n "mkcert local development CA" -t "C,," -i /mkcert-data/mkcert/rootCA.pem'
