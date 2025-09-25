from django.db import models
from django.contrib.auth.models import AbstractUser
from django.contrib.auth.models import User

class UserProfile(models.Model):
    """Extended user profile to store additional user information"""
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    uf = models.CharField(max_length=2, blank=True, null=True, verbose_name="Estado")
    votos_gravados = models.TextField(blank=True, null=True, verbose_name="Votações Registradas")
    pontos_ranking = models.IntegerField(default=0, verbose_name="Pontos de Ranking")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Perfil do Usuário"
        verbose_name_plural = "Perfis dos Usuários"
    
    def __str__(self):
        return f"Perfil de {self.user.username}"
    
    def get_votos_list(self):
        """Returns list of vote IDs from votos_gravados string"""
        if self.votos_gravados:
            return [int(x) for x in self.votos_gravados.split('.') if x.isdigit()]
        return []
    
    def add_voto(self, voto_id):
        """Add a vote ID to the votos_gravados string"""
        if not self.votos_gravados:
            self.votos_gravados = ''
        self.votos_gravados += f'{voto_id}.'
        self.save()
