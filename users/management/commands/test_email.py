from django.core.management.base import BaseCommand
from django.core.mail import send_mail, get_connection
from django.conf import settings
import smtplib
import socket

class Command(BaseCommand):
    help = 'Test email sending configuration with debug output'

    def add_arguments(self, parser):
        parser.add_argument('to_email', type=str, nargs='?', help='Email address to send the test message to')

    def handle(self, *args, **options):
        # Allow command line argument, default to EMAIL_HOST_USER if not provided
        to_email = options['to_email']
        
        if not to_email:
            self.stdout.write(self.style.WARNING(f"No recipient specified. Defaulting to sender: {settings.EMAIL_HOST_USER}"))
            to_email = settings.EMAIL_HOST_USER

        if not to_email:
             self.stdout.write(self.style.ERROR('No target email provided and EMAIL_HOST_USER is empty.'))
             return

        self.stdout.write(f"Attempting to send email to: {to_email}")
        self.stdout.write("Configuration:")
        self.stdout.write(f"  EMAIL_HOST: {settings.EMAIL_HOST}")
        self.stdout.write(f"  EMAIL_PORT: {settings.EMAIL_PORT}")
        self.stdout.write(f"  EMAIL_USE_TLS: {settings.EMAIL_USE_TLS}")
        self.stdout.write(f"  EMAIL_HOST_USER: {settings.EMAIL_HOST_USER}")
        self.stdout.write(f"  DEFAULT_FROM_EMAIL: {settings.DEFAULT_FROM_EMAIL}")
        
        try:
            # Create a connection with debug enabled
            connection = get_connection()
            # 1 = print SMTP interaction to stdout
            # Note: Django's SMTP backend uses python's smtplib, but exposing set_debuglevel 
            # might require accessing the underlying 'connection' property which is created on open()
            # Easier way is to subclass or just do it manually if send_mail doesn't expose it easily.
            # Actually, we can manually manage the connection opening.
            
            # Using standard smtplib for clear debug output if django wrapper hides it
            self.stdout.write("\n--- SMTP Debug Log ---")
            
            # We try using Django's send_mail first but with a custom backend wrapper or just manual open
            connection.open()
            # The underlying python smtp object is connection.connection
            if hasattr(connection, 'connection') and connection.connection:
                connection.connection.set_debuglevel(1)
            
            send_mail(
                subject='VoteBem - Teste de Email (Debug)',
                message=f'Este é um email de teste para verificar a configuração SMTP.\nEnviado para: {to_email}',
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[to_email],
                fail_silently=False,
                connection=connection
            )
            connection.close()
            
            self.stdout.write("\n----------------------")
            self.stdout.write(self.style.SUCCESS('Email sent successfully!'))
            self.stdout.write(self.style.WARNING('If the email does not arrive, check:'))
            self.stdout.write('1. Spam/Junk folder.')
            self.stdout.write('2. SPF/DKIM records for your domain (votebem.online).')
            self.stdout.write('3. Zoho Mail "Sent" folder to see if it was saved there.')
            
        except smtplib.SMTPAuthenticationError as e:
            self.stdout.write(self.style.ERROR(f'SMTP Authentication Error: {e}'))
            self.stdout.write(self.style.WARNING('Check your EMAIL_HOST_USER and EMAIL_HOST_PASSWORD.'))
        except smtplib.SMTPConnectError as e:
            self.stdout.write(self.style.ERROR(f'SMTP Connection Error: {e}'))
            self.stdout.write(self.style.WARNING('Check EMAIL_HOST and EMAIL_PORT.'))
        except socket.gaierror as e:
            self.stdout.write(self.style.ERROR(f'DNS Error: {e}'))
            self.stdout.write(self.style.WARNING('Could not resolve EMAIL_HOST.'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'An unexpected error occurred: {type(e).__name__}: {e}'))
            import traceback
            self.stdout.write(traceback.format_exc())
