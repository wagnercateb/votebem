
import os
import sys
import django
from django.db import connection

# Add current directory to sys.path so 'votebem' module can be found
sys.path.append(os.getcwd())

print("Starting script...")
print(f"Current DJANGO_SETTINGS_MODULE: {os.environ.get('DJANGO_SETTINGS_MODULE')}")

try:
    # Force settings module
    os.environ["DJANGO_SETTINGS_MODULE"] = "votebem.settings.production"
    print(f"Set DJANGO_SETTINGS_MODULE to: {os.environ.get('DJANGO_SETTINGS_MODULE')}")
    
    django.setup()
    print("Django setup complete.")
except Exception as e:
    print(f"Django setup failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

def check_schema():
    try:
        with connection.cursor() as cursor:
            tables = ['voting_proposicao', 'voting_referencia', 'voting_votacaovotebem']
            for table in tables:
                print(f"--- Schema for {table} ---")
                try:
                    cursor.execute(f"DESCRIBE {table}")
                    rows = cursor.fetchall()
                    for row in rows:
                        print(row)
                except Exception as e:
                    print(f"Error describing {table}: {e}")
    except Exception as e:
        print(f"Connection failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    check_schema()
