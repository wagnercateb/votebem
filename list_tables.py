
import os
import sys
import django
from django.db import connection

sys.path.append(os.getcwd())
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "votebem.settings.production")
django.setup()

def list_voting_tables():
    print(f"DB Name: {django.conf.settings.DATABASES['default']['NAME']}")
    with connection.cursor() as cursor:
        cursor.execute("SHOW TABLES")
        tables = cursor.fetchall()
        print(f"Found {len(tables)} tables.")
        for table in tables:
            if 'voting' in table[0]:
                print(table[0])

if __name__ == "__main__":
    list_voting_tables()
