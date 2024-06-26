# Tailscale Auto docker-compose generator

Automatically generate tailscale sidecar containers for each of your services as per [Contain your excitement: A deep dive into using Tailscale with Docker](https://tailscale.com/blog/docker-tailscale-guide).

Instead of repeating yourself over and over, just add labels to each container a-la traefik.

## Setup

1. Install the python dependencies: `pip install -r requirements.txt`
2. Put your normal docker stuff in a yaml file e.g. `compose.main.yaml`. Add the labels `tailscale.port` and `tailscale.allowFunnel` to each of your containers e.g:
```yaml
services:
  whoami:
    image: containous/whoami
    container_name: whoami
    restart: unless-stopped
    labels:
      - "tailscale.port=80"
      - "tailscale.allowFunnel=false"
  mealie:
    image: ghcr.io/mealie-recipes/mealie:v1.0.0
    container_name: mealie
    volumes:
      - ./mealie:/app/data/
    environment:
      - ALLOW_SIGNUP=true
    restart: unless-stopped
    labels:
      - "tailscale.port=9000"
      - "tailscale.allowFunnel=false"
```
3. Start the script with your tailscale credentials: `python make_tailscale.py --ts_oauth_client_secret tskey-client-aJNDSFD-DSAd...`.
This will regenerate `compose.yaml` with all the tailscale magic everytime you edit `compose.main.yaml` so find a way to keep it running in the background.

Make sure you're enabled serving, ACL tags etc.. in the tailscale admin console.

## How it works

For every service with "tailscale" labels, the script will generate a sidecar container + a serve config. Under `.tailscale`, the script generates the following structure:

```
.tailscale
├─ serve_configs
│  ├─ mealie.json
│  ├─ whoami.json
├─ states
│  ├─ mealie
│  ├─ whoami
```
