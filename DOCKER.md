# Run LifeLog locally with Docker

The stack serves the frontend and API at http://127.0.0.1:8080. PostgreSQL and FastAPI have no published host ports. This is local HTTP development configuration, not a public HTTPS deployment.

A private .env.docker has been prepared locally using the existing API key and a generated PostgreSQL password. Keep it private and out of Git. For a different installation, copy .env.docker.example to .env.docker and supply your own values. Use an alphanumeric database password because the Compose connection URL inserts it directly. Existing backend/.env remains the configuration for your regular Windows setup.

Run these commands yourself from the project root:

```powershell
cd C:\Giri\Learning\lifelog-ai
docker compose --env-file .env.docker config --quiet
docker compose --env-file .env.docker up --build -d
docker compose --env-file .env.docker ps
```

Validation succeeds silently. Avoid running config without --quiet when sharing output, because resolved configuration contains secrets.

Open http://127.0.0.1:8080 and register an account. Docker uses a new PostgreSQL database; your Windows database and its account remain separate. Existing data is not transferred automatically.

The backend waits for PostgreSQL health, applies versioned migrations, then starts FastAPI and its vector retry worker. Nginx starts after the backend healthcheck succeeds. The first embedding-model download can take time. Database data, Chroma vectors, and downloaded models live in named volumes.

Useful commands:

```powershell
docker compose --env-file .env.docker logs --tail 60 backend
docker compose --env-file .env.docker logs --tail 60 frontend
docker compose --env-file .env.docker logs --tail 60 db
docker compose --env-file .env.docker down
```

The final command stops the stack while retaining data. Do not add -v unless you intend to delete all named data volumes. PostgreSQL initialization credentials apply when its volume is first created; changing .env.docker later does not change an existing database password.

Check saving, calendar, summaries, and chatbot behavior. Run down, then up -d, and verify your Docker account and test entry persist. This does not require stopping your existing services on ports 5173, 8000, or 5432; Docker publishes only localhost port 8080.

Frontend images build with an empty VITE_API_BASE_URL and use Nginx /api routing. frontend/.env.local is excluded from the image and continues to configure normal Vite development. Secrets and local data are excluded from both build contexts.

The assistant has not run Docker commands or verified container startup; run the commands above to perform that verification.

If normal development is running at localhost:5173, use 127.0.0.1:8080 for Docker. Cookies are shared across ports on one hostname; using different hostnames prevents the two installations from replacing each other's session cookie.

