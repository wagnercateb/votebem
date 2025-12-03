- ver django_votebem/scripts/linux/update_project_container.sh
       
Here’s a clean, safe way to rebuild and bring your Docker Compose stack back up on the remote host after updating code. I’ll show both “all services” and “single service” flows, and avoid using `&&` as requested.

Quick rebuild and start (all services)
- Go to the directory with your `docker-compose.yml`.
- Run:
  - `docker compose down ; docker compose build ; docker compose up -d ; docker compose ps`
- If you need a fresh build without cache:
  - `docker compose down ; docker compose build --no-cache ; docker compose up -d ; docker compose ps`
- If your host uses Compose v1, replace `docker compose` with `docker-compose`.

One-line rebuild on the fly
- Rebuild and start in one step:
  - `docker compose up -d --build ; docker compose ps`

Rebuild a single service
- Replace `<service>` with the service name in your compose file:
  - `docker compose stop <service> ; docker compose build <service> ; docker compose up -d <service> ; docker compose ps`
- Force container recreation without rebuilding:
  - `docker compose up -d --force-recreate <service> ; docker compose ps`

Choose compose file (if you use a non-default)
- If you need a specific compose file:
  - `docker compose -f docker-compose.yml up -d --build ; docker compose ps`
  - Or for local/dev: `docker compose -f docker-compose-local.yml up -d --build ; docker compose ps`

Verify and troubleshoot
- Tail logs for a specific service:
  - `docker compose logs -f --tail=100 <service>`
- Check container health:
  - `docker compose ps`
- If disk space is tight, prune unused images/containers (careful on production):
  - `docker system prune -f`

Repo-specific helpers (optional)
- Your project includes Linux deployment scripts under `scripts/linux/`. If you prefer scripted flows on the remote host:
  - `bash scripts/linux/__docker_deploy.sh`
  - `bash scripts/linux/__deploy_production.sh`
- These often wrap the compose build/up steps and may ensure envs and migrations are handled consistently.

Notes
- Ensure you run commands in the folder containing your `docker-compose.yml` and `.env`.
- If environment variables changed, verify that `.env` on the remote host is up-to-date before rebuilding.
- For Django-specific post-deploy tasks (migrations, static collection), you can run inside the web container:
  - `docker compose exec <web_service> python manage.py migrate ; docker compose exec <web_service> python manage.py collectstatic --noinput`

If you share which service(s) changed or which compose file you use on the remote, I can tailor exact commands for your setup.
        