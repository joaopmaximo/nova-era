# Sistema de Gestão de Alunos - Nova Era

Sistema para gerenciamento de alunos e matrículas em cursos, desenvolvido com Python, FastAPI e PostgreSQL.

## Funcionalidades Atuais

- **Gestão de Alunos:** Cadastro, edição, exclusão e listagem de alunos.
- **Matrículas em Cursos:** Suporte a múltiplos cursos por aluno (Inglês Iniciante, Inglês Avançado, Espanhol, Informática).
- **Interface por Abas:** Organização por curso e visão geral de todos os alunos.
- **Importação/Exportação:** Suporte a arquivos CSV para migração de dados.
- **Filtros e Busca:** Pesquisa inteligente dentro de cada aba selecionada.

## Stack Tecnológica

- **Backend**: FastAPI + SQLAlchemy + Passlib (Bcrypt)
- **Banco de Dados**: PostgreSQL (via Docker)
- **Frontend**: Jinja2 + Vanilla JS + Tailwind CSS (Responsivo)

## Estrutura do Projeto

```
├── app/
│   ├── auth.py        # Autenticação JWT
│   ├── database.py    # Conexão com banco
│   ├── models.py      # Modelos SQLAlchemy (Student, Course, User)
│   └── main.py        # Rotas e Lógica principal
├── templates/
│   ├── base.html      # Layout principal
│   ├── login.html     # Página de acesso
│   └── students.html  # Interface de gestão de alunos
├── ONLINE_FEATURE.md  # Documentação da funcionalidade oculta
├── IMPLEMENTATION.md  # Detalhes técnicos da implementação
└── docker-compose.yml
```

## Instalação e Execução

```bash
# 1. Iniciar banco de dados
docker compose up -d

# 2. Instalar dependências (use um ambiente virtual)
pip install -r requirements.txt

# 3. Rodar migrações/seed (opcional para dev)
py seed_dev.py

# 4. Iniciar o servidor
py -m uvicorn app.main:app --reload
```

## Documentação Extra

- Para detalhes sobre a funcionalidade de "Alunos Online" e como reativá-la, consulte [ONLINE_FEATURE.md](./ONLINE_FEATURE.md).
