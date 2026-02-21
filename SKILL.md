---
name: buscador-juridico
description: Skill de búsqueda de tesis, jurisprudencias y precedentes en el Semanario Judicial de la Federación (SJF) de México. Entiende jerarquía judicial, circuitos y prioridad de criterios.
---

# Buscador Jurídico Mexicano

Busca tesis y jurisprudencias en el **Semanario Judicial de la Federación (SJF)** — la única fuente programática confiable del Poder Judicial.

## Contexto del usuario

- **Circuito:** Noveno Circuito (San Luis Potosí)
- **Prioridad:** Jurisprudencia sobre tesis aislada, SIEMPRE

## Jerarquía del Poder Judicial (de mayor a menor obligatoriedad)

```
1. SCJN — Pleno                        → Obliga a TODOS
2. SCJN — Primera y Segunda Sala       → Obliga a TODOS (salvo Pleno)
3. Plenos Regionales                    → Obliga a TCC de su región
4. Tribunales Colegiados de Circuito    → Obliga en su circuito
```

**Regla de oro:** Un criterio del Pleno prevalece sobre uno de Sala. Uno de Sala prevalece sobre uno de TCC. Uno del Noveno Circuito es directamente aplicable al usuario.

## Formato Obligatorio de Salida
Cada vez que se presente una tesis, es OBLIGATORIO incluir estos tres elementos:
1. **Registro Digital:** El número de identificación único.
2. **URL:** Enlace directo a la tesis en el portal de la SCJN.
3. **Rubro:** El título exacto de la tesis en mayúsculas.

## Tipos de criterio (de mayor a menor fuerza)

| Tipo | Clave | Fuerza | Significado |
|------|-------|--------|------------|
| **Jurisprudencia** | J | VINCULANTE | Obliga a tribunales inferiores. Se forma por reiteración (5 tesis) o por contradicción resuelta |
| **Precedente** | PC | VINCULANTE | Sentencia de SCJN que establece criterio obligatorio |
| **Tesis Aislada** | TA | Solo orientadora | NO obliga. Puede citarse como apoyo pero no es obligatoria |

**SIEMPRE buscar jurisprudencia primero. Solo presentar tesis aisladas si no hay jurisprudencia sobre el tema.**

## Cómo ejecutar búsquedas

```bash
python scripts/search_sjf.py --query "TÉRMINOS" --limit 10
```

El script usa Selenium headless Chrome. Requiere: `pip install selenium webdriver-manager`

## Pruebas y Validación

Para verificar que la skill funciona correctamente y medir el rendimiento:

```bash
python scripts/test_skill.py
```

Este comando valida la extracción de datos, la identificación de jerarquías y el benchmark de velocidad.

## Estrategia de búsqueda inteligente

Cuando el usuario pida buscar un tema, el agente DEBE:

### 1. Descomponer el tema en conceptos jurídicos precisos

❌ MAL: Buscar textualmente lo que dice el usuario
✅ BIEN: Extraer los conceptos jurídicos subyacentes

**Ejemplo:** El usuario dice "acuerdos verbales en contratos mercantiles"

El agente debe pensar:
- **Concepto 1:** Consentimiento verbal → validez del consentimiento en materia mercantil
- **Concepto 2:** Forma del contrato mercantil → ¿se requiere forma escrita?
- **Concepto 3:** Art. 78 Código de Comercio → libertad de forma en contratos mercantiles
- **Concepto 4:** Prueba del contrato verbal → carga probatoria

Búsquedas a ejecutar:
1. `"contrato mercantil consentimiento verbal"`
2. `"forma contrato mercantil código comercio"`
3. `"libertad contractual mercantil"`
4. `"prueba contrato verbal"`

### 2. Priorizar por jerarquía

Al presentar resultados, SIEMPRE ordenar así:
1. Jurisprudencia del Pleno de la SCJN
2. Jurisprudencia de Salas de la SCJN
3. Jurisprudencia de Plenos Regionales
4. Jurisprudencia de TCC (preferir Noveno Circuito)
5. Tesis aisladas (solo si no hay jurisprudencia)

### 3. Filtrar por relevancia

- Descartar tesis de materia penal si el tema es civil/mercantil
- Descartar tesis sobre delitos si el tema es contractual
- Priorizar Undécima y Décima época (criterios actuales)
- Marcar si una tesis fue superada, modificada o interrumpida

### Modo documento

Si el usuario proporciona un documento legal, el agente extrae:
1. Derechos invocados
2. Figuras jurídicas en juego
3. Materia (civil, mercantil, administrativa, penal, laboral, fiscal)
4. Normas citadas (artículos específicos)
5. Conceptos técnicos del área

Y ejecuta búsquedas múltiples con los conceptos extraídos.

### Modo conversación

Si hay contexto en el chat pero no términos explícitos, el agente propone términos y pregunta antes de buscar.

## Glosario rápido

- **Época:** La actual es Undécima (desde 2021). La Décima (2011-2021) sigue siendo muy relevante
- **Rubro:** Título de la tesis que resume el criterio
- **Registro digital:** ID numérico único de cada tesis
- **Noveno Circuito:** San Luis Potosí
