- Explicar uso de docker-compose-local.yml vs docker-compose.yml

# Compose Files: Quando Cada Um É Usado

- Local (Windows): você escolhe explicitamente o arquivo ao subir os serviços.
  - Banco e cache locais: docker compose -f docker-compose-local.yml up -d db ; docker compose -f docker-compose-local.yml up -d valkey
  - O app Django roda fora do Docker via python manage.py runserver ou pelo run_server.py , usando votebem.settings.production .
- VPS (produção): o arquivo é docker-compose.yml executado no servidor.
  - Sobe db , valkey e web com docker compose -f docker-compose.yml up -d
  - O serviço web roda Gunicorn e usa .env como env_file . Ele executa:
    - python manage.py migrate --settings=votebem.settings.production
    - python manage.py collectstatic --settings=votebem.settings.production
    - gunicorn ... votebem.wsgi:application , com DJANGO_SETTINGS_MODULE vindo do .env .

# Como o settings é escolhido (Windows x VPS)

- Local (Windows, host): manage.py define por padrão DJANGO_SETTINGS_MODULE='votebem.settings.production' . Então runserver usa sempre desenvolvimento, salvo se você passar --settings ou definir DJANGO_SETTINGS_MODULE no ambiente.
- Produção (VPS, containers):
  - O .env do projeto define DJANGO_SETTINGS_MODULE=votebem.settings.production (conforme .env.example ). O web container carrega esse .env e, junto com os comandos --settings=votebem.settings.production , garante que produção seja usado.
  - wsgi.py faz os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'votebem.settings') , mas o valor do .env tem precedência e aponta para votebem.settings.production


  ## Adicionei o arquivo /.env.dev 
  com variáveis para desenvolvimento, alinhadas ao stack local (MariaDB e Valkey via Docker Desktop), e com HTTPS desativado para evitar net::ERR_SSL_PROTOCOL_ERROR .

  ## Como usar no Windows (host)

- Rodar servidor Django com o script que já carrega .env.dev :
  - python run_server.py
- Alternativa direta:
  - python manage.py runserver 127.0.0.1:8000
  - O manage.py usa votebem.settings.production ; o settings.development agora está explicitamente HTTP-only.

  ## Como subir containers locais com este .env.dev

- MariaDB e Valkey:
  - docker compose -f docker-compose-local.yml --env-file .env.dev up -d db
  - docker compose -f docker-compose-local.yml --env-file .env.dev up -d valkey
- URLs e portas no .env.dev :
  - Banco: DB_HOST=127.0.0.1 DB_PORT=3306
  - Valkey: REDIS_URL=redis://127.0.0.1:6379/0
  - Se 6379 estiver ocupado (Memurai), mude para 6380 nos dois lugares:
    - REDIS_URL=redis://127.0.0.1:6380/0
    - Em docker-compose-local.yml , ajuste ports para 127.0.0.1:6380:6379

## Conteúdo principal de .env.dev

- Ambiente e segurança
  - DJANGO_SETTINGS_MODULE=votebem.settings.production
  - DEBUG=True
  - ALLOWED_HOSTS=localhost,127.0.0.1,0.0.0.0
  - USE_HTTPS=False
  - SECURE_SSL_REDIRECT=False
- Banco de Dados
  - DB_NAME=votebem_db
  - DB_USER=votebem_user
  - DB_PASSWORD=votebem_dev_password
  - DB_ROOT_PASSWORD=votebem_dev_root_password
  - DB_HOST=127.0.0.1
  - DB_PORT=3306
- Redis/Valkey
  - REDIS_URL=redis://127.0.0.1:6379/0
- CORS local
  - CORS_ALLOWED_ORIGINS=http://localhost:8000,http://127.0.0.1:8000

## Notas e próximos passos

- Se você já tem dados no MariaDB local, mantenha DB_NAME/USER/PASSWORD conforme usados anteriormente para não quebrar acesso. Caso tenha dúvidas, eu alinjo as credenciais ao que está no seu container.
- Caso veja qualquer redirecionamento para HTTPS (por HSTS “memorizado” no navegador), acesse pelo http://localhost:8000 ou limpe HSTS para 127.0.0.1 no navegador.


---------

# Q&A

## i have delete records from the local MariaDB votebem_db database. where are records of http://localhost:8000/gerencial/votacoes/management/ coming from?

Short answer: those records come from the `VotacaoVoteBem` table in whatever database your Django app is actually connected to. In your current setup, that’s likely not `votebem_db`.

Why you still see records after deleting from MariaDB

- Your server uses the `votebem.settings.production` settings module (set in `manage.py`).
- In `votebem/settings/development.py`, the app tries to connect to MariaDB using environment variables (`DB_HOST`, `DB_PORT`, `DB_USER`, `DB_PASSWORD`, `DB_NAME`). If the connection fails, it silently falls back to SQLite at `votebem/db.sqlite3`.
- The defaults in development settings use `DB_NAME='votebem_db'`. If you deleted data from `votebem_db` but the app is pointing at `votebem_outro_nome` (or fell back to SQLite), your deletions won’t affect what you see.

Where the management page pulls data from
- View: `voting/admin_views.py::votacoes_management`
- Query: `VotacaoVoteBem.objects.select_related('proposicao_votacao__proposicao').order_by('-created_at')`
- Template: `templates/admin/voting/votacoes_management.html`
- So it’s reading live rows from the configured DB and showing them with related `Proposicao` info.

How to verify which DB is active
- Check the server console output for “MariaDB not available, using SQLite database” messages; this is logged by `dev_log` in the development settings fallback.
- Inspect the DB config in a Django shell:
  - Run: `python manage.py shell -c "from django.conf import settings; print(settings.DATABASES)"` 
  - If you see `ENGINE='django.db.backends.sqlite3'` and a path like `votebem/db.sqlite3`, you’re on SQLite.
  - If you see `ENGINE='django.db.backends.mysql'` with `NAME='votebem_dev'` (or another name), you’re on MariaDB — but possibly the wrong DB name.

How to point the app at `votebem_db`
- Create a `.env` file in the project root (alongside `manage.py`) using `.env.example` as a base.
- Set variables to match your local MariaDB:
  - `DB_HOST=127.0.0.1`
  - `DB_PORT=3306`
  - `DB_USER=<your_user>`
  - `DB_PASSWORD=<your_password>`
  - `DB_NAME=votebem_db`
- Restart the dev server so it picks up the environment.
- Optional: remove `votebem/db.sqlite3` to avoid accidental fallback masking issues.
- Run migrations on the target DB: `python manage.py migrate`.

If after switching you still see records
- Confirm you didn’t have a second DB with data (e.g., `votebem_dev`) and that your credentials are connecting to `votebem_db`.
- Ensure MariaDB is running and accessible from your host.
- Check if any import scripts (e.g., `scripts/linux/import_dummy_data.py`) have been run against your current DB and repopulated it.

If you want, tell me the current `settings.DATABASES` output and I’ll confirm exactly which database your app is reading from.
        







## Onde é definido qual .env é usado ?
          
Short answer: both `development.py` and `production.py` read from the same source of environment variables via `python-decouple`. Decouple first checks OS environment variables, and if a variable isn’t set there, it looks for a `.env` file in the current working directory. In your setup, the `.env` sitting next to `manage.py` is the one being used, because the server is started with the project root as the working directory.

Key points
- Settings selection: `manage.py` sets `DJANGO_SETTINGS_MODULE` to `votebem.settings.production`, so the server uses `votebem/settings/development.py`. In production, you would start the server with `DJANGO_SETTINGS_MODULE=votebem.settings.production` (isso está em docker-compose.yml > services > web > command)
- Env resolution order: `from decouple import config` reads
  - OS environment variables first,
  - then falls back to values in `.env` in the current working directory,
  - finally uses any `default=...` you provided in code.
- `.env` location: With the default `decouple.config`, the `.env` file is discovered in the process’s current working directory. Since the server runs from `c:\Users\User\Dados\Tecnicos\HardESoftware\EmDesenvolvimento\VotoBomPython\django_votebem`, the `.env` next to `manage.py` is used.
- Database fallback: `development.py` tries MariaDB with values from env (`DB_HOST`, `DB_PORT`, `DB_USER`, `DB_PASSWORD`, `DB_NAME`). If it can’t connect, it logs a message and falls back to SQLite (`BASE_DIR / 'db.sqlite3'`). So if your `.env` has wrong credentials or MariaDB is down, you’ll be on SQLite even if the `.env` exists.

How to use different .env per environment
- OS env override: Set variables in the OS (or via your process manager/docker-compose). These win over `.env`.
- Different `.env` files: If you want a non-default path (e.g., `.env.production`), you need to use `decouple.AutoConfig` or `Config(RepositoryEnv('path'))` explicitly in settings, for example:
  - `from decouple import AutoConfig`
  - `config = AutoConfig(search_path='/absolute/path/to/envdir')`
  - Then replace uses of `from decouple import config` with the `config` you defined.
- Separate processes: Run your production process with a different working directory that contains the intended `.env`, or set `DJANGO_SETTINGS_MODULE` and environment variables as part of the service definition.

Quick verification
- Print DB config in the running environment:
  - `python manage.py shell -c "from django.conf import settings; print(settings.DATABASES)"`
- Check whether MariaDB or SQLite is in use:
  - If you see `ENGINE='django.db.backends.mysql'` and your intended `NAME`, you’re on MariaDB.
  - If you see `ENGINE='django.db.backends.sqlite3'` and `db.sqlite3`, you’re on SQLite.
- Confirm variable resolution:
  - `python manage.py shell -c "from decouple import config; print(config('DB_USER', default='not-set'))"`

Common gotchas
- Running from a different directory: If you start Django from another cwd, decouple may not find the `.env` next to `manage.py`.
- Docker/compose: Environment variables supplied by Docker/compose override `.env`.
- Typos and defaults: If a key is misspelled in `.env`, `config('KEY', default='...')` will silently use the default, potentially masking configuration issues.

If you want, I can wire `AutoConfig` in settings to point at a specific `.env` path so there’s no ambiguity, or help inspect your current `DATABASES` live to verify it’s reading from the intended `.env`.
        















## Database password
          
**Short Answer**
Yes, you can (and should) reset the MariaDB user’s password directly in the database. If your MariaDB runs in a Docker container, doing it inside the container is typically the most straightforward. After resetting, update your app’s `.env` with the new password and restart the Django server.

**Choose Your Path**
- If MariaDB runs in Docker: reset the password inside the DB container.
- If MariaDB runs locally (Windows service): reset via the `mysql/mariadb` client as `root` (or another account with `ALTER USER` privilege).

**Docker Container**
- Find the container name:
  - PowerShell: `docker ps`
  - Identify the MariaDB container (often named `db`, `mariadb`, or similar).
- Enter the container:
  - `docker exec -it <container_name> bash` 
  - If `bash` isn’t available: `docker exec -it <container_name> sh`
- Connect as `root`:
  - `mariadb -u root -p` (or `mysql -u root -p`)
  - Enter the root password. If you don’t know it, check compose env or logs:
    - `docker inspect <container_name>`; look under `Config.Env` for `MARIADB_ROOT_PASSWORD` or `MYSQL_ROOT_PASSWORD`
    - `docker logs <container_name>` may show the initialization info
- Reset the application user’s password:
  - First, see which host entry your user has:
    - `SELECT Host, User FROM mysql.user WHERE User='votebem_user';`
  - Update the password for each matching host (commonly `'localhost'` and `'%'`):
    - `ALTER USER 'votebem_user'@'localhost' IDENTIFIED BY 'NEW_STRONG_PASSWORD';`
    - `ALTER USER 'votebem_user'@'%' IDENTIFIED BY 'NEW_STRONG_PASSWORD';`
    - `FLUSH PRIVILEGES;`
- Optional one‑liner (without an interactive session):
  - `docker exec -i <container_name> mariadb -uroot -p<ROOT_PASSWORD> -e "ALTER USER 'votebem_user'@'localhost' IDENTIFIED BY 'NEW_STRONG_PASSWORD'; ALTER USER 'votebem_user'@'%' IDENTIFIED BY 'NEW_STRONG_PASSWORD'; FLUSH PRIVILEGES;"`

**Local MariaDB (no Docker)**
- Open a terminal and connect as `root`:
  - `mariadb -u root -p` (or `mysql -u root -p`)
- Run the same SQL statements as above to alter the user and flush privileges.
- If you don’t know the root password, you can temporarily start MariaDB with `--skip-grant-tables` to reset it, but that’s more involved; I can walk you through it if needed.

**Update Django Configuration**
- Add or update DB variables in `c:\Users\User\Dados\Tecnicos\HardESoftware\EmDesenvolvimento\VotoBomPython\django_votebem\.env`:
  - `DB_NAME=votebem_db`
  - `DB_USER=votebem_user`
  - `DB_PASSWORD=NEW_STRONG_PASSWORD`
  - `DB_HOST=127.0.0.1` (or your container service name if Django connects via Docker networking)
  - `DB_PORT=3306`
- Note: Your `.env` currently sets `DJANGO_SETTINGS_MODULE=votebem.settings.production`. That means production settings load, and they will read these `DB_*` values via `python-decouple`. If you intend to use development settings, change this to `votebem.settings.production`.

**Verify**
- In DBeaver: Edit Connection → set the new password → Test Connection.
- In Django:
  - Restart the server so settings reload.
  - Run a quick check: `python manage.py migrate` to confirm DB connectivity.
  - Alternatively, open any page that hits the DB (e.g., `/gerencial/votacoes/management/`) to ensure it loads.

**Important Notes**
- Compose env vars like `MARIADB_USER` and `MARIADB_PASSWORD` only apply at initial container initialization. Changing them later doesn’t update existing DB users if the data is persisted in a Docker volume. Use `ALTER USER` as shown.
- If you recreated the DB container but kept the volume, the old password persists. Reset in the DB; don’t rely on changing compose env to overwrite it.
- If you prefer, share:
  - Whether DB runs in Docker or locally,
  - The MariaDB user shown in DBeaver’s connection,
  - The container name (if using Docker),
  and I’ll give you exact, copy‑paste commands tailored to your setup.
        