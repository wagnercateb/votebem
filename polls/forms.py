from django import forms
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Submit, Row, Column, Field
from .models import Enquete, RespostaEnquete
from voting.models import Proposicao

class EnqueteForm(forms.ModelForm):
    """Form for creating and editing enquetes"""
    
    class Meta:
        model = Enquete
        fields = ['proposicao', 'titulo', 'pergunta', 'descricao', 'estado']
        widgets = {
            'titulo': forms.TextInput(attrs={'placeholder': 'Título da enquete'}),
            'pergunta': forms.TextInput(attrs={'placeholder': 'Pergunta principal'}),
            'descricao': forms.Textarea(attrs={'rows': 4, 'placeholder': 'Descrição detalhada da enquete'}),
        }
        labels = {
            'proposicao': 'Proposição',
            'titulo': 'Título',
            'pergunta': 'Pergunta',
            'descricao': 'Descrição',
            'estado': 'Status',
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.layout = Layout(
            Row(
                Column('proposicao', css_class='form-group col-md-6 mb-0'),
                Column('estado', css_class='form-group col-md-6 mb-0'),
                css_class='form-row'
            ),
            'titulo',
            'pergunta',
            'descricao',
            Submit('submit', 'Salvar Enquete', css_class='btn btn-primary')
        )
        
        # Filter proposicoes to only show active ones
        self.fields['proposicao'].queryset = Proposicao.objects.filter(ativa=True)
        self.fields['proposicao'].empty_label = "Selecione uma proposição"

class RespostaEnqueteForm(forms.ModelForm):
    """Form for responding to enquetes"""
    
    RESPOSTA_CHOICES = [
        ('SIM', 'Sim'),
        ('NAO', 'Não'),
        ('NEUTRO', 'Neutro'),
    ]
    
    resposta = forms.ChoiceField(
        choices=RESPOSTA_CHOICES,
        widget=forms.RadioSelect,
        label='Sua resposta'
    )
    
    class Meta:
        model = RespostaEnquete
        fields = ['resposta', 'comentario']
        widgets = {
            'comentario': forms.Textarea(attrs={'rows': 3, 'placeholder': 'Comentário opcional'}),
        }
        labels = {
            'comentario': 'Comentário (opcional)',
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.layout = Layout(
            Field('resposta', css_class='mb-3'),
            'comentario',
            Submit('submit', 'Enviar Resposta', css_class='btn btn-success')
        )