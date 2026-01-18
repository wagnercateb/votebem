
import os
import django
from django.conf import settings

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'votebem.settings.production')
django.setup()

from users.forms import EmailAuthenticationForm

form = EmailAuthenticationForm(request=None, data={'username': 'vava', 'password': 'somepassword'})
print(f"Is valid: {form.is_valid()}")
if not form.is_valid():
    print(f"Errors: {form.errors}")
