.PHONY: kube play down workspace clean certificate

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

chromium:
	/usr/bin/flatpak run --branch=stable --arch=x86_64 --command=/app/bin/chromium --file-forwarding org.chromium.Chromium --use-gl=angle --use-angle=gl --ignore-gpu-blocklist --disable-gpu-driver-bug-workaround --ozone-platform=wayland --enable-native-gpu-memory-buffers --enable-gpu-memory-buffer-video-frames --enable-zero-copy --enable-chrome-browser-cloud-management --enable-gpu-rasterization --enable-plugins --enable-extensions --enable-user-scripts --enable-printing --enable-sync --auto-ssl-client-auth --disable-features=ExtensionManifestV2DeprecationWarning,ExtensionManifestV2Disabled,ExtensionManifestV2Unsupported --enable-features=AcceleratedVideoEncoder,AcceleratedVideoDecodeLinuxGL,AcceleratedVideoDecodeLinuxZeroCopyGL,VaapiOnNvidiaGPUs,OverlayScrollbar,AllowLegacyMV2Extensions,TouchpadOverscrollHistoryNavigation --remote-debugging-address=127.0.0.1 --remote-debugging-port=9222 --user-data-dir=/tmp/chromium-devtools @@u %U @@