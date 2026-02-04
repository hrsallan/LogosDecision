# VigilaCore — Revisão de Arquitetura e Funcionalidades

> **Escopo desta revisão**  
> Baseado no código presente no ZIP do projeto (estrutura `backend/` + `frontend/`).  
> O foco é: arquitetura atual, fluxo de dados, pontos fortes/fracos e recomendações práticas de evolução.

---

## 1) Visão geral (como o sistema funciona hoje)

O **VigilaCore** é um sistema web com:

- **Backend (Flask)** expondo uma API REST em `/api/*` com autenticação via **JWT**.
- **Banco local (SQLite)** (`backend/data/vigilacore.db`) com dados segregados por `user_id` (multiusuário).
- **Frontend estático** (`frontend/views/*.html`) consumindo a API via `fetch` e exibindo métricas/gráficos (Chart.js).
- **Sincronização automática** via **Selenium** (módulo `core/portal_scraper.py`) para baixar relatórios do portal e depois processar Excel para popular o banco.
- **Scheduler** (APScheduler) para rodar a sincronização em horários “redondos”.

**Páginas principais do frontend:**
- `dashboard.html`: visão geral + (para perfis privilegiados) seleção de funcionário/usuário para métricas.
- `releitura.html`: upload/sync + gráficos + métricas de Releituras.
- `porteira.html`: upload/sync + gráficos/tabelas + métricas de Porteira.
- `usuario.html`: credenciais do portal por usuário (configuração).
- `administracao.html`: painel/placeholder de administração (o backend já possui endpoints administrativos).

---

## 2) Mapa da arquitetura (alto nível)

```
[Frontend: HTML/CSS/JS]  --->  [API Flask: /api/*]  --->  [SQLite: vigilacore.db]
           |                            |
           |                            +--> [Scheduler APScheduler]
           |                            +--> [Scraper Selenium / portal_scraper.py]
           |                            +--> [Analytics: leitura de Excel -> normalização -> DB]
           |
           +--> [JWT em localStorage] -> Authorization: Bearer <token>
```

---

## 3) Funcionalidades existentes (por área)

### Autenticação / Usuários
- Registro e login por usuário.
- Senhas com hash (bcrypt).
- JWT com expiração (24h).
- Dados no DB isolados por `user_id`.

### Releituras
- Upload de planilha + processamento (`deep_scan_excel`) -> persistência.
- Métricas: total/pendentes/concluídas, detalhamento, “vencimentos”.
- Checagem de duplicidade por hash do arquivo.

### Porteira
- Upload de planilha + processamento (`deep_scan_porteira_excel`) -> persistência.
- Métricas, resumo, tabelas e gráficos.
- Histórico de uploads.
- Regras de “ciclos rurais” e agregações por UL/Razão.

### Scraping / Sincronização
- Selenium abre portal e realiza download.
- Download em `data/exports/`.
- Rotina de “esperar download completar”.
- Scheduler evita disparo concorrente (execução sequencial Releitura -> Porteira).

### Administração (backend)
- Endpoint para listar usuários (sem dados sensíveis).
- Endpoint para start/stop do scheduler.
- Proteções por role (RBAC) no backend.

---

## 4) Pontos fortes

1) **Separação razoável por camadas**
   - `core/portal_scraper.py` (integração externa), `core/analytics.py` (processamento), `core/database.py` (persistência), `app.py` (API/rotas).

2) **Boa preocupação com “robustez” de scraping**
   - Imports “lazy” no scraper para não quebrar o backend sem Selenium.
   - Espera de término de download e limpeza de pasta de exports.

3) **Multiusuário com segregação real**
   - Tabelas principais carregam `user_id`, permitindo visão isolada por usuário e habilitando futura visão por equipe.

4) **Segurança básica correta**
   - Senhas não são armazenadas em texto puro (hash).
   - Credenciais do portal no DB são armazenadas criptografadas (Fernet).
   - JWT para autenticação nas rotas protegidas.

5) **CORS/preflight bem tratado**
   - Resposta rápida para `OPTIONS` evita o clássico “Failed to fetch” quando há `Authorization`.

---

## 5) Pontos fracos / riscos atuais

### Arquitetura / manutenção
- **`app.py` concentra muitas responsabilidades**: autenticação, RBAC, lógica de negócio e endpoints extensos. Isso aumenta custo de manutenção.
- **Ausência de versionamento/migração formal de DB**: hoje há migrações “na mão”; isso funciona, mas é fácil quebrar em produção sem um controle de versão.
- **RBAC espalhado** (comparações de string de role em vários pontos). Isso tende a virar “colcha de retalhos”.

### Frontend / UX
- **Navegação duplicada em várias páginas** (sidebar repetida em muitos `.html`). Qualquer mudança exige editar N arquivos.
- **Regras de visibilidade** historicamente foram feitas “na página” (ex.: dashboard), o que exige cuidado para não ficar inconsistente.

### Segurança / operação
- **Segredos com defaults** (`JWT_SECRET` com fallback “segredo-super-seguro”): risco se alguém rodar sem configurar env.
- **JWT no localStorage**: é comum, mas expõe risco maior em caso de XSS.
- **Controle de acesso por “apenas UI”** não é suficiente — precisa ser sempre reforçado no backend (vocês já fazem isso em endpoints administrativos, mas vale padronizar).

### Qualidade / confiabilidade
- **Poucos testes automatizados** (aparenta não haver testes unitários/integrados).
- **Monitoramento e logs**: existe logging no scheduler, mas o backend/API poderia ter logs estruturados e rastreio de erros.

---

## 6) Melhorias futuras (priorizadas)

### Curto prazo (alto impacto, baixo esforço)
- **Padronizar RBAC em decorators** (ex.: `@require_roles("diretoria","gerencia")`) para reduzir duplicação.
- **Centralizar visibilidade do menu** em 1 JS comum (ou 1 template), para evitar inconsistências.
- **Configurar `JWT_SECRET` obrigatório** e falhar ao iniciar se não existir em produção.

### Médio prazo
- **Blueprints Flask**:
  - `auth_bp`, `releitura_bp`, `porteira_bp`, `admin_bp`, `scheduler_bp`.
  - Reduz tamanho do `app.py` e melhora organização.
- **Migração de DB** (Alembic ou um “schema_version” com migrations incrementais).
- **Camada de serviços**:
  - `services/releitura_service.py`, `services/porteira_service.py` para encapsular regras e reduzir SQL espalhado.

### Longo prazo
- **Observabilidade**:
  - Logs estruturados (JSON), correlação por request-id.
  - Dashboard de erros e métricas (Sentry/Prometheus).
- **Revisão de segurança**:
  - Refresh token, expiração menor, rotação.
  - Hardening para XSS/CSRF dependendo de como o frontend é servido.

---

## 7) Checklist rápido de “próximos passos”
- [ ] Consolidar roles e permissões em 1 lugar (backend).
- [ ] Criar UI de “Administração” de verdade (gerenciar usuários/roles, ver logs, status do scheduler).
- [ ] Adotar migrações de banco versionadas.
- [ ] Reduzir duplicação do menu (template ou includes).

---

# Apêndice — Mudanças implementadas neste pacote (pedido atual)

1) **Usuários: adicionadas colunas `nome` e `base`** no cadastro (migração segura).
2) **Novo sistema de roles**: `diretoria`, `gerencia`, `analistas` (com migração automática de `admin -> diretoria` e `user -> analistas`).
3) **Visibilidade**: `diretoria` e `analistas` **não veem** a aba **“Área do Usuário”** e são bloqueados ao tentar abrir `usuario.html`.
4) **Aba Porteira**: permanece sem seletor de usuário (nenhuma UI de seleção foi mantida nessa página).

