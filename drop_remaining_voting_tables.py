
import os
import sys
import django
from django.db import connection

sys.path.append(os.getcwd())
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "votebem.settings.production")
django.setup()

def drop_remaining():
    tables = [
        'voting_congressman',
        'voting_proposicao_tema',
        'voting_referencias',
        'voting_temas'
    ]
    with connection.cursor() as cursor:
        print("Disabling FK checks...")
        cursor.execute("SET FOREIGN_KEY_CHECKS = 0;")
        for table in tables:
            print(f"Dropping {table}...")
            cursor.execute(f"DROP TABLE IF EXISTS {table}")
            print(f"Dropped {table}.")
        print("Enabling FK checks...")
        cursor.execute("SET FOREIGN_KEY_CHECKS = 1;")

if __name__ == "__main__":
    drop_remaining()
