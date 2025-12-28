
import os
import sys
import django
from django.conf import settings
from django.db import connection

sys.path.append(os.getcwd())
os.environ["DJANGO_SETTINGS_MODULE"] = "votebem.settings.production"
django.setup()

print(f"DB Name: {settings.DATABASES['default']['NAME']}", flush=True)

def clear_voting_migrations():
    with connection.cursor() as cursor:
        print("Deleting migration history for 'voting' app...", flush=True)
        cursor.execute("DELETE FROM django_migrations WHERE app = 'voting';")
        print(f"Deleted {cursor.rowcount} rows.", flush=True)

if __name__ == "__main__":
    clear_voting_migrations()
