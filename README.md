# LogosDecision

**Sistema de Inteligência e Gestão Estratégica de Leituras - MG Setel**

O **LogosDecision** representa a evolução definitiva na gestão de operações de leitura de serviços públicos. Desenvolvido sob medida para a **MG Setel**, este sistema é uma ferramenta de "missão crítica", projetada para garantir excelência operacional, integridade de dados e suporte à tomada de decisões estratégicas em alto nível.

Este projeto não é apenas um software; é o **pilar tecnológico** que centraliza a inteligência do negócio, transformando dados brutos em insights acionáveis para otimizar recursos, reduzir custos e maximizar a eficiência das equipes de campo.

---

## 🚀 Visão Geral e Propósito

O **LogosDecision** foi arquitetado para solucionar desafios complexos nos processos de **Releitura** e **Porteira**, oferecendo:

*   **Excelência Operacional:** Automação de fluxos de trabalho que eliminam erros manuais e reduzem drasticamente o tempo de processamento.
*   **Inteligência de Dados:** Dashboards analíticos que permitem monitoramento em tempo real e previsão de tendências.
*   **Governança e Controle:** Rastreabilidade completa das operações, garantindo compliance e auditoria eficaz.

O sistema atende a todos os níveis da organização, desde analistas operacionais até a diretoria executiva, consolidando-se como o ativo digital mais importante da operação.

---

## 🌟 Funcionalidades Estratégicas

### 1. Módulo de Releitura Inteligente
Focado na gestão de alta performance das ordens de serviço de releitura.
*   **Ingestão de Dados Robusta:** Processamento de planilhas complexas com verificação de integridade (Hash SHA-256) para garantir a unicidade dos dados.
*   **Roteamento Algorítmico:** Distribuição automática e inteligente de demandas para as regionais (**Araxá, Uberaba, Frutal**) baseada em capacidade e regras de negócio.
*   **Painel de Controle em Tempo Real:** Visualização instantânea de KPIs (Key Performance Indicators) de produtividade e status de execução.

### 2. Módulo de Gestão de Porteira (Analytics)
Ferramenta poderosa para análise de qualidade e detecção de anomalias.
*   **Análise Profunda de Indicadores:** Monitoramento detalhado de OSB (Ordens de Serviço Baixadas) e CNV (Consumo Não Verificado).
*   **Auditoria de Atrasos (Snapshots):** Sistema de congelamento de dados para análise forense de atrasos e gargalos operacionais.
*   **Comparativos Temporais:** Análises "Mês a Mês" e evolutivas para suporte a decisões táticas.

### 3. Automação (RPA) e Integração
*   **Web Scraping Avançado:** Agentes autônomos (Selenium) que interagem com portais de concessionárias para extração segura e contínua de relatórios.
*   **Scheduler Corporativo:** Orquestração de tarefas em background para garantir que os dados estejam sempre atualizados sem intervenção humana.

### 4. Segurança e Administração
*   **Controle de Acesso RBAC:** Gestão granular de permissões baseada em funções (Analista, Supervisor, Gerente, Diretor).
*   **Segurança de Nível Enterprise:** Criptografia de senhas (Bcrypt) e autenticação via Tokens JWT.

---

## 🛠️ Arquitetura Técnica

O **LogosDecision** é construído sobre uma stack tecnológica moderna, priorizando estabilidade, escalabilidade e manutenibilidade:

*   **Backend:** Python 3.10+ (Flask Framework)
    *   **Core:** Pandas, OpenPyXL (Processamento de Dados Massivos).
    *   **Automação:** Selenium WebDriver, APScheduler.
    *   **Segurança:** PyJWT, Cryptography, BCrypt.
*   **Frontend:** HTML5, CSS3, JavaScript (Vanilla ES6+), Chart.js.
*   **Banco de Dados:** SQLite (Otimizado para alta performance local).

---

## 📦 Instalação e Execução

### Pré-requisitos
*   Python 3.10 ou superior.
*   Google Chrome (versão compatível com WebDriver).

### Procedimento de Instalação

1.  **Clone o Repositório**
    ```bash
    git clone https://github.com/mgsetel/logos-decision.git
    cd logos-decision
    ```

2.  **Configuração do Ambiente Virtual**
    ```bash
    python -m venv venv
    # Windows
    venv\Scripts\activate
    # Linux/Mac
    source venv/bin/activate
    ```

3.  **Instalação de Dependências**
    ```bash
    pip install -r requirements.txt
    ```

4.  **Configuração de Variáveis de Ambiente (.env)**
    Crie um arquivo `.env` na raiz conforme o modelo de configuração segura da empresa.

5.  **Inicialização do Sistema**
    ```bash
    python backend/app.py
    ```
    O sistema estará acessível em `http://127.0.0.1:5000`.

---

## 📂 Estrutura de Diretórios

```
logos-decision/
├── backend/            # Núcleo da aplicação (API e Lógica de Negócio)
│   ├── app.py          # Entry point da aplicação
│   ├── core/           # Módulos de processamento e regras de negócio
│   └── data/           # Camada de persistência
├── frontend/           # Interface do Usuário (UI/UX)
│   ├── views/          # Templates HTML
│   ├── css/            # Estilos
│   └── js/             # Lógica de apresentação
├── requirements.txt    # Manifesto de dependências
├── LICENSE             # Termos de uso exclusivo
└── README.md           # Documentação oficial
```

---

## ⚠️ Propriedade Intelectual e Licença

**USO EXCLUSIVO DA MG SETEL.**

Todo o código-fonte, algoritmos, designs e documentação contidos neste repositório são propriedade intelectual exclusiva da **MG Setel**.

É **estritamente proibida** a cópia, modificação, distribuição, engenharia reversa ou qualquer forma de uso não autorizado, sob pena de medidas legais cabíveis.

Consulte o arquivo `LICENSE` para os termos legais completos.

---

## 📞 Suporte e Manutenção

Desenvolvido com rigor técnico e paixão pela excelência.

Para suporte técnico, report de bugs ou solicitações de melhoria, entre em contato diretamente com a equipe de Desenvolvimento de Sistemas da MG Setel.

---
*LogosDecision © 2026 MG Setel - Excelência em Gestão.*
