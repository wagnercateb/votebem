from django.shortcuts import render, redirect
from django.conf import settings
from django.contrib import messages
import os
from decouple import config

def site_lock_view(request):
    if request.method == 'POST':
        password = request.POST.get('password')
        master_password = config('SITE_MASTER_PASSWORD', default='')
        
        if password == master_password:
            request.session['site_unlocked'] = True
            # Get the 'next' parameter or default to home
            next_url = request.GET.get('next', '/')
            # Prevent redirect loop if next is the lock page itself
            if 'site-lock' in next_url:
                next_url = '/'
            return redirect(next_url)
        else:
            messages.error(request, 'Senha incorreta.')
    
    return render(request, 'site_lock.html')
