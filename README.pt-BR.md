# VigilaCore

<div align="center">

![Python](https://img.shields.io/badge/Python-31.0%25-3776AB?style=flat-square&logo=python&logoColor=white)
![HTML](https://img.shields.io/badge/HTML-53.1%25-E34F26?style=flat-square&logo=html5&logoColor=white)
![CSS](https://img.shields.io/badge/CSS-14.6%25-1572B6?style=flat-square&logo=css3&logoColor=white)
![JavaScript](https://img.shields.io/badge/JavaScript-1.3%25-F7DF1E?style=flat-square&logo=javascript&logoColor=black)

**Plataforma de monitoramento e análise para gestão de leituras**

[🇺🇸 English Version](README.md)

</div>

---

## 🆕 Últimas Atualizações (Fevereiro 2026)

### Versão 2.1 - Correções de Bugs e Melhorias

**✅ Problemas Corrigidos:**

1. **Aba Releitura - Calendário não funcionava**
   - ✅ RESOLVIDO: O seletor de data agora passa corretamente o parâmetro `date` para a API
   - As métricas e gráficos agora atualizam ao trocar de dia
   - Histórico de dados funciona perfeitamente

2. **Aba Porteira - Análise de dados incorreta**
   - ✅ RESOLVIDO: Mapeamento correto de UL regional (dígitos 3-6)
   - Valores de leituras não executadas agora são precisos
   - Releituras não executadas calculadas corretamente

3. **Aba Porteira - Métricas de releitura removidas**
   - ✅ IMPLEMENTADO: Interface limpa focada em leituras
   - Removidas: Total Releituras, Releituras Não Exec.
   - Adicionadas: % Não Executada, Impedimentos, % Impedimento

4. **Filtro por Cidade**
   - ✅ FUNCIONAL: Atualização em tempo real ao selecionar região
   - Métricas, gráficos e tabela se atualizam instantaneamente
   - Funciona para: Araxá, Uberaba, Frutal, ou Geral (todas)

5. **Sistema de Ciclos Mensal**
   - ✅ IMPLEMENTADO: Ciclo 98 configurado corretamente
   - Localidades: 01-88 + 92, 93, 96, 98
   - Filtro automático baseado nos 2 últimos dígitos da UL
   - Suporte para Ciclos 97, 98 e 99

**🎯 Novos Recursos:**
- **% Não Executada**: Porcentagem de leituras não executadas em relação ao total
- **Impedimentos**: Nova coluna mostrando impedimentos (atualmente preparada para dados futuros)
- **% Impedimento**: Porcentagem de impedimentos em relação ao total
- Tabela da Porteira reorganizada e simplificada

**🔧 Melhorias Técnicas:**
- Schema de banco de dados atualizado com coluna `Impedimentos`
- Parâmetro `date` corretamente implementado na API `/api/status/releitura`
- Validação aprimorada de UL regional no processamento de Excel
- Melhores logs de debug para facilitar diagnóstico
- Correção de bugs de sintaxe no `analytics.py`

---

## 📋 Visão Geral

O VigilaCore é uma aplicação web full-stack desenvolvida especificamente para monitorar e analisar dados de leitura de utilidades da **CEMIG (Companhia Energética de Minas Gerais)** através do portal **SGL (Sistema de Gestão de Leitura)**.

O sistema automatiza o processo tedioso de baixar, processar e analisar manualmente relatórios de leitura, fornecendo dashboards em tempo real, métricas e visualizações para dois fluxos de trabalho operacionais críticos:

- **Releitura**: Rastreia e gerencia operações de releitura de medidores
- **Porteira**: Monitora operações de leitura programadas e status de execução

### Valor para o Negócio

- **Elimina trabalho manual**: Downloads automatizados do portal CEMIG SGL
- **Visibilidade em tempo real**: Dashboards ao vivo mostrando status atual
- **Rastreamento histórico**: Trilha de auditoria completa de todas as operações
- **Detecção de duplicatas**: Algoritmos inteligentes para identificar leituras duplicadas
- **Métricas de desempenho**: KPIs e análises para medir eficiência operacional
- **Gestão por ciclos**: Organização de leituras por ciclos mensais
- **Análise regional**: Filtragem e análise por regiões geográficas

---

## ✨ Funcionalidades

### Funcionalidade Principal

- 📊 **Dashboards em Tempo Real**
  - Métricas ao vivo para leituras pendentes, concluídas e atrasadas
  - Gráficos interativos mostrando tendências e distribuição
  - Separação específica por região e comparações
  - Indicadores baseados em porcentagem para taxas de execução

- 🔄 **Sincronização Automatizada de Dados**
  - Downloads programados do portal CEMIG SGL
  - Detecção inteligente de duplicatas
  - Processamento e categorização automática de dados
  - Suporte para ciclos mensais de leitura

- 📈 **Análise Avançada**
  - Análise de tendências históricas
  - Rastreamento de KPIs de desempenho
  - Filtragem por intervalo de datas personalizado
  - Relatórios baseados em região e ciclo
  - Rastreamento e análise de impedimentos

- 🔐 **Controle de Acesso Baseado em Função**
  - Permissões de usuário em vários níveis
  - Isolamento de dados específico por região
  - Autenticação segura com tokens JWT
  - Armazenamento criptografado de senhas

- 📅 **Gestão de Ciclos de Leitura**
  - Suporte para sistema trimestral de ciclos da CEMIG (Ciclos 97, 98, 99)
  - Detecção e filtragem automática de ciclo
  - Métricas e comparações baseadas em ciclo

---

## 🚀 Começando

### Pré-requisitos

- Python 3.9 ou superior
- pip (gerenciador de pacotes Python)
- Navegador web moderno (Chrome, Firefox, Safari, Edge)

### Instalação

1. **Clone o repositório**
   ```bash
   git clone https://github.com/yourusername/VigilaCore.git
   cd VigilaCore
   ```

2. **Instale as dependências**
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure as variáveis de ambiente**
   Crie um arquivo `.env` no diretório raiz:
   ```env
   JWT_SECRET=sua-chave-secreta-aqui
   PORTAL_USERNAME=seu-usuario-portal-cemig
   PORTAL_PASSWORD=sua-senha-portal-cemig
   RELEITURA_MANAGER_USERNAME=GRTRI
   ```

4. **Inicialize o banco de dados**
   ```bash
   cd backend
   python -c "from core.database import init_db; init_db()"
   ```

5. **Inicie o servidor**
   ```bash
   python app.py
   ```

6. **Acesse a aplicação**
   Abra seu navegador e navegue para `http://localhost:5001`

---

## 📚 Documentação da API

### Endpoints de Autenticação

#### POST /api/register
Registra uma nova conta de usuário

#### POST /api/login
Autentica usuário e recebe token JWT

### Endpoints de Sincronização de Dados

#### POST /api/sync/releitura
Aciona sincronização de dados de releitura do portal CEMIG

#### POST /api/sync/porteira
Aciona sincronização de dados de leitura de porteira

### Endpoints de Status e Métricas

#### GET /api/status/releitura?region=<region>&date=<date>
Obtém status de releitura, métricas e dados históricos

**Parâmetros de Query:**
- `region` (opcional): Filtra por região (Araxá, Uberaba, Frutal, ou "all")
- `date` (opcional): Data para dados históricos no formato YYYY-MM-DD

#### GET /api/porteira/table?ciclo=<ciclo>&regiao=<regiao>
Obtém dados da tabela de porteira com filtragem opcional

**Parâmetros de Query:**
- `ciclo` (opcional): Filtra por ciclo (97, 98, ou 99)
- `regiao` (opcional): Filtra por região

---

## 🛠️ Pilha Tecnológica

### Backend
- **Flask**: Framework web
- **SQLite**: Banco de dados
- **Pandas**: Processamento de dados
- **JWT**: Autenticação
- **APScheduler**: Agendamento de tarefas
- **Selenium**: Automação web

### Frontend
- **HTML5/CSS3**: Estrutura e estilização
- **JavaScript**: Lógica do lado do cliente
- **Chart.js**: Visualização de dados
- **Lucide Icons**: Ícones de UI

---

## 📄 Licença

Este projeto está licenciado sob a Licença MIT - veja o arquivo [LICENSE](LICENSE) para detalhes.

---

**⭐ Se você achar este projeto útil, por favor considere dar uma estrela!**
