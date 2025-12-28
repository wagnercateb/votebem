
import os
import sys
import django
from django.db import connection

sys.path.append(os.getcwd())
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "votebem.settings.production")
django.setup()

def check_referencias():
    with connection.cursor() as cursor:
        cursor.execute("SELECT id, proposicao_votacao_id, kind, url FROM voting_referencias WHERE id IN (33, 34)")
        rows = cursor.fetchall()
        print("Records 33 and 34:")
        for row in rows:
            print(row)
            
        cursor.execute("SELECT COUNT(*) FROM voting_referencias WHERE proposicao_votacao_id = 956")
        count = cursor.fetchone()[0]
        print(f"\nTotal references for proposicao_votacao_id=956: {count}")

        if count > 0:
            cursor.execute("SELECT id, kind, url FROM voting_referencias WHERE proposicao_votacao_id = 956")
            rows = cursor.fetchall()
            print("References for 956:")
            for row in rows:
                print(row)

if __name__ == "__main__":
    check_referencias()
