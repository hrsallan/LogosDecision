# VigilaCore

<div align="center">

![Python](https://img.shields.io/badge/Python-31.0%25-3776AB?style=flat-square&logo=python&logoColor=white)
![HTML](https://img.shields.io/badge/HTML-53.1%25-E34F26?style=flat-square&logo=html5&logoColor=white)
![CSS](https://img.shields.io/badge/CSS-14.6%25-1572B6?style=flat-square&logo=css3&logoColor=white)
![JavaScript](https://img.shields.io/badge/JavaScript-1.3%25-F7DF1E?style=flat-square&logo=javascript&logoColor=black)

**A monitoring and analytics platform for utility reading management**

[🇧🇷 Versão em Português](README.pt-BR.md)

</div>

---

## 🆕 Latest Updates (February 2026)

### Version 2.1 - Bug Fixes & Improvements

**✅ Correções Implementadas:**
1. **Calendário Releitura** - Seletor de data agora filtra corretamente métricas e gráficos
2. **Métricas Porteira** - Removidas métricas redundantes de releitura, adicionados indicadores de porcentagem
3. **Tabela Porteira** - Colunas simplificadas para mostrar apenas dados primários de leitura
4. **Filtro por Região** - Atualização em tempo real de métricas e gráficos ao filtrar por região
5. **Sistema de Ciclos** - Implementação correta dos ciclos mensais de leitura (97, 98, 99)

**🎯 Novos Recursos:**
- **% Não Executada** - Métrica de porcentagem de leituras não executadas
- **% Impedimento** - Métrica de porcentagem de impedimentos
- Sincronização de dados em tempo real melhorada nas visualizações filtradas
- Melhor tratamento de cálculos de ciclo de leitura

**🔧 Melhorias Técnicas:**
- Schema de banco de dados aprimorado com coluna `Impedimentos`
- Tratamento melhorado de parâmetros de data nos endpoints da API
- Melhor validação de dados no processamento de Excel
- Mapeamento de UL regional mais preciso

---

For full documentation, features, and installation instructions, please see below.

## 📋 Overview

VigilaCore is a comprehensive monitoring platform for CEMIG SGL utility reading management, featuring:
- Real-time dashboards for reading operations
- Automated data synchronization from CEMIG portal
- Advanced analytics with historical tracking
- Role-based access control
- Regional and cycle-based filtering

For complete documentation, installation guide, and API reference, please refer to the sections below.
