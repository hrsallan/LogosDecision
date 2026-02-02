# VigilaCore

<div align="center">

![Python](https://img.shields.io/badge/Python-31.0%25-3776AB?style=flat-square&logo=python&logoColor=white)
![HTML](https://img.shields.io/badge/HTML-53.1%25-E34F26?style=flat-square&logo=html5&logoColor=white)
![CSS](https://img.shields.io/badge/CSS-14.6%25-1572B6?style=flat-square&logo=css3&logoColor=white)
![JavaScript](https://img.shields.io/badge/JavaScript-1.3%25-F7DF1E?style=flat-square&logo=javascript&logoColor=black)

**Plataforma de monitoramento e análise para gestão de leituras de medição**

[🇺🇸 English Version](README.md) | [📖 Guia do Scheduler](GUIA_SCHEDULER_AUTOMATICO.md)

</div>

---

## 📑 Índice

- [Visão Geral](#-visão-geral)
- [Funcionalidades](#-funcionalidades)
- [Capturas de Tela](#-capturas-de-tela)
- [Arquitetura do Projeto](#️-arquitetura-do-projeto)
- [Como Começar](#-como-começar)
- [Documentação da API](#-documentação-da-api)
- [Variáveis de Ambiente](#-variáveis-de-ambiente)
- [Guia de Segurança](#-guia-de-segurança)
- [Stack Tecnológico](#️-stack-tecnológico)
- [Contribuindo](#-contribuindo)
- [Licença](#-licença)

---

## 📋 Visão Geral

VigilaCore é uma aplicação web full-stack abrangente desenvolvida especificamente para monitorar e analisar dados de leitura de medição da **CEMIG (Companhia Energética de Minas Gerais)** através do portal **SGL (Sistema de Gestão de Leitura)**.

O sistema automatiza o tedioso processo de baixar, processar e analisar relatórios de leitura manualmente, fornecendo dashboards em tempo real, métricas e visualizações para dois fluxos operacionais críticos:

- **Releitura**: Rastreia e gerencia operações de releitura de medidores quando leituras iniciais são questionadas ou requerem verificação
- **Porteira**: Monitora operações de leitura agendadas e status de execução em diferentes pontos de serviço

### Valor de Negócio Principal

- **Elimina trabalho manual**: Downloads automatizados do portal CEMIG SGL via sincronização agendada
- **Visibilidade em tempo real**: Dashboards ao vivo mostrando status atual de leituras e operações
- **Rastreamento histórico**: Trilha de auditoria completa de todas as operações de leitura ao longo do tempo
- **Detecção de duplicatas**: Algoritmos inteligentes para identificar e sinalizar leituras duplicadas
- **Métricas de desempenho**: KPIs e análises para medir eficiência operacional

## ✨ Funcionalidades

- 🔐 **Autenticação de Usuários** - Sistema seguro de login e registro com controle de acesso baseado em funções (admin/usuário)
- 📊 **Dashboards Interativos** - Métricas em tempo real, KPIs e visualizações em gráficos atualizados automaticamente
- 📁 **Processamento de Arquivos Excel** - Upload e processamento de relatórios Excel do CEMIG SGL com extração automática de dados
- 🔄 **Sincronização Automatizada com Portal** - Downloads agendados do portal CEMIG SGL usando web scraping baseado em Selenium
- 📈 **Motor de Analytics Avançado** - Análise profunda de dados de leitura com detecção inteligente de duplicatas
- ⏰ **Scheduler Inteligente** - Downloads automáticos configuráveis em intervalos especificados durante horário comercial
- 🗄️ **Gerenciamento de Credenciais** - Armazenamento e gerenciamento seguro de credenciais do portal por usuário
- 📉 **Visualizações em Gráficos** - Gráficos dinâmicos mostrando tendências e status de execução ao longo do tempo
- 👥 **Controles de Administrador** - Capacidades de reset de banco de dados e gerenciamento de scheduler para administradores
- 🔍 **Relatórios Detalhados** - Tabelas abrangentes mostrando registros individuais de leitura e detalhes de execução

## 📸 Capturas de Tela

_Em breve - Capturas de tela do dashboard, gráficos e principais funcionalidades serão adicionadas aqui_

## 🏗️ Arquitetura do Projeto

```
VigilaCore/
├── backend/
│   ├── app.py                    # Servidor REST API Flask com todos os endpoints
│   ├── scheduler.py              # Automação APScheduler para downloads do portal
│   ├── requirements.txt          # Dependências Python
│   ├── test_auth.py              # Testes unitários de autenticação
│   ├── migrate_passwords.py      # Utilitário de migração de banco de dados
│   ├── .env                      # Configuração de ambiente (não no repo)
│   ├── core/                     # Módulos de lógica de negócio
│   │   ├── analytics.py          # Análise de dados e detecção de duplicatas
│   │   ├── database.py           # Operações de banco de dados SQLite
│   │   ├── auth.py               # Autenticação e autorização
│   │   ├── dashboard_metrics.py  # Cálculo de métricas para dashboards
│   │   └── portal_scraper.py     # Scraper CEMIG SGL baseado em Selenium
│   └── data/
│       ├── vigilacore.db         # Banco de dados SQLite
│       └── exports/              # Arquivos Excel baixados do portal
├── frontend/
│   ├── views/                    # Templates HTML
│   │   ├── login.html
│   │   ├── register.html
│   │   ├── dashboard.html
│   │   ├── releitura.html
│   │   └── porteira.html
│   ├── css/                      # Folhas de estilo
│   │   └── styles.css
│   └── js/                       # Arquivos JavaScript
│       └── app.js
└── docs/
    ├── README.md                 # Versão em inglês
    ├── README.pt-BR.md           # Este arquivo
    └── GUIA_SCHEDULER_AUTOMATICO.md  # Guia do scheduler
```

## 🚀 Como Começar

### Pré-requisitos

- Python 3.8 ou superior
- pip (gerenciador de pacotes Python)
- Google Chrome (para automação Selenium)
- ChromeDriver (gerenciado automaticamente pelo webdriver-manager)

### Instalação

1. **Clone o repositório**
   ```bash
   git clone https://github.com/hrsallan/VigilaCore.git
   cd VigilaCore
   ```

2. **Instale as dependências Python**
   ```bash
   cd backend
   pip install -r requirements.txt
   ```

3. **Configure as variáveis de ambiente**
   ```bash
   cp .env.example .env
   nano .env  # Edite com seu editor preferido
   ```
   
   Veja a seção [Variáveis de Ambiente](#-variáveis-de-ambiente) para detalhes.

4. **Execute a aplicação**
   ```bash
   python app.py
   ```

5. **Acesse a aplicação**
   
   Abra seu navegador e acesse `http://localhost:5000`

6. **Crie seu primeiro usuário**
   
   Registre uma nova conta através da interface web. O primeiro usuário criado recebe automaticamente privilégios de administrador.

## 📡 Documentação da API

Referência completa da API REST com todos os 19 endpoints organizados por categoria funcional.

### Autenticação

| Método | Endpoint | Descrição | Autenticação Necessária |
|--------|----------|-----------|------------------------|
| POST | `/api/register` | Registrar uma nova conta de usuário | Não |
| POST | `/api/login` | Autenticar usuário e receber token de sessão | Não |

**Exemplo de Requisição - Registro:**
```json
POST /api/register
{
  "username": "joao.silva",
  "password": "SenhaSegura123",
  "role": "user"
}
```

**Exemplo de Requisição - Login:**
```json
POST /api/login
{
  "username": "joao.silva",
  "password": "SenhaSegura123"
}
```

### Dashboard & Métricas

| Método | Endpoint | Descrição | Autenticação Necessária |
|--------|----------|-----------|------------------------|
| GET | `/api/ping` | Endpoint de verificação de saúde | Não |
| GET | `/api/dashboard/metrics` | Obter métricas abrangentes do dashboard | Sim |
| GET | `/api/status/releitura` | Obter status, métricas e atividade recente de releitura | Sim |
| GET | `/api/status/porteira` | Obter status, métricas e dados de execução de porteira | Sim |

**Exemplo de Resposta - Métricas do Dashboard:**
```json
{
  "releitura": {
    "total": 156,
    "pending": 23,
    "completed": 133
  },
  "porteira": {
    "total": 89,
    "executed": 67,
    "not_executed": 22
  },
  "last_sync": "2026-02-02T10:30:00"
}
```

### Operações de Releitura

| Método | Endpoint | Descrição | Autenticação Necessária |
|--------|----------|-----------|------------------------|
| POST | `/api/upload` | Upload de arquivo Excel de releitura para processamento | Sim |
| POST | `/api/sync/releitura` | Disparar sincronização manual do portal CEMIG SGL | Sim |
| POST | `/api/reset` | Resetar banco de dados de releitura (apenas admin) | Sim (Admin) |

**Exemplo de Requisição - Upload:**
```bash
POST /api/upload
Content-Type: multipart/form-data

file: relatorio_releitura.xlsx
```

### Operações de Porteira

| Método | Endpoint | Descrição | Autenticação Necessária |
|--------|----------|-----------|------------------------|
| POST | `/api/upload/porteira` | Upload de arquivo Excel de porteira para processamento | Sim |
| POST | `/api/sync/porteira` | Disparar sincronização manual do portal CEMIG SGL | Sim |
| GET | `/api/porteira/chart` | Obter dados do gráfico para visualizações | Sim |
| GET | `/api/porteira/table` | Obter dados detalhados da tabela | Sim |
| GET | `/api/porteira/nao-executadas-chart` | Obter dados do gráfico de operações não executadas | Sim |
| POST | `/api/reset/porteira` | Resetar banco de dados de porteira (apenas admin) | Sim (Admin) |

**Exemplo de Resposta - Gráfico de Porteira:**
```json
{
  "labels": ["2026-02-01", "2026-02-02"],
  "executed": [45, 52],
  "not_executed": [12, 8]
}
```

### Gerenciamento de Usuários

| Método | Endpoint | Descrição | Autenticação Necessária |
|--------|----------|-----------|------------------------|
| GET | `/api/user/portal-credentials` | Obter credenciais armazenadas do portal CEMIG do usuário | Sim |
| PUT | `/api/user/portal-credentials` | Salvar ou atualizar credenciais do portal | Sim |
| DELETE | `/api/user/portal-credentials` | Deletar credenciais armazenadas do portal | Sim |

**Exemplo de Requisição - Salvar Credenciais:**
```json
PUT /api/user/portal-credentials
{
  "username": "usuario.cemig",
  "password": "senha_portal"
}
```

### Gerenciamento de Scheduler

| Método | Endpoint | Descrição | Autenticação Necessária |
|--------|----------|-----------|------------------------|
| GET | `/api/scheduler/status` | Obter status do scheduler e próximos horários de execução | Sim |
| POST | `/api/scheduler/toggle` | Iniciar ou parar o scheduler (apenas admin) | Sim (Admin) |

**Exemplo de Resposta - Status do Scheduler:**
```json
{
  "enabled": true,
  "running": true,
  "schedule": "7h - 17h",
  "interval_minutes": 60,
  "next_run_releitura": "2026-02-02T12:00:00",
  "next_run_porteira": "2026-02-02T12:00:00"
}
```

**Exemplo de Requisição - Alternar Scheduler:**
```json
POST /api/scheduler/toggle
{
  "action": "start"  // ou "stop"
}
```

## 🔧 Variáveis de Ambiente

Crie um arquivo `.env` no diretório `backend/` com a seguinte configuração:

```ini
# Configuração do Flask
FLASK_SECRET_KEY=sua-chave-secreta-aqui-mude-isto-em-producao
FLASK_ENV=development

# Credenciais do Portal CEMIG SGL (para sincronização automatizada)
PORTAL_USER=seu_usuario_cemig
PORTAL_PASS=sua_senha_cemig

# Configuração do Scheduler
SCHEDULER_ENABLED=1                    # 1 para habilitar, 0 para desabilitar
SCHEDULER_START_HOUR=7                 # Hora de início (0-23)
SCHEDULER_END_HOUR=17                  # Hora de término (0-23)
SCHEDULER_INTERVAL_MINUTES=60          # Intervalo em minutos
SCHEDULER_AUTO_RELEITURA=1             # Auto-download releitura (1=sim, 0=não)
SCHEDULER_AUTO_PORTEIRA=1              # Auto-download porteira (1=sim, 0=não)
SCHEDULER_USER_ID=1                    # ID do usuário para operações automatizadas

# Configuração do Banco de Dados
DATABASE_PATH=data/vigilacore.db

# Configuração de Download
DOWNLOAD_PATH=data/exports
```

### Notas Importantes:

- **Nunca faça commit do `.env` para controle de versão** - Ele já está no `.gitignore`
- Mude `FLASK_SECRET_KEY` para uma string aleatória segura em produção
- O `SCHEDULER_USER_ID` deve ser o ID de um usuário admin
- O scheduler só executará entre `START_HOUR` e `END_HOUR`
- Veja [GUIA_SCHEDULER_AUTOMATICO.md](GUIA_SCHEDULER_AUTOMATICO.md) para configuração detalhada do scheduler

## 🔒 Guia de Segurança

### Autenticação & Autorização

- **Segurança de Senhas**: Todas as senhas são hasheadas usando bcrypt padrão da indústria com salt
- **Gerenciamento de Sessão**: Cookies de sessão seguros com flag HTTP-only habilitada
- **Controle de Acesso Baseado em Funções (RBAC)**: Funções de admin e usuário com diferentes níveis de permissão
- **Prevenção de Injeção SQL**: Todas as consultas ao banco de dados usam declarações parametrizadas

### Melhores Práticas

1. **Senhas Fortes**: Impor políticas de senhas fortes para todos os usuários
2. **Armazenamento de Credenciais**: Credenciais do portal são criptografadas no banco de dados
3. **Variáveis de Ambiente**: Nunca codifique credenciais diretamente - sempre use arquivo `.env`
4. **HTTPS em Produção**: Sempre use HTTPS ao implantar em produção
5. **Atualizações Regulares**: Mantenha todas as dependências atualizadas para patches de segurança
6. **Log de Acesso**: Todas as operações de admin são registradas para trilhas de auditoria
7. **Backups de Banco de Dados**: Faça backup regular do arquivo de banco de dados SQLite

### Checklist de Segurança para Implantação

- [ ] Mudar `FLASK_SECRET_KEY` padrão para um valor aleatório forte
- [ ] Habilitar HTTPS com certificado SSL válido
- [ ] Definir `FLASK_ENV=production` no `.env`
- [ ] Configurar firewall para restringir acesso à porta 5000
- [ ] Configurar backups automatizados regulares do banco de dados
- [ ] Revisar e limitar contas de usuário admin
- [ ] Monitorar logs da aplicação para atividade suspeita
- [ ] Manter Python e todas as dependências atualizadas

## 🛠️ Stack Tecnológico

### Backend
- **Framework**: Flask 2.x - Framework web Python leve
- **Servidor WSGI**: Werkzeug - Servidor de desenvolvimento (use Gunicorn para produção)
- **Banco de Dados**: SQLite3 - Banco de dados relacional embutido
- **Autenticação**: Sessões Flask com hash de senha bcrypt
- **Processamento de Dados**: Pandas, OpenPyXL, xlrd - Parsing e análise de arquivos Excel
- **Scheduler de Tarefas**: APScheduler - Jobs em background automatizados
- **Web Scraping**: Selenium, PyAutoGUI - Automação de navegador para downloads do portal

### Frontend
- **HTML5**: Marcação semântica
- **CSS3**: Estilização moderna com Flexbox/Grid
- **JavaScript**: JS Vanilla para interatividade
- **Gráficos**: Chart.js para visualizações de dados
- **Ícones**: Font Awesome para ícones de UI

### DevOps & Ferramentas
- **Controle de Versão**: Git & GitHub
- **Gerenciamento de Ambiente**: python-dotenv
- **Testes**: Pytest (testes unitários)
- **Driver de Navegador**: webdriver-manager - Gerenciamento automático do ChromeDriver

## 🤝 Contribuindo

Aceitamos contribuições da comunidade! Veja como você pode ajudar:

### Reportando Problemas

- Use a página de [GitHub Issues](https://github.com/hrsallan/VigilaCore/issues)
- Pesquise issues existentes antes de criar uma nova
- Forneça informações detalhadas:
  - Passos para reproduzir
  - Comportamento esperado vs atual
  - Informações do sistema (SO, versão Python, navegador)
  - Capturas de tela se aplicável

### Submetendo Pull Requests

1. **Faça fork do repositório** e crie uma nova branch
   ```bash
   git checkout -b feature/nome-da-sua-feature
   ```

2. **Faça suas alterações** seguindo o estilo do código:
   - Use nomes significativos para variáveis e funções
   - Adicione comentários para lógica complexa
   - Siga o guia de estilo PEP 8 para código Python
   - Teste suas alterações minuciosamente

3. **Faça commit de suas alterações** com mensagens claras
   ```bash
   git commit -m "Adicionar feature: descrição do que você adicionou"
   ```

4. **Envie para seu fork** e submeta um pull request
   ```bash
   git push origin feature/nome-da-sua-feature
   ```

5. **Diretrizes de Pull Request**:
   - Descreva claramente o que seu PR faz
   - Referencie quaisquer issues relacionadas
   - Inclua capturas de tela para alterações de UI
   - Certifique-se de que todos os testes passam
   - Atualize documentação se necessário

### Código de Conduta

- Seja respeitoso e construtivo
- Dê as boas-vindas a novatos e ajude-os a aprender
- Foque no que é melhor para a comunidade
- Mostre empatia para com outros membros da comunidade

## 📄 Licença

Este projeto está licenciado sob a **Licença Não-Comercial VigilaCore Versão 1.0**.

- ✅ **Permitido**: Usar, modificar e distribuir para fins não-comerciais
- ❌ **Proibido**: Uso comercial, venda ou geração de receita
- 📋 **Requisito**: Compartilhar da mesma forma - trabalhos derivados devem usar a mesma licença

Para consultas sobre licenciamento comercial, entre em contato com [hrsallan](https://github.com/hrsallan).

Veja o arquivo [LICENSE](LICENSE) para termos legais completos.

---

## 🔗 Documentação Relacionada

- [🇺🇸 English README](README.md) - Versão completa em inglês
- [📖 Guia do Scheduler Automático](GUIA_SCHEDULER_AUTOMATICO.md) - Guia detalhado de configuração do scheduler

---

<div align="center">

**Criado por [Allan Silva (hrsallan)](https://github.com/hrsallan)**

Copyright © 2026 Allan Silva. Todos os direitos reservados.

</div>
