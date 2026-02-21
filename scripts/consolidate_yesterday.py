import glob
import os

files = glob.glob("dump_2031*.txt")
results = []

for f in files:
    with open(f, "r", encoding="utf-8") as file:
        lines = [l.strip() for l in file.readlines() if l.strip()]
        registro = ""
        materia = ""
        rubro = ""
        tipo = ""
        fecha = ""
        
        found_tipo = False
        for i, line in enumerate(lines):
            if "Registro digital:" in line: registro = line.split(":")[-1].strip()
            if "Materia(s):" in line: materia = line.split(":")[-1].strip()
            if "Tipo:" in line: 
                tipo = line.split(":")[-1].strip()
                # El rubro suele ser la siguiente línea significativa
                if i + 1 < len(lines):
                    rubro = lines[i+1]
            if "Esta tesis se publicó el viernes 20 de febrero de 2026" in line:
                fecha = "20/02/2026"

        if fecha == "20/02/2026" and "Penal" in materia:
            results.append({
                "registro": registro,
                "materia": materia,
                "rubro": rubro,
                "url": f"https://sjf2.scjn.gob.mx/detalle/tesis/{registro}"
            })

# Ordenar por registro
results.sort(key=lambda x: x["registro"])

for r in results:
    print(f"REGISTRO: {r['registro']}")
    print(f"MATERIA: {r['materia']}")
    print(f"URL: {r['url']}")
    print(f"RUBRO: {r['rubro']}")
    print("-" * 20)
