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

class Congressman(models.Model):
    """Model for congressmen/deputies"""
    id_cadastro = models.IntegerField(unique=True, verbose_name="ID Cadastro")
    nome = models.CharField(max_length=200, verbose_name="Nome")
    partido = models.CharField(max_length=50, verbose_name="Partido")
    partidos_historico = models.TextField(blank=True, null=True, verbose_name="Partidos (histórico)")
    uf = models.CharField(max_length=2, verbose_name="UF")
    foto_url = models.URLField(blank=True, null=True, verbose_name="URL da Foto")
    ativo = models.BooleanField(default=True, verbose_name="Ativo")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Congressista"
        verbose_name_plural = "Congressistas"
        ordering = ['nome']
    
    def __str__(self):
        return f"{self.nome} ({self.partido}/{self.uf})"
    
    def get_foto_url(self):
        """Get congressman photo URL from Camara dos Deputados"""
        if self.foto_url:
            return self.foto_url
        return f"http://www.camara.gov.br/internet/deputado/bandep/{self.id_cadastro}.jpg"

class CongressmanVote(models.Model):
    """Model for congressman votes on propositions"""
    VOTO_CHOICES = [
        (1, 'Sim'),
        (-1, 'Não'),
        (0, 'Abstenção'),
        (None, 'Não Compareceu'),
    ]
    
    congressman = models.ForeignKey(Congressman, on_delete=models.CASCADE, verbose_name="Congressista")
    proposicao = models.ForeignKey(Proposicao, on_delete=models.CASCADE, verbose_name="Proposição")
    voto = models.IntegerField(choices=VOTO_CHOICES, blank=True, null=True, verbose_name="Voto")
    congress_vote_id = models.IntegerField(blank=True, null=True, verbose_name="ID Votação da Câmara")
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = "Voto do Congressista"
        verbose_name_plural = "Votos dos Congressistas"
        unique_together = ['congressman', 'proposicao']
        ordering = ['-created_at']
    
    def __str__(self):
        voto_display = self.get_voto_display() if self.voto is not None else "Não Compareceu"
        return f"{self.congressman.nome} - {voto_display} em {self.proposicao.titulo[:30]}"
    
    def get_voto_display_text(self):
        """Get human-readable vote display"""
        if self.voto is None:
            return "Não compareceu"
        elif self.voto == 0:
            return "Abstenção"
        elif self.voto == 1:
            return "Sim"
        elif self.voto == -1:
            return "Não"
        return "Desconhecido"
