import glob
import os

files = glob.glob("dump_*.txt")
results = []

for f in files:
    try:
        with open(f, "r", encoding="utf-8") as file:
            content = file.read()
            if "20 de febrero de 2026" in content and "Materia(s):" in content and "Penal" in content:
                # Re-reading to extract structured data
                file.seek(0)
                lines = [l.strip() for l in file.readlines() if l.strip()]
                registro = ""
                rubro = ""
                
                for i, line in enumerate(lines):
                    if "Registro digital:" in line:
                        registro = line.split(":")[-1].strip()
                    if "Tipo:" in line:
                        # The rubro is usually the next line
                        if i + 1 < len(lines):
                            rubro = lines[i+1]
                
                if registro and rubro:
                    results.append({
                        "registro": registro,
                        "rubro": rubro,
                        "url": f"https://sjf2.scjn.gob.mx/detalle/tesis/{registro}"
                    })
    except:
        pass

results.sort(key=lambda x: x["registro"])

for r in results:
    print(f"REGISTRO: {r['registro']}")
    print(f"URL: {r['url']}")
    print(f"RUBRO: {r['rubro']}")
    print("-" * 30)
