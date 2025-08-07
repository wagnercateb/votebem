# VoteBem - Sistema de Votação Popular

Um sistema web desenvolvido em Django para permitir que cidadãos participem de votações populares sobre proposições legislativas e criem enquetes sobre temas de interesse público.

## 🚀 Funcionalidades

### Sistema de Votação
- **Votações Populares**: Visualize e vote em proposições legislativas
- **Estatísticas em Tempo Real**: Acompanhe os resultados das votações
- **Comparação com Resultados Oficiais**: Compare votos populares com resultados oficiais
- **Histórico de Votações**: Acesse votações anteriores e seus resultados

### Sistema de Enquetes
- **Criação de Enquetes**: Usuários podem criar enquetes sobre diversos temas
- **Enquetes Relacionadas**: Vincule enquetes a proposições específicas
- **Respostas com Comentários**: Permita respostas detalhadas com comentários opcionais
- **Estatísticas Detalhadas**: Visualize distribuição de respostas e análises

### Sistema de Usuários
- **Cadastro e Autenticação**: Sistema completo de registro e login
- **Perfis de Usuário**: Gerencie informações pessoais e avatar
- **Sistema de Ranking**: Ranking baseado em participação e engajamento
- **Pontuação por Atividade**: Ganhe pontos por votos, enquetes e participação

## 🛠️ Tecnologias Utilizadas

- **Backend**: Django 4.2.23
- **Frontend**: Bootstrap 5 + Bootstrap Icons
- **Formulários**: Django Crispy Forms com Bootstrap 5
- **Banco de Dados**: SQLite (desenvolvimento) / PostgreSQL (produção)
- **Autenticação**: Sistema nativo do Django
- **Upload de Arquivos**: Pillow para processamento de imagens

## 📋 Pré-requisitos

- Python 3.8+
- pip (gerenciador de pacotes Python)
- Git

## 🔧 Instalação e Configuração

### 1. Clone o repositório
```bash
git clone https://github.com/wagnercateb/django-votebem.git
cd django-votebem
```

### 2. Crie um ambiente virtual
```bash
python -m venv .venv

# Windows
.venv\Scripts\activate

# Linux/Mac
source .venv/bin/activate
```

### 3. Instale as dependências
```bash
pip install -r requirements.txt
```

### 4. Configure o banco de dados
```bash
python manage.py makemigrations
python manage.py migrate
```

### 5. Crie um superusuário
```bash
python manage.py createsuperuser
```

### 6. Execute o servidor de desenvolvimento
```bash
python manage.py runserver
```

O sistema estará disponível em: http://127.0.0.1:8000/

## 📁 Estrutura do Projeto

```
django_votebem/
├── manage.py
├── requirements.txt
├── .gitignore
├── README.md
├── votebem/                 # Configurações principais do Django
│   ├── settings.py
│   ├── urls.py
│   └── ...
├── voting/                  # App de votações
│   ├── models.py           # Modelos: Proposicao, VotacaoDisponivel, Voto
│   ├── views.py            # Views para listagem e votação
│   ├── urls.py
│   └── ...
├── polls/                   # App de enquetes
│   ├── models.py           # Modelos: Enquete, RespostaEnquete
│   ├── views.py            # Views para CRUD de enquetes
│   ├── forms.py            # Formulários para enquetes
│   └── ...
├── users/                   # App de usuários
│   ├── models.py           # Modelo: UserProfile
│   ├── views.py            # Views de autenticação e perfil
│   ├── forms.py            # Formulários de usuário
│   └── ...
└── templates/               # Templates HTML
    ├── base.html           # Template base
    ├── voting/             # Templates de votação
    ├── polls/              # Templates de enquetes
    └── users/              # Templates de usuários
```

## 🎯 Como Usar

### Para Usuários
1. **Cadastre-se** ou faça **login** no sistema
2. **Vote** nas proposições disponíveis na seção "Votações"
3. **Crie enquetes** sobre temas de seu interesse
4. **Responda enquetes** de outros usuários
5. **Acompanhe seu ranking** e pontuação

### Para Administradores
1. Acesse o **Django Admin** em `/admin/`
2. **Gerencie proposições** e votações disponíveis
3. **Modere enquetes** e respostas
4. **Visualize estatísticas** de usuários e participação

## 🏆 Sistema de Pontuação

- **+10 pontos**: Voto em proposição
- **+20 pontos**: Criação de enquete
- **+5 pontos**: Resposta em enquete
- **+3 pontos**: Comentário em resposta

## 🔐 Configurações de Segurança

- Autenticação obrigatória para votação e criação de enquetes
- Proteção CSRF em todos os formulários
- Validação de dados de entrada
- Controle de acesso baseado em permissões

## 🚀 Deploy em Produção

### Variáveis de Ambiente Recomendadas
```bash
DEBUG=False
SECRET_KEY=sua_chave_secreta_aqui
DATABASE_URL=postgresql://user:password@host:port/database
ALLOWED_HOSTS=seudominio.com,www.seudominio.com
```

### Configurações Adicionais
- Configure um servidor web (Nginx/Apache)
- Use um servidor WSGI (Gunicorn/uWSGI)
- Configure coleta de arquivos estáticos
- Configure backup do banco de dados

## 🤝 Contribuindo

1. Faça um fork do projeto
2. Crie uma branch para sua feature (`git checkout -b feature/AmazingFeature`)
3. Commit suas mudanças (`git commit -m 'Add some AmazingFeature'`)
4. Push para a branch (`git push origin feature/AmazingFeature`)
5. Abra um Pull Request

## 📝 Licença

Este projeto está sob a licença MIT. Veja o arquivo `LICENSE` para mais detalhes.

## 👨‍💻 Autor

**Wagner Cateb**
- GitHub: [@wagnercateb](https://github.com/wagnercateb)
- Email: wagnercateb@gmail.com

## 🙏 Agradecimentos

- Comunidade Django pela excelente documentação
- Bootstrap pela interface responsiva
- Todos os contribuidores que ajudaram a melhorar este projeto

---

⭐ Se este projeto foi útil para você, considere dar uma estrela no repositório!