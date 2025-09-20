from django import forms
from .models import Voto

class VotoForm(forms.ModelForm):
    class Meta:
        model = Voto
        fields = ['voto']
        widgets = {
            'voto': forms.RadioSelect(choices=Voto.VOTO_CHOICES)
        }
        
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['voto'].widget.attrs.update({'class': 'form-check-input'})