# Ejemplos de Búsqueda Jurídica

## 1. Buscar jurisprudencia sobre IVA (materia administrativa)

```bash
python scripts/search_sjf.py --query "IVA acreditamiento" --tipo jurisprudencia --materia administrativa --limit 5
```

## 2. Buscar tesis aislada sobre derecho a la salud

```bash
python scripts/search_sjf.py --query "derecho a la salud" --tipo aislada --materia constitucional --limit 10
```

## 3. Buscar acciones de inconstitucionalidad

```bash
python scripts/search_bj.py --query "matrimonio igualitario" --tipo accion --limit 5
```

## 4. Buscar controversias constitucionales

```bash
python scripts/search_bj.py --query "competencia municipal" --tipo controversia --limit 5
```

## 5. Buscar sentencias en el Buscador Jurídico

```bash
python scripts/search_bj.py --query "amparo directo laboral" --tipo sentencia --limit 5
```

## 6. Buscar tesis vigentes en materia fiscal (TFJA)

```bash
python scripts/search_tfja.py --query "deducción de gastos" --estado vigente --limit 10
```

## 7. Búsqueda unificada en todas las fuentes

```bash
python scripts/search_unified.py --query "presunción de inocencia" --sources all --limit 5
```

## 8. Búsqueda solo en SJF y BJ con formato JSON

```bash
python scripts/search_unified.py --query "libertad de expresión" --sources sjf,bj --format json --limit 10
```

## 9. Búsqueda con IA (JulIA) en lenguaje coloquial

```bash
python scripts/search_julia.py --query "¿puedo deducir gastos médicos de mis impuestos?" --source julia
```

## 10. Consulta a JusticIA con pregunta natural

```bash
python scripts/search_julia.py --query "¿qué dice la SCJN sobre el derecho al agua?" --source justicia
```

## 11. Buscar por registro digital específico

```bash
python scripts/search_sjf.py --query "2024000" --campo registro --limit 1
```

## 12. Buscar por rubro de tesis

```bash
python scripts/search_sjf.py --query "AMPARO DIRECTO EN REVISIÓN" --campo rubro --limit 5
```

---

## Casos de uso frecuentes para abogados

### Preparar una demanda de amparo
1. Buscar jurisprudencia aplicable: `--tipo jurisprudencia --materia [materia]`
2. Buscar tesis que soporten los argumentos: `--tipo aislada`
3. Verificar que no haya criterios contrarios en el BJ

### Investigar un tema fiscal
1. Buscar en TFJA: `search_tfja.py --query "[tema]" --estado vigente`
2. Complementar con SJF: `search_sjf.py --query "[tema]" --materia administrativa`
3. Unificar: `search_unified.py --query "[tema]" --sources sjf,tfja`

### Consulta rápida con IA
1. Preguntar en lenguaje natural a JulIA o JusticIA
2. Profundizar con búsqueda formal en SJF/BJ
