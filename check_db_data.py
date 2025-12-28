
import os
import sys
import django
from django.db import connection

# Add current directory to sys.path
sys.path.append(os.getcwd())

print("Starting script...", flush=True)

try:
    os.environ["DJANGO_SETTINGS_MODULE"] = "votebem.settings.production"
    django.setup()
    print("Django setup complete.", flush=True)
except Exception as e:
    print(f"Django setup failed: {e}", flush=True)
    sys.exit(1)

def check_data():
    try:
        with connection.cursor() as cursor:
            for table in ['voting_proposicao', 'voting_votacaovotebem']:
                print(f"--- {table} ---", flush=True)
                cursor.execute(f"SELECT count(*) FROM {table}")
                print(f"Count: {cursor.fetchone()[0]}", flush=True)
                
    except Exception as e:
        print(f"Error reading data: {e}", flush=True)

if __name__ == "__main__":
    check_data()
