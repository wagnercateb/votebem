from django.db import models
from django.contrib.auth.models import User
from voting.models import Proposicao

class Enquete(models.Model):
    """Model for user-created polls/surveys about propositions"""
    ESTADO_CHOICES = [
        (5, 'Rascunho'),
        (10, 'Publicada'),
        (15, 'Arquivada'),
    ]
    
    autor = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name="Autor")
    proposicao = models.ForeignKey(Proposicao, on_delete=models.CASCADE, verbose_name="Proposição")
    titulo = models.CharField(max_length=500, verbose_name="Título")
    pergunta = models.TextField(verbose_name="Pergunta")
    descricao = models.TextField(blank=True, null=True, verbose_name="Descrição")
    estado = models.IntegerField(choices=ESTADO_CHOICES, default=5, verbose_name="Estado")
    criada_em = models.DateTimeField(auto_now_add=True)
    atualizada_em = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Enquete"
        verbose_name_plural = "Enquetes"
        ordering = ['estado', 'criada_em']
    
    def __str__(self):
        return f"Enquete: {self.titulo[:50]} - {self.autor.username}"
    
    def is_published(self):
        return self.estado == 10
    
    def get_total_respostas(self):
        """Get total responses for this poll"""
        return self.respostaenquete_set.count()
    
    def get_respostas_sim(self):
        """Get SIM responses count"""
        return self.respostaenquete_set.filter(resposta='SIM').count()
    
    def get_respostas_nao(self):
        """Get NÃO responses count"""
        return self.respostaenquete_set.filter(resposta='NAO').count()
    
    def get_percentual_sim(self):
        """Get percentage of SIM responses"""
        total = self.get_total_respostas()
        if total == 0:
            return 0
        return round((self.get_respostas_sim() / total) * 100, 1)
    
    def get_percentual_nao(self):
        """Get percentage of NÃO responses"""
        total = self.get_total_respostas()
        if total == 0:
            return 0
        return round((self.get_respostas_nao() / total) * 100, 1)

class RespostaEnquete(models.Model):
    """Model for poll responses"""
    RESPOSTA_CHOICES = [
        ('SIM', 'Sim'),
        ('NAO', 'Não'),
        ('NEUTRO', 'Neutro'),
    ]
    
    enquete = models.ForeignKey(Enquete, on_delete=models.CASCADE, verbose_name="Enquete")
    user = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name="Usuário")
    resposta = models.CharField(max_length=10, choices=RESPOSTA_CHOICES, verbose_name="Resposta")
    comentario = models.TextField(blank=True, null=True, verbose_name="Comentário")
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = "Resposta da Enquete"
        verbose_name_plural = "Respostas das Enquetes"
        unique_together = ['enquete', 'user']  # One response per user per poll
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.user.username} - {self.resposta} em {self.enquete.titulo[:30]}"
