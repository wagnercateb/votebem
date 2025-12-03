- Explicar uso de docker-compose-local.yml vs docker-compose.yml

# Compose Files: Quando Cada Um É Usado

- Local (Windows): você escolhe explicitamente o arquivo ao subir os serviços.
  - Banco e cache locais: docker compose -f docker-compose-local.yml up -d db ; docker compose -f docker-compose-local.yml up -d valkey
  - O app Django roda fora do Docker via python manage.py runserver ou pelo run_server.py , usando votebem.settings.development .
- VPS (produção): o arquivo é docker-compose.yml executado no servidor.
  - Sobe db , valkey e web com docker compose -f docker-compose.yml up -d
  - O serviço web roda Gunicorn e usa .env como env_file . Ele executa:
    - python manage.py migrate --settings=votebem.settings.production
    - python manage.py collectstatic --settings=votebem.settings.production
    - gunicorn ... votebem.wsgi:application , com DJANGO_SETTINGS_MODULE vindo do .env .

# Como o settings é escolhido (Windows x VPS)

- Local (Windows, host): manage.py define por padrão DJANGO_SETTINGS_MODULE='votebem.settings.development' . Então runserver usa sempre desenvolvimento, salvo se você passar --settings ou definir DJANGO_SETTINGS_MODULE no ambiente.
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
  - O manage.py usa votebem.settings.development ; o settings.development agora está explicitamente HTTP-only.

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
  - DJANGO_SETTINGS_MODULE=votebem.settings.development
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
