# VigilaCore

<div align="center">

![Python](https://img.shields.io/badge/Python-33.3%25-3776AB?style=flat-square&logo=python&logoColor=white)
![HTML](https://img.shields.io/badge/HTML-47.6%25-E34F26?style=flat-square&logo=html5&logoColor=white)
![CSS](https://img.shields.io/badge/CSS-18.8%25-1572B6?style=flat-square&logo=css3&logoColor=white)
![JavaScript](https://img.shields.io/badge/JavaScript-0.3%25-F7DF1E?style=flat-square&logo=javascript&logoColor=black)

**Plataforma de monitoramento e análise para gestão de leituras de medição**

[🇺🇸 English Version](README.md)

</div>

---

## 📋 Menu Principal

VigilaCore é uma aplicação web full-stack projetada para monitorar e analisar dados de leitura de medição. Oferece métricas de dashboard, visualizações em gráficos e relatórios detalhados para acompanhamento de operações de **Releitura** e **Porteira**.

## ✨ Funcionalidades

- 🔐 **Autenticação de Usuários** - Sistema seguro de login e registro com controle de acesso baseado em funções
- 📊 **Dashboards Interativos** - Métricas em tempo real e visualizações em gráficos
- 📁 **Processamento de Arquivos Excel** - Upload e processamento de relatórios Excel com extração automática de dados
- 🔄 **Sincronização com Portal** - Sincronização automática de dados com portais externos via web scraping
- 📈 **Motor de Analytics** - Análise profunda de dados de leitura com detecção de duplicatas
- 👥 **Controles de Administrador** - Capacidade de reset do banco de dados para administradores

## 🏗️ Estrutura do Projeto

```
VigilaCore/
├── backend/
│   ├── app.py              # Servidor REST API Flask
│   ├── requirements.txt    # Dependências Python
│   ├── test_auth.py        # Testes de autenticação
│   ├── migrate_passwords.py
│   └── core/               # Módulos de lógica de negócio
│       ├── analytics.py    # Funções de análise de dados
│       ├── database.py     # Operações de banco de dados
│       ├── auth.py         # Lógica de autenticação
│       ├── dashboard_metrics.py
│       └── portal_scraper.py  # Web scraping para sincronização
├── frontend/
│   ├── views/              # Templates HTML
│   ├── css/                # Folhas de estilo
│   └── js/                 # Arquivos JavaScript
└── data/                   # Arquivos Excel enviados
```

## 🚀 Como Começar

### Pré-requisitos

- Python 3.8+
- pip (gerenciador de pacotes Python)

### Instalação

1. **Clone o repositório**
   ```bash
   git clone https://github.com/hrsallan/VigilaCore.git
   cd VigilaCore
   ```

2. **Instale as dependências**
   ```bash
   cd backend
   pip install -r requirements.txt
   ```

3. **Execute a aplicação**
   ```bash
   python app.py
   ```

4. **Acesse a aplicação**
   
   Abra seu navegador e acesse `http://localhost:5000`

## 📡 Endpoints da API

| Método | Endpoint | Descrição |
|--------|----------|-----------|
| POST | `/api/login` | Autenticação de usuário |
| POST | `/api/register` | Registro de usuário |
| GET | `/api/status/releitura` | Obtém status e métricas de releitura |
| GET | `/api/status/porteira` | Obtém status e métricas de porteira |
| GET | `/api/dashboard/metrics` | Obtém métricas do dashboard |
| POST | `/api/upload` | Upload de arquivo Excel para processamento |
| POST | `/api/upload/porteira` | Upload de arquivo Excel de porteira |
| POST | `/api/sync/releitura` | Sincroniza dados de releitura do portal |
| POST | `/api/sync/porteira` | Sincroniza dados de porteira do portal |
| POST | `/api/reset` | Reseta o banco de dados (apenas admin) |
| POST | `/api/reset/porteira` | Reseta banco de dados da porteira (apenas admin) |
| GET | `/api/porteira/chart` | Obtém dados do gráfico de porteira |
| GET | `/api/porteira/table` | Obtém dados da tabela de porteira |

## 🛠️ Stack Tecnológico

- **Backend**: Python, Flask, Flask-CORS
- **Frontend**: HTML5, CSS3, JavaScript
- **Processamento de Dados**: Pandas, OpenPyXL, xlrd
- **Automação**: Selenium, PyAutoGUI
- **Configuração**: python-dotenv

## 📄 Licença

Este projeto está disponível sob uma **Licença Não-Comercial**. Você pode usar, modificar e distribuir este software apenas para fins não-comerciais. O uso comercial, incluindo venda ou uso deste software para gerar receita, é estritamente proibido. Veja o arquivo [LICENSE](LICENSE) para mais detalhes.

## 🤝 Contribuindo

Contribuições, issues e solicitações de funcionalidades são bem-vindas! Sinta-se à vontade para verificar a [página de issues](https://github.com/hrsallan/VigilaCore/issues).

---

<div align="center">
Criado por <a href="https://github.com/hrsallan">hrsallan</a>
</div>