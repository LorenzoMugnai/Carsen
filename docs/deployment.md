# Deployment

## Local development

Install the package in a Python 3.12 environment, create or provide a YAML configuration, index sources, then serve:

```bash
ariadne validate --config config.example.yaml
ariadne index --config config.example.yaml
ariadne serve --config config.example.yaml
```

## Remote HTTP

Set `server.transport: http`, bind an appropriate `host` and use a unique `port` per instance. Place an authenticating reverse proxy in front if exposing beyond trusted local networks.

## Docker

The repository includes a `Dockerfile` and `docker-compose.example.yml`. The compose file demonstrates Qdrant plus two Ariadne services with separate configs, ports and data volumes.

## systemd

`deployment/systemd/ariadne@.service` runs `ariadne serve %i --transport http` under an `ariadne` user with `ARIADNE_CONFIG_DIR=/etc/ariadne`. Enable one unit per registered instance, for example `ariadne@example.service`.
