from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone

class Proposicao(models.Model):
    """Model for political propositions from Camara dos Deputados"""
    # Make id_proposicao the primary key for the table
    id_proposicao = models.IntegerField(primary_key=True, verbose_name="ID da Proposição")
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

class ProposicaoVotacao(models.Model):
    """Votações oficiais associadas a uma proposição (1-N).

    Armazena o identificador de votação (sufixo) e sua descrição para cada proposição.
    Exemplo: proposicao_id=2270800 possui votações 175, 160 e 135.
    """
    # Explicitly reference Proposicao by its new primary key id_proposicao
    proposicao = models.ForeignKey(
        Proposicao,
        to_field='id_proposicao',
        on_delete=models.CASCADE,
        related_name='votacoes_oficiais',
        verbose_name='Proposição'
    )
    votacao_sufixo = models.IntegerField(verbose_name='ID da Votação (sufixo)')
    descricao = models.TextField(blank=True, null=True, verbose_name='Descrição da Votação')
    # Prioridade de exibição/ordem para esta votação da proposição (opcional)
    prioridade = models.IntegerField(blank=True, null=True, verbose_name='Prioridade')
    # Campos de contagem oficial devem residir aqui e não em VotacaoDisponivel
    # Eles são populados somente quando os dados oficiais são buscados
    sim_oficial = models.IntegerField(default=0, verbose_name="Votos SIM Oficiais")
    nao_oficial = models.IntegerField(default=0, verbose_name="Votos NÃO Oficiais")
    # Data/Hora do registro da votação na API (dados oficiais)
    data_votacao = models.DateTimeField(blank=True, null=True, verbose_name="Data/Hora do Registro da Votação")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Votação da Proposição'
        verbose_name_plural = 'Votações da Proposição'
        unique_together = ['proposicao', 'votacao_sufixo']
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.proposicao.id_proposicao}-{self.votacao_sufixo}"

class VotacaoVoteBem(models.Model):
    """Model for available voting sessions"""
    # Link directly to a specific official voting entry for the proposição
    proposicao_votacao = models.ForeignKey(
        'voting.ProposicaoVotacao',
        on_delete=models.CASCADE,
        blank=True,
        null=True,
        related_name='votacaovotebem',
        verbose_name="Votação da Proposição"
    )
    titulo = models.CharField(max_length=500, verbose_name="Título da Votação")
    resumo = models.TextField(verbose_name="Resumo")
    data_hora_votacao = models.DateTimeField(verbose_name="Data/Hora da Votação Original")
    no_ar_desde = models.DateTimeField(verbose_name="No Ar Desde")
    no_ar_ate = models.DateTimeField(blank=True, null=True, verbose_name="No Ar Até")
    ativo = models.BooleanField(default=True, verbose_name="Ativo")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Votação VoteBem"
        verbose_name_plural = "Votações VoteBem"
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
        # Reverse relation uses related_name='voto' (not the default 'voto_set')
        return self.voto.count()
    
    def get_votos_sim_populares(self):
        """Get popular SIM votes count"""
        # Count related votes with value 'SIM' via related_name='voto'
        return self.voto.filter(voto='SIM').count()
    
    def get_votos_nao_populares(self):
        """Get popular NÃO votes count"""
        # Count related votes with value 'NAO' via related_name='voto'
        return self.voto.filter(voto='NAO').count()

class Voto(models.Model):
    """Model for individual votes"""
    VOTO_CHOICES = [
        ('SIM', 'Sim'),
        ('NAO', 'Não'),
        ('ABSTENCAO', 'Abstenção'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name="Usuário")
    votacao = models.ForeignKey(VotacaoVoteBem, on_delete=models.CASCADE, related_name='voto', verbose_name="Votação")
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
    # Tie the vote to a specific official voting of a proposição
    proposicao_votacao = models.ForeignKey(
        'voting.ProposicaoVotacao',
        on_delete=models.CASCADE,
        blank=True,
        null=True,
        verbose_name="Votação da Proposição"
    )
    voto = models.IntegerField(choices=VOTO_CHOICES, blank=True, null=True, verbose_name="Voto")
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = "Voto do Congressista"
        verbose_name_plural = "Votos dos Congressistas"
        unique_together = ['congressman', 'proposicao_votacao']
        ordering = ['-created_at']
    
    def __str__(self):
        voto_display = self.get_voto_display() if self.voto is not None else "Não Compareceu"
        try:
            titulo = self.proposicao_votacao.proposicao.titulo[:30]
        except Exception:
            titulo = "Proposição"
        return f"{self.congressman.nome} - {voto_display} em {titulo}"
    
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

# ------------------------------------------------------------
# Temas (referências oficiais de temas de proposições)
# - Table name must be exactly 'voting_temas'
# - Fields:
#   - codigo: integer code from Câmara API (e.g., 34, 35, ...)
#   - nome: textual name of the theme
#   - descricao: textual description (often empty in the source)
# ------------------------------------------------------------
class Tema(models.Model):
    # 'codigo' é o identificador oficial (Câmara) e passa a ser a PK
    # Tornando-o primary_key, o Django deixará de criar o campo 'id' automático
    codigo = models.IntegerField(primary_key=True)
    nome = models.TextField()
    descricao = models.TextField(blank=True, null=True)

    class Meta:
        db_table = 'voting_temas'
        verbose_name = 'Tema'
        verbose_name_plural = 'Temas'

    def __str__(self):
        return f"{self.codigo} - {self.nome}"

# ------------------------------------------------------------
# N:N entre Proposição e Tema (voting_proposicao_tema)
# - Armazena vínculos dos códigos de tema (codTema) às proposições.
# - Usa ForeignKey para Proposicao (to_field=id_proposicao) e
#   Tema (to_field=codigo) com colunas explícitas solicitadas.
# ------------------------------------------------------------
class ProposicaoTema(models.Model):
    proposicao = models.ForeignKey(
        Proposicao,
        to_field='id_proposicao',
        on_delete=models.CASCADE,
        db_column='proposicao_id',
        verbose_name='Proposição'
    )
    tema = models.ForeignKey(
        Tema,
        to_field='codigo',
        on_delete=models.CASCADE,
        db_column='tema_id',
        verbose_name='Tema (código)'
    )

    class Meta:
        db_table = 'voting_proposicao_tema'
        unique_together = ['proposicao', 'tema']
        verbose_name = 'Proposição-Tema'
        verbose_name_plural = 'Proposições-Temas'

    def __str__(self):
        return f"Prop {self.proposicao_id} ⇄ Tema {self.tema_id}"


# ------------------------------------------------------------
# Referências externas relacionadas a uma votação de proposição
# - Tabela deve se chamar exatamente 'voting_referencias'
# - Relação 1:N com ProposicaoVotacao (uma votação pode ter várias referências)
# - Armazena URL e um código/enum para o tipo da referência
#   (web_page, sound, social_media)
# ------------------------------------------------------------
class Referencia(models.Model):
    class Kind(models.TextChoices):
        # Tipos de referência suportados
        WEB_PAGE = 'web_page', 'Página Web'
        SOUND = 'sound', 'Áudio'
        SOCIAL_MEDIA = 'social_media', 'Rede Social'

    # Vínculo obrigatório à votação oficial da proposição (1:N)
    proposicao_votacao = models.ForeignKey(
        'voting.ProposicaoVotacao',
        on_delete=models.CASCADE,
        related_name='referencias',
        verbose_name='Votação da Proposição'
    )

    # URL de referência (pode ser longa; validação básica via URLField)
    url = models.URLField(max_length=500, verbose_name='URL da Referência')

    # Código do tipo da referência (choices)
    kind = models.CharField(
        max_length=20,
        choices=Kind.choices,
        verbose_name='Tipo da Referência'
    )

    # Metadados comuns
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'voting_referencias'
        verbose_name = 'Referência de Votação'
        verbose_name_plural = 'Referências de Votação'
        ordering = ['-created_at']
        indexes = [
            # Índice para consultas por votação
            models.Index(fields=['proposicao_votacao']),
            # Índice para filtros por tipo
            models.Index(fields=['kind']),
        ]

    def __str__(self):
        try:
            pv = self.proposicao_votacao
            return f"Ref[{self.get_kind_display()}] {pv.proposicao.id_proposicao}-{pv.votacao_sufixo}"
        except Exception:
            return f"Ref[{self.get_kind_display()}] {self.url}"
