
import os
import sys
import django
from django.db import connection

sys.path.append(os.getcwd())
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "votebem.settings.production")
django.setup()

def drop_tables():
    tables = [
        'voting_voto',
        'voting_referencia',
        'voting_congressmanvote',
        'voting_votacaovotebem',
        'voting_proposicaotema',
        'voting_proposicaovotacao',
        'voting_proposicao',
    ]
    with connection.cursor() as cursor:
        print("Disabling FK checks...")
        cursor.execute("SET FOREIGN_KEY_CHECKS = 0;")
        for table in tables:
            print(f"Dropping {table}...")
            try:
                cursor.execute(f"DROP TABLE IF EXISTS {table}")
                print(f"Dropped {table}.")
            except Exception as e:
                print(f"Error dropping {table}: {e}")
        print("Enabling FK checks...")
        cursor.execute("SET FOREIGN_KEY_CHECKS = 1;")

if __name__ == "__main__":
    drop_tables()
