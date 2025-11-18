from django import forms
from .models import Voto

class VotoForm(forms.ModelForm):
    class Meta:
        model = Voto
        fields = ['voto', 'peso']
        widgets = {
            'voto': forms.RadioSelect(choices=Voto.VOTO_CHOICES),
            'peso': forms.RadioSelect(choices=((1, 'normal (1 ponto)'), (3, 'muito (3 pontos)'), (8, 'crucial (8 pontos)'))),
        }
        
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['voto'].widget.attrs.update({'class': 'form-check-input'})
        self.fields['peso'].widget.attrs.update({'class': 'form-check-input'})