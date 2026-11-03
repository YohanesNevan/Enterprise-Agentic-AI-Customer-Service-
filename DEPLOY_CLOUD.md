# Demo cloud deployment

This profile follows the TRD demo-cloud shape: one Linux VM running Docker Compose, with Caddy terminating HTTPS in front of the web app and API. Keep this deployment on synthetic data as required by the FRD; it is a protected capstone demo, not a public banking service.

## VM and network

The TRD cloud target is a single VM with 4 vCPU and 16 GB RAM. An AWS Lightsail Xlarge Linux bundle currently matches that size at US$84/month, before tax and any extra services. Singapore (`ap-southeast-1`) is available. See [Lightsail bundle pricing](https://aws.amazon.com/lightsail/pricing/) and [supported regions](https://docs.aws.amazon.com/lightsail/latest/userguide/understanding-regions-and-availability-zones-in-amazon-lightsail.html). A university VM with equivalent capacity is also suitable.

Use a DNS name you control and point its A record to the VM's static IPv4 address. Allow inbound TCP 80 and 443 (plus UDP 443 for HTTP/3); restrict SSH (22) to your own IP. The cloud Compose profile publishes only Caddy's web ports. PostgreSQL, Redis, MinIO, Mailpit, the API, and the CRM simulator remain on the private Compose network.

## Configure secrets

Copy the project to the VM without `.env`, `.env.cloud`, SQLite files, or `node_modules`. Then:

```sh
cp .env.cloud.example .env.cloud
chmod 600 .env.cloud
```

Edit `.env.cloud` and set `SITE_HOST`, `ACME_EMAIL`, and a private demo username. Generate `POSTGRES_PASSWORD`, `MINIO_ROOT_PASSWORD`, and `JWT_SIGNING_KEY` as independent random values (for example, `openssl rand -hex 32`). Set `MINIO_ROOT_USER` as well.

Generate a bcrypt hash interactively with Caddy (it prompts for the password, so the plaintext is not part of the command):

```sh
docker run --rm -it caddy:2-alpine caddy hash-password
```

Put the resulting hash in `SITE_PASSWORD_HASH`. In this Compose environment file, escape every dollar sign in the hash by doubling it (`$` becomes `$$`). Never put the plaintext demo password in the file. Keep `.env.cloud` out of source control and backups that are not encrypted.

The browser shows a basic-auth prompt before serving the UI or API. This is a shared demo gate, not individual user accounts; the application's role selector remains for demonstration only.

## Build and start

Install Docker Engine and the Compose plugin on the VM. From the project directory, validate the configuration and start the stack:

```sh
docker compose --env-file .env.cloud -f docker-compose.yml -f docker-compose.cloud.yml config -q
docker compose --env-file .env.cloud -f docker-compose.yml -f docker-compose.cloud.yml up -d --build
docker compose --env-file .env.cloud -f docker-compose.yml -f docker-compose.cloud.yml ps
```

After DNS resolves to the VM, Caddy requests and renews the TLS certificate automatically. Open `https://SITE_HOST` and sign in with the demo credentials. The API documentation is at `https://SITE_HOST/docs` behind the same gate.

## Database backup

Keep PostgreSQL in its Docker volume and create a nightly encrypted `pg_dump` backup to storage outside the VM. The TRD requires a recoverable database snapshot for demo continuity. Test restoring a backup before relying on it.

## Current deployment limits

The cloud profile protects the whole demo behind one password and keeps backing services private. It does not add individual staff identity, multi-user login, managed secret storage, a managed database, or high availability. Do not load real customer information or connect production banking systems to this demo.
