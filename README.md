# Logos Decision

**Sistema Integrado de Monitoramento e Gestão de Leituras - MG Setel**

Bem-vindo ao **Logos Decision**, uma solução robusta e de alto desempenho desenvolvida exclusivamente para a MG Setel. Este projeto representa um marco na gestão operacional de leituras de serviços públicos (água/energia), consolidando-se como uma ferramenta essencial para a tomada de decisões estratégicas e o controle de qualidade.

---

## 🚀 Sobre o Projeto

O **Logos Decision** ("Projeto da Minha Vida") foi concebido para centralizar, analisar e otimizar os processos de **Releitura** e **Porteira**. Através de uma interface web intuitiva e um backend poderoso, o sistema permite o acompanhamento em tempo real de métricas críticas, identificação de gargalos operacionais e automação de tarefas repetitivas.

A plataforma integra dados de diversas fontes, aplica regras de negócio complexas (como roteamento regional e cálculo de prazos) e apresenta dashboards executivos para diferentes níveis hierárquicos (Analistas, Supervisão, Gerência e Diretoria).

---

## 🌟 Funcionalidades Principais

### 1. Gestão de Releitura
O módulo de Releitura foca na eficiência e cumprimento de prazos das ordens de serviço.
*   **Upload e Processamento Inteligente:** Importação de planilhas Excel com validação automática e cálculo de hash para evitar duplicidades.
*   **Roteamento Automático (V2):** Distribuição automática das ordens para as regionais corretas (**Araxá, Uberaba, Frutal**) com base em regras predefinidas.
*   **Dashboard Operacional:** Visualização clara de status (Pendente, Concluída, Atrasada) e métricas de desempenho individual e regional.
*   **Controle de Metas:** Configuração de responsáveis por região diretamente pela interface administrativa.

### 2. Gestão de Porteira
O módulo de Porteira oferece uma visão analítica profunda sobre a qualidade e as ocorrências.
*   **Métricas Avançadas:** Acompanhamento detalhado de OSB (Ordens de Serviço Baixadas) e CNV (Consumo Não Verificado).
*   **Comparativo Mensal (Abertura):** Análise evolutiva "Mês Atual vs. Mês Anterior" para identificar tendências.
*   **Snapshots de Atrasos:** Sistema de "congelamento" diário para auditoria de atrasos (18 razões críticas).
*   **Gráficos Interativos:** Visualização de dados por ciclo, região e localidade.

### 3. Automação e Integração
*   **Portal Scraper:** Robôs (Selenium) para download automático de relatórios dos portais das concessionárias, garantindo que os dados estejam sempre atualizados sem intervenção manual.
*   **Agendador de Tarefas (Scheduler):** Execução periódica de processos de sincronização e manutenção do banco de dados.

### 4. Administração e Segurança
*   **Controle de Acesso RBAC:** Perfis de usuário bem definidos (Analista, Supervisor, Gerência, Diretoria, Desenvolvedor) com permissões granulares.
*   **Autenticação JWT:** Segurança robusta para proteção dos dados.
*   **Logs e Auditoria:** Rastreabilidade de ações críticas no sistema.

---

## 🛠️ Tecnologias Utilizadas

O Logos Decision utiliza uma pilha tecnológica moderna e eficiente:

*   **Backend:** Python 3.10+
    *   **Flask:** Framework web leve e flexível.
    *   **Pandas & OpenPyXL:** Processamento de dados e manipulação de Excel de alta performance.
    *   **APScheduler:** Gerenciamento de tarefas em segundo plano.
    *   **Selenium:** Automação de navegação web (Scraping).
    *   **SQLite:** Banco de dados relacional (leve e eficiente para a escala atual).
    *   **PyJWT & BCrypt:** Segurança e criptografia.
*   **Frontend:**
    *   HTML5, CSS3, JavaScript (Vanilla).
    *   Chart.js para visualização de dados.
    *   Design responsivo e focado na experiência do usuário (UX).

---

## 📦 Instalação e Configuração

### Pré-requisitos
*   Python 3.10 ou superior.
*   Navegador Google Chrome (para o Selenium/Scraper).

### Passo a Passo

1.  **Clone o Repositório**
    ```bash
    git clone https://github.com/seu-usuario/logos-decision.git
    cd logos-decision
    ```

2.  **Crie um Ambiente Virtual**
    ```bash
    python -m venv venv
    # Windows
    venv\Scripts\activate
    # Linux/Mac
    source venv/bin/activate
    ```

3.  **Instale as Dependências**
    ```bash
    pip install -r requirements.txt
    ```

4.  **Configuração de Ambiente (.env)**
    Crie um arquivo `.env` na raiz do projeto com as configurações necessárias (exemplo):
    ```env
    JWT_SECRET=sua_chave_secreta_super_segura
    RELEITURA_MANAGER_USERNAME=GRTRI
    ```

5.  **Execute o Servidor**
    ```bash
    python backend/app.py
    ```
    O servidor iniciará em `http://0.0.0.0:5000`.

---

## 📂 Estrutura do Projeto

```
logos-decision/
├── backend/            # Código-fonte do servidor Python
│   ├── app.py          # Ponto de entrada da aplicação
│   ├── core/           # Lógica de negócios (Scrapers, Analytics, DB)
│   └── data/           # Armazenamento de dados (SQLite, Arquivos Temp)
├── frontend/           # Interface do usuário
│   ├── views/          # Páginas HTML
│   ├── css/            # Estilos
│   └── js/             # Lógica do Frontend
├── requirements.txt    # Dependências do Python
├── LICENSE             # Licença de Uso
└── README.md           # Documentação do Projeto
```

---

## ⚠️ Licença e Direitos Autorais

**USO EXCLUSIVO DA MG SETEL.**

Este software é propriedade intelectual da **MG Setel**. O uso, cópia, modificação, distribuição ou comercialização não autorizada deste código é estritamente proibida.

Consulte o arquivo `LICENSE` para os termos completos.

---

## 📞 Contato

Desenvolvido com excelência técnica e compromisso para a **MG Setel**.

Para suporte técnico ou dúvidas sobre o sistema, entre em contato com a equipe de TI ou o desenvolvedor responsável.

---
*Logos Decision © 2026 MG Setel - Todos os direitos reservados.*
