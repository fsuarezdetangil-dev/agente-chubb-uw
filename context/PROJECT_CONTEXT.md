# PROJECT_CONTEXT — agente-chubb-uw

## Qué es el sistema
Agente de IA combinado agéntico + RAG construido con LangGraph que automatiza el ciclo de suscripción (underwriting) de pólizas de seguros P&C Commercial Lines. El agente recibe una submission (email del broker + documentación adjunta), la procesa a través de cinco nodos especializados y produce un borrador de cotización, un informe de riesgo y una comunicación al broker — con tres puntos de revisión humana obligatorios para casos que superen umbrales de complejidad o riesgo.

## Cliente
- **Organización:** Chubb EMEA
- **Hub:** Madrid
- **Interlocutor:** Equipo de Innovación / UW Digital

## Caso de uso
Automatización del UW cycle para P&C Commercial Lines:
- Líneas: **Property** y **Casualty**
- Segmento: riesgos estándar (no facultativo, no specialty)
- Canal de entrada: email del broker, portal web, API

## Criterios de éxito de la PoC
Mínimo 4 de 7 métricas deben alcanzar target en 50-100 submissions de prueba:

| Métrica | Target |
|---|---|
| Time-to-quote (modo STP) | < 4 horas |
| Straight-Through Processing rate | > 60 % |
| Extracción de campos críticos | > 92 % accuracy |
| Coste LLM por submission | < 100 EUR |
| UW satisfaction score | > 4.0 / 5.0 |
| LLM-Judge score (output quality) | > 85 / 100 |
| Activación HITL correcta | > 95 % |

## Estado actual
**Fase 8+ — EDD v2.0 en curso** (mejoras de prompts para CA-01 y CA-06)

Ver plan de fases completo en [DEVELOPMENT_PLAN.md](DEVELOPMENT_PLAN.md).
