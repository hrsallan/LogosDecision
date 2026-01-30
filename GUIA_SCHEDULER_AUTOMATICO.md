# 🤖 Guia de Automação - Scheduler de Downloads Automáticos

## 📋 Visão Geral

O VigilaCore agora possui um **sistema de automação** que baixa automaticamente os relatórios do portal CEMIG SGL em intervalos configurados, sem necessidade de intervenção manual.

### ✨ Funcionalidades

- ⏰ **Downloads automáticos** de hora em hora (ou intervalo personalizado)
- 🔁 **Execução sequencial (Releitura → Porteira)** para evitar abrir duas abas/janelas ao mesmo tempo
- 🕐 **Horário configurável** (ex: apenas das 07h às 17h)
- 🔄 **Sincronização inteligente** de Releitura e Porteira
- 🚫 **Detecção de duplicatas** (não processa o mesmo arquivo 2x)
- 📊 **Atualização automática** das métricas e gráficos
- 📝 **Logs detalhados** de todas as operações

---

## 🚀 Instalação Rápida

### 1. Instalar Dependências

```bash
cd backend
pip install -r requirements.txt
```

**Dependência principal:** APScheduler
```bash
pip install apscheduler
```

### 2. Configurar o .env

Copie o arquivo de exemplo:
```bash
cp .env.example .env
```

Edite o `.env` e configure:

```ini
# Credenciais do Portal CEMIG
PORTAL_USER=seu_usuario
PORTAL_PASS=sua_senha

# Ativar Scheduler
SCHEDULER_ENABLED=1

# Horário de operação (7h às 17h)
SCHEDULER_START_HOUR=7
SCHEDULER_END_HOUR=17

# Intervalo (60 minutos = 1 hora)
SCHEDULER_INTERVAL_MINUTES=60

# O que baixar automaticamente
SCHEDULER_AUTO_RELEITURA=1
SCHEDULER_AUTO_PORTEIRA=1

# ID do usuário (IMPORTANTE!)
SCHEDULER_USER_ID=1
```

### 3. Descobrir seu User ID

**Opção A - Via SQLite Browser:**
1. Abra o arquivo: `backend/data/vigilacore.db`
2. Tabela `users` → veja o campo `id`
3. Normalmente o primeiro usuário tem `id = 1`

**Opção B - Via Python:**
```bash
cd backend
python -c "import sqlite3; conn=sqlite3.connect('data/vigilacore.db'); print(conn.execute('SELECT id, username FROM users').fetchall())"
```

### 4. Iniciar o Servidor

```bash
cd backend
python app.py
```

Você verá logs assim:
```
✅ Arquivo .env carregado de: /caminho/do/.env
📋 Configurações do Scheduler:
   - Habilitado: True
   - Horário: 7h às 17h
   - Intervalo: 60 minutos
   - Auto Releitura: True
   - Auto Porteira: True
   - User ID: 1
✅ Job de RELEITURA agendado (a cada 60 min)
✅ Job de PORTEIRA agendado (a cada 60 min)
🚀 Scheduler automático iniciado com sucesso!
⏰ Execuções programadas: 7h às 17h
```

---

## ⚙️ Configurações Detalhadas

### Variáveis do .env

| Variável | Valores | Descrição |
|----------|---------|-----------|
| `SCHEDULER_ENABLED` | `0` ou `1` | Liga/desliga o scheduler |
| `SCHEDULER_START_HOUR` | `0-23` | Hora de início (ex: `7` = 07:00) |
| `SCHEDULER_END_HOUR` | `0-23` | Hora de fim (ex: `17` = 17:00) |
| `SCHEDULER_INTERVAL_MINUTES` | `1-1440` | Intervalo em minutos |
| `SCHEDULER_AUTO_RELEITURA` | `0` ou `1` | Baixar relatório de Releitura |
| `SCHEDULER_AUTO_PORTEIRA` | `0` ou `1` | Baixar relatório de Porteira |
| `SCHEDULER_USER_ID` | número | ID do usuário no banco |

### Exemplos de Configuração

**Exemplo 1: A cada hora, das 7h às 17h**
```ini
SCHEDULER_START_HOUR=7
SCHEDULER_END_HOUR=17
SCHEDULER_INTERVAL_MINUTES=60
```
→ Executa às: 7h, 8h, 9h, 10h, 11h, 12h, 13h, 14h, 15h, 16h (10x por dia)

**Exemplo 2: A cada 30 minutos, das 8h às 18h**
```ini
SCHEDULER_START_HOUR=8
SCHEDULER_END_HOUR=18
SCHEDULER_INTERVAL_MINUTES=30
```
→ Executa às: 8h, 8:30, 9h, 9:30... até 17:30 (20x por dia)

**Exemplo 3: A cada 2 horas, o dia todo**
```ini
SCHEDULER_START_HOUR=0
SCHEDULER_END_HOUR=23
SCHEDULER_INTERVAL_MINUTES=120
```
→ Executa às: 0h, 2h, 4h, 6h, 8h, 10h, 12h, 14h, 16h, 18h, 20h, 22h (12x por dia)

**Exemplo 4: Apenas Releitura, das 9h às 12h**
```ini
SCHEDULER_START_HOUR=9
SCHEDULER_END_HOUR=12
SCHEDULER_AUTO_RELEITURA=1
SCHEDULER_AUTO_PORTEIRA=0
SCHEDULER_INTERVAL_MINUTES=60
```
→ Executa apenas releitura às: 9h, 10h, 11h (3x por dia)

---

## 📊 Monitoramento

### Via Logs do Console

Quando o scheduler roda, você vê logs como:

```
✅ Execução bem-sucedida:
2026-01-30 07:00:02 - INFO - 🔄 Iniciando sync automático de RELEITURA...
2026-01-30 07:00:45 - INFO - ✅ Arquivo baixado: /caminho/releitura.xlsx
2026-01-30 07:00:47 - INFO - ✅ Releitura sincronizada: 23 registros processados

⚠️ Arquivo duplicado:
2026-01-30 08:00:02 - INFO - 🔄 Iniciando sync automático de RELEITURA...
2026-01-30 08:00:45 - INFO - ℹ️ Relatório já processado anteriormente (duplicado)

❌ Erro no download:
2026-01-30 09:00:02 - INFO - 🔄 Iniciando sync automático de RELEITURA...
2026-01-30 09:01:15 - ERROR - ❌ Erro no sync de releitura: Timeout na conexão
```

### Via API (Status do Scheduler)

**Endpoint:** `GET /api/scheduler/status`

**Resposta:**
```json
{
  "enabled": true,
  "running": true,
  "schedule": "7h - 17h",
  "interval_minutes": 60,
  "auto_releitura": true,
  "auto_porteira": true,
  "user_id": 1,
  "within_schedule": true,
  "jobs": [
    {
      "id": "releitura_sync",
      "name": "Sync Automático - Releitura",
      "next_run": "2026-01-30T08:00:00"
    },
    {
      "id": "porteira_sync",
      "name": "Sync Automático - Porteira",
      "next_run": "2026-01-30T08:00:00"
    }
  ]
}
```

### Controlar via API (Admin)

**Parar o Scheduler:**
```bash
POST /api/scheduler/toggle
{
  "action": "stop"
}
```

**Iniciar o Scheduler:**
```bash
POST /api/scheduler/toggle
{
  "action": "start"
}
```

⚠️ **Nota:** Apenas usuários com role `admin` podem controlar o scheduler via API.

---

## 🔧 Troubleshooting

### Problema: Scheduler não inicia

**Sintoma:**
```
ℹ️ Scheduler desabilitado (SCHEDULER_ENABLED=0)
```

**Solução:**
Verifique no `.env`:
```ini
SCHEDULER_ENABLED=1  # ← deve ser 1
```

---

### Problema: "SCHEDULER_USER_ID não configurado"

**Sintoma:**
```
❌ SCHEDULER_USER_ID não configurado no .env - scheduler não iniciado
```

**Solução:**
1. Descubra seu User ID (ver passo 3 da instalação)
2. Adicione no `.env`:
```ini
SCHEDULER_USER_ID=1
```

---

### Problema: Downloads não acontecem no horário esperado

**Sintoma:**
Scheduler rodando mas nada acontece.

**Diagnóstico:**
Veja nos logs:
```
⏰ Fora do horário agendado - pulando sync de releitura
```

**Solução:**
Verifique se está no horário configurado:
- Hora atual: 18:00
- Configurado: `START_HOUR=7` e `END_HOUR=17`
- Resultado: ❌ Fora do horário (17h = até 16:59)

**Ajuste:**
```ini
SCHEDULER_END_HOUR=18  # agora roda até 17:59
```

---

### Problema: "Dependências do sincronizador não instaladas"

**Sintoma:**
```
❌ Erro: Dependências não instaladas: selenium, pyautogui...
```

**Solução:**
```bash
pip install selenium pyautogui python-dotenv apscheduler
```

Ou instale tudo de uma vez:
```bash
pip install -r requirements.txt
```

---

### Problema: Selenium/ChromeDriver não funciona

**Sintoma:**
```
❌ WebDriver não encontrado
```

**Solução:**
Instale o webdriver-manager:
```bash
pip install webdriver-manager
```

Ou baixe manualmente o ChromeDriver:
- https://chromedriver.chromium.org/
- Coloque no PATH do sistema

---

### Problema: Relatórios duplicados

**Sintoma:**
```
ℹ️ Relatório já processado anteriormente (duplicado)
```

**Explicação:**
Isso é **normal e esperado**! O sistema detecta quando o portal ainda não atualizou e não reprocessa o mesmo arquivo.

**Não é erro** - é uma proteção inteligente.

---

## 🎯 Cenários de Uso

### Cenário 1: Monitoramento durante o expediente

**Objetivo:** Acompanhar releituras em tempo real durante o dia de trabalho.

**Configuração:**
```ini
SCHEDULER_ENABLED=1
SCHEDULER_START_HOUR=7    # Início do expediente
SCHEDULER_END_HOUR=18     # Fim do expediente
SCHEDULER_INTERVAL_MINUTES=60
SCHEDULER_AUTO_RELEITURA=1
SCHEDULER_AUTO_PORTEIRA=0  # Só releitura
```

**Resultado:**
- Downloads automáticos a cada hora das 7h às 17h
- Total de 11 downloads por dia
- Apenas relatório de releitura

---

### Cenário 2: Atualização frequente

**Objetivo:** Capturar mudanças rapidamente.

**Configuração:**
```ini
SCHEDULER_INTERVAL_MINUTES=30  # A cada 30 min
SCHEDULER_START_HOUR=8
SCHEDULER_END_HOUR=17
```

**Resultado:**
- Downloads a cada 30 minutos
- 18 downloads por dia (8h, 8:30, 9h, 9:30... 16:30)

---

### Cenário 3: Economia de recursos

**Objetivo:** Minimizar uso de recursos e acessos ao portal.

**Configuração:**
```ini
SCHEDULER_INTERVAL_MINUTES=120  # A cada 2 horas
SCHEDULER_START_HOUR=8
SCHEDULER_END_HOUR=16
```

**Resultado:**
- Downloads a cada 2 horas
- 4 downloads por dia (8h, 10h, 12h, 14h)

---

## 📈 Benefícios da Automação

✅ **Economia de tempo** - Não precisa fazer download manual  
✅ **Dados sempre atualizados** - Métricas em tempo real  
✅ **Histórico consistente** - Capturas regulares ao longo do dia  
✅ **Detecção automática** de releituras realizadas  
✅ **Sem intervenção** - Funciona em background  
✅ **Logs auditáveis** - Rastreamento completo de operações  

---

## 🔐 Segurança

### Credenciais

- ✅ Credenciais ficam apenas no `.env` (nunca no código)
- ✅ `.env` está no `.gitignore` (não vai pro Git)
- ✅ Use credenciais de um usuário com permissões limitadas

### Recomendações

1. **Não use credenciais de admin** do portal
2. **Crie um usuário específico** para automação
3. **Proteja o arquivo .env** (chmod 600 no Linux)
4. **Use HTTPS** se expor o backend externamente
5. **Monitore os logs** regularmente

---

## 📝 Manutenção

### Verificar se está rodando

```bash
# Linux/Mac
ps aux | grep "python app.py"

# Ver logs em tempo real
tail -f /caminho/do/log/vigilacore.log
```

### Reiniciar após mudanças no .env

```bash
# Pare o servidor (Ctrl+C)
# Reinicie
python app.py
```

As novas configurações serão carregadas automaticamente.

---

## 🆘 Suporte

**Problemas comuns:**
1. Verifique se todas as dependências estão instaladas
2. Confirme que o `.env` está configurado corretamente
3. Verifique se o ChromeDriver está acessível
4. Veja os logs para identificar erros específicos

**Logs importantes:**
- ✅ = Sucesso
- ⚠️ = Aviso (normal em alguns casos)
- ❌ = Erro (precisa correção)

---

## 🎓 Exemplo Completo de Uso

### Passo a Passo

1. **Instalar**
```bash
cd backend
pip install -r requirements.txt
```

2. **Configurar .env**
```bash
cp .env.example .env
nano .env  # ou editor de sua preferência
```

Adicionar:
```ini
PORTAL_USER=joao.silva
PORTAL_PASS=senha123
SCHEDULER_ENABLED=1
SCHEDULER_START_HOUR=7
SCHEDULER_END_HOUR=17
SCHEDULER_INTERVAL_MINUTES=60
SCHEDULER_AUTO_RELEITURA=1
SCHEDULER_AUTO_PORTEIRA=1
SCHEDULER_USER_ID=1
```

3. **Iniciar**
```bash
python app.py
```

4. **Verificar logs**
```
🚀 Scheduler automático iniciado com sucesso!
⏰ Execuções programadas: 7h às 17h
⚡ Executando sync inicial imediatamente...
🔄 Iniciando sync automático de RELEITURA...
✅ Arquivo baixado: /data/exports/releitura_20260130.xlsx
✅ Releitura sincronizada: 23 registros processados
```

5. **Monitorar pelo Dashboard**
- Abra o dashboard
- Veja as métricas atualizando automaticamente
- Observe o gráfico sendo preenchido ao longo do dia

---

**🎉 Pronto! Seu VigilaCore agora está totalmente automatizado!**

Dúvidas? Verifique os logs ou entre em contato com o suporte.
