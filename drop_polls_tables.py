
import os
import sys
import django
from django.db import connection

sys.path.append(os.getcwd())
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "votebem.settings.production")
django.setup()

def drop_polls_tables():
    tables = [
        'polls_respostaenquete',
        'polls_enquete',
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
        
        print("Deleting migration history for 'polls' app...")
        cursor.execute("DELETE FROM django_migrations WHERE app = 'polls';")
        print("Deleted migration history.")
        
        print("Enabling FK checks...")
        cursor.execute("SET FOREIGN_KEY_CHECKS = 1;")

if __name__ == "__main__":
    drop_polls_tables()
