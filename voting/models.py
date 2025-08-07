from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone

class Proposicao(models.Model):
    """Model for political propositions from Camara dos Deputados"""
    id_proposicao = models.IntegerField(unique=True, verbose_name="ID da Proposição")
    titulo = models.CharField(max_length=500, verbose_name="Título")
    ementa = models.TextField(verbose_name="Ementa")
    tipo = models.CharField(max_length=50, verbose_name="Tipo")
    numero = models.IntegerField(verbose_name="Número")
    ano = models.IntegerField(verbose_name="Ano")
    autor = models.CharField(max_length=200, blank=True, null=True, verbose_name="Autor")
    estado = models.CharField(max_length=100, blank=True, null=True, verbose_name="Estado")
    url_foto1 = models.URLField(blank=True, null=True, verbose_name="URL Foto 1")
    alt_foto1 = models.CharField(max_length=200, blank=True, null=True, verbose_name="Alt Foto 1")
    url_foto2 = models.URLField(blank=True, null=True, verbose_name="URL Foto 2")
    alt_foto2 = models.CharField(max_length=200, blank=True, null=True, verbose_name="Alt Foto 2")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Proposição"
        verbose_name_plural = "Proposições"
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.tipo} {self.numero}/{self.ano} - {self.titulo[:50]}"

class VotacaoDisponivel(models.Model):
    """Model for available voting sessions"""
    proposicao = models.ForeignKey(Proposicao, on_delete=models.CASCADE, verbose_name="Proposição")
    titulo = models.CharField(max_length=500, verbose_name="Título da Votação")
    resumo = models.TextField(verbose_name="Resumo")
    data_hora_votacao = models.DateTimeField(verbose_name="Data/Hora da Votação Original")
    no_ar_desde = models.DateTimeField(verbose_name="No Ar Desde")
    no_ar_ate = models.DateTimeField(blank=True, null=True, verbose_name="No Ar Até")
    sim_oficial = models.IntegerField(default=0, verbose_name="Votos SIM Oficiais")
    nao_oficial = models.IntegerField(default=0, verbose_name="Votos NÃO Oficiais")
    ativo = models.BooleanField(default=True, verbose_name="Ativo")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Votação Disponível"
        verbose_name_plural = "Votações Disponíveis"
        ordering = ['-no_ar_desde']
    
    def __str__(self):
        return f"Votação: {self.titulo[:50]}"
    
    def is_active(self):
        """Check if voting session is currently active"""
        now = timezone.now()
        if not self.ativo:
            return False
        if self.no_ar_ate and now > self.no_ar_ate:
            return False
        return now >= self.no_ar_desde
    
    def get_total_votos_populares(self):
        """Get total popular votes for this voting session"""
        return self.voto_set.count()
    
    def get_votos_sim_populares(self):
        """Get popular SIM votes count"""
        return self.voto_set.filter(voto='SIM').count()
    
    def get_votos_nao_populares(self):
        """Get popular NÃO votes count"""
        return self.voto_set.filter(voto='NAO').count()

class Voto(models.Model):
    """Model for individual votes"""
    VOTO_CHOICES = [
        ('SIM', 'Sim'),
        ('NAO', 'Não'),
        ('ABSTENCAO', 'Abstenção'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name="Usuário")
    votacao = models.ForeignKey(VotacaoDisponivel, on_delete=models.CASCADE, verbose_name="Votação")
    voto = models.CharField(max_length=10, choices=VOTO_CHOICES, verbose_name="Voto")
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = "Voto"
        verbose_name_plural = "Votos"
        unique_together = ['user', 'votacao']  # One vote per user per voting session
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.user.username} - {self.voto} em {self.votacao.titulo[:30]}"
