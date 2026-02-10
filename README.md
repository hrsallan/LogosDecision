# VigilaCore

<div align="center">

![Python](https://img.shields.io/badge/Python-3.9%2B-3776AB?style=flat-square&logo=python&logoColor=white)
![Flask](https://img.shields.io/badge/Flask-2.0%2B-000000?style=flat-square&logo=flask&logoColor=white)
![SQLite](https://img.shields.io/badge/SQLite-3-003B57?style=flat-square&logo=sqlite&logoColor=white)
![HTML5](https://img.shields.io/badge/HTML-5-E34F26?style=flat-square&logo=html5&logoColor=white)
![CSS3](https://img.shields.io/badge/CSS-3-1572B6?style=flat-square&logo=css3&logoColor=white)
![JavaScript](https://img.shields.io/badge/JavaScript-ES6%2B-F7DF1E?style=flat-square&logo=javascript&logoColor=black)

**Plataforma de Monitoramento e Análise para Gestão de Leituras**

</div>

---

## 📋 Sobre o Projeto

O **VigilaCore** é uma aplicação web full-stack robusta desenvolvida para monitorar, analisar e gerenciar dados de leitura de utilidades (especificamente para operações da CEMIG). O sistema automatiza o processo de coleta de dados do portal SGL, processa relatórios complexos em Excel e fornece dashboards em tempo real para tomada de decisão.

O objetivo principal é eliminar o trabalho manual repetitivo, detectar inconsistências (como leituras não executadas) e fornecer uma visão clara do desempenho operacional através de métricas e gráficos interativos.

### Principais Benefícios
- **Automação:** Download e processamento automático de relatórios.
- **Eficiência:** Redução drástica do tempo de análise de dados.
- **Confiabilidade:** Eliminação de erros humanos na manipulação de planilhas.
- **Visibilidade:** Dashboards em tempo real acessíveis a toda a equipe.

---

## ✨ Funcionalidades

### 🔄 Módulo de Releitura
- **Monitoramento de Pendências:** Acompanhamento em tempo real de releituras não executadas.
- **Roteamento Inteligente:** Distribuição automática de ordens de serviço por região (Araxá, Uberaba, Frutal).
- **Análise de Vencimentos:** Visualização de prazos e priorização de ordens.

### 🚪 Módulo de Porteira
- **Controle de Ciclos:** Suporte completo aos ciclos de leitura 97, 98 e 99.
- **Análise Regional:** Filtros por região e localidade.
- **Métricas de Execução:** Comparativo entre leituras totais e não executadas.
- **Detecção de Impedimentos:** Identificação automática de motivos de não leitura.

### 📊 Relatórios e Análises
- **Dashboards Interativos:** Gráficos de barras, pizza e evolução temporal.
- **Histórico Mensal:** Acompanhamento da evolução de pendências mês a mês.
- **Exportação de Dados:** Capacidade de gerar relatórios consolidados.

### 🔐 Segurança e Administração
- **Autenticação JWT:** Sistema seguro de login com tokens.
- **Controle de Acesso (RBAC):** Níveis de permissão (Analista, Gerência, Diretoria, Desenvolvedor).
- **Criptografia:** Senhas e credenciais sensíveis armazenadas com criptografia forte.

---

## 🛠️ Tecnologias Utilizadas

### Backend
- **Linguagem:** Python 3.9+
- **Framework Web:** Flask
- **Banco de Dados:** SQLite3
- **Processamento de Dados:** Pandas, OpenPyXL
- **Automação:** Selenium (para scraping do portal), APScheduler (agendamento de tarefas)
- **Segurança:** BCrypt, PyJWT, Cryptography

### Frontend
- **Estrutura:** HTML5 Semântico
- **Estilização:** CSS3 Moderno (Variáveis CSS, Flexbox, Grid)
- **Lógica:** JavaScript (ES6+)
- **Visualização:** Chart.js
- **Ícones:** Lucide Icons

---

## 🚀 Começando

### Pré-requisitos
- Python 3.9 ou superior instalado.
- Gerenciador de pacotes `pip`.
- Navegador web moderno (Chrome, Firefox, Edge).

### Instalação

1. **Clone o repositório:**
   ```bash
   git clone https://github.com/seu-usuario/VigilaCore.git
   cd VigilaCore
   ```

2. **Crie um ambiente virtual (recomendado):**
   ```bash
   python -m venv venv
   # Windows
   venv\Scripts\activate
   # Linux/Mac
   source venv/bin/activate
   ```

3. **Instale as dependências:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure as variáveis de ambiente:**
   Crie um arquivo `.env` na raiz do projeto com o seguinte conteúdo:
   ```env
   # Segurança
   JWT_SECRET=sua_chave_secreta_super_segura

   # Credenciais Padrão (Opcional - Configurado via Interface)
   # RELEITURA_MANAGER_USERNAME=GRTRI

   # Scheduler (Opcional)
   SCHEDULER_ENABLED=1
   ```

5. **Inicialize o Banco de Dados:**
   O banco de dados será criado automaticamente na primeira execução, mas você pode forçar a inicialização:
   ```bash
   python -c "from backend.core.database import init_db; init_db()"
   ```

6. **Execute a aplicação:**
   ```bash
   python backend/app.py
   ```
   O servidor iniciará em `http://localhost:5000` (ou a porta configurada).

---

## 📖 Como Usar

1. **Acesso ao Sistema:**
   - Abra o navegador e acesse `http://localhost:5000/views/login.html` (ou configure um servidor web para servir o frontend).
   - Faça login com suas credenciais. Se for o primeiro acesso, solicite ao administrador.

2. **Navegação:**
   - Use a barra lateral para alternar entre os módulos (Releitura, Porteira, Relatórios).
   - O **Menu Principal** oferece uma visão geral do sistema.

3. **Upload de Arquivos:**
   - Nos módulos de Releitura e Porteira, utilize a área de upload para enviar as planilhas do SGL.
   - O sistema processará os dados e atualizará os dashboards automaticamente.

---

## 📚 Documentação da API

O backend fornece uma API RESTful para comunicação com o frontend.

### Autenticação
- `POST /api/login`: Autentica o usuário e retorna um token JWT.
- `POST /api/register`: Registra novos usuários (requer permissão).

### Releitura
- `GET /api/status/releitura`: Retorna métricas e dados para os gráficos.
- `POST /api/upload`: Envia um relatório de releitura para processamento.
- `POST /api/sync/releitura`: Aciona a sincronização automática (download do portal).

### Porteira
- `GET /api/status/porteira`: Retorna métricas gerais da porteira.
- `GET /api/porteira/table`: Retorna os dados detalhados para a tabela.
- `POST /api/upload/porteira`: Envia um relatório de porteira.

---

## 📂 Estrutura do Projeto

```
VigilaCore/
├── backend/
│   ├── app.py                 # Ponto de entrada da aplicação Flask
│   ├── data/                  # Banco de dados SQLite e arquivos temporários
│   └── core/                  # Núcleo da lógica de negócios
│       ├── analytics.py       # Processamento de planilhas
│       ├── auth.py            # Lógica de autenticação
│       ├── database.py        # Camada de acesso a dados
│       ├── portal_scraper.py  # Automação de download
│       └── scheduler.py       # Agendador de tarefas
├── frontend/
│   ├── css/                   # Folhas de estilo
│   ├── js/                    # Scripts do lado do cliente
│   └── views/                 # Páginas HTML
├── requirements.txt           # Dependências do Python
├── README.md                  # Documentação do projeto
└── LICENSE                    # Licença de uso
```

---

## 📄 Licença

Este projeto está licenciado sob a **Licença de Uso Não Comercial VigilaCore**. Consulte o arquivo [LICENSE](LICENSE) para obter detalhes completos.

---

## 📞 Contato e Créditos

**Desenvolvedor:** Allan Silva (hrsallan)
- **GitHub:** [hrsallan](https://github.com/hrsallan)

Feito com ❤️ e Python.
