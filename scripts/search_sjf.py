# -*- coding: utf-8 -*-
"""
search_sjf.py — Busca tesis en el Semanario Judicial de la Federación.
Optimizado para velocidad y robustez.
"""
import sys, time, argparse
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

BASE = "https://sjf2.scjn.gob.mx"
SEARCH = f"{BASE}/busqueda-principal-tesis"

def _driver():
    try:
        from webdriver_manager.chrome import ChromeDriverManager
        svc = Service(ChromeDriverManager().install())
    except Exception:
        svc = Service()
    
    o = Options()
    # Usar headless=new para mejor compatibilidad y velocidad
    o.add_argument("--headless=new")
    o.add_argument("--no-sandbox")
    o.add_argument("--disable-dev-shm-usage")
    o.add_argument("--disable-gpu")
    o.add_argument("--window-size=1920,1080")
    o.add_argument("--log-level=3")
    o.add_experimental_option("excludeSwitches", ["enable-logging"])
    
    d = webdriver.Chrome(service=svc, options=o)
    d.set_page_load_timeout(30)
    return d

def search_sjf(query, limit=100):
    # Detectar si es un registro digital directo (7 dígitos)
    is_registro = query.isdigit() and len(query) == 7
    
    d = _driver()
    wait = WebDriverWait(d, 20)
    try:
        if is_registro:
            url = f"https://sjf2.scjn.gob.mx/detalle/tesis/{query}"
            r = _extract_detail(d, url, wait)
            return [r] if r else []

        d.get(SEARCH)
        # Búsqueda inicial
        inp = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "input[type='text']")))
        inp.clear()
        inp.send_keys(query)
        inp.send_keys(Keys.ENTER)
        
        # Esperar resultados
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, 'a[href*="detalle/tesis"]')))
        
        # El sitio carga resultados por scroll o paginación. 
        # Para 100 resultados, intentaremos recolectar de la lista principal antes de entrar al detalle.
        urls = []
        seen = set()
        
        # Intentar recolectar hasta el límite
        tries = 0
        while len(urls) < limit and tries < 5:
            links = d.find_elements(By.CSS_SELECTOR, 'a[href*="detalle/tesis"]')
            for l in links:
                href = l.get_attribute("href") or ""
                if href and href not in seen:
                    seen.add(href)
                    urls.append(href)
            
            if len(urls) < limit:
                # Intentar scroll o esperar a que carguen más si es infinito
                d.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                time.sleep(2)
                tries += 1
            else:
                break
        
        urls = urls[:limit]
        if not urls:
            return []

        print(f"Propagando extracción para {len(urls)} tesis...")
        results = []
        # En una versión futura podríamos usar hilos aquí, pero Selenium no es thread-safe por driver.
        # Optimizamos la extracción individual para que sea instantánea si ya cargó.
        for i, url in enumerate(urls, 1):
            if i % 10 == 0: print(f"  Extrayendo {i}/{len(urls)}...")
            r = _extract_detail(d, url, wait)
            if r:
                results.append(r)
        
        return results
    except Exception as e:
        print(f"Error durante la búsqueda masiva: {e}")
        return []
    finally:
        d.quit()

def _extract_detail(d, url, wait):
    try:
        d.get(url)
        # Esperar carga real
        wait.until(EC.presence_of_element_located((By.XPATH, "//*[contains(text(), 'Registro digital:')]")))
        
        # Pequeña pausa adicional para asegurar renderizado JS completo del contenido
        time.sleep(2)
        
        # Obtener el texto de todo el body
        raw_text = d.execute_script("return document.body.innerText")
        lines = [l.strip() for l in raw_text.split("\n") if l.strip()]

        r = {"url": url}
        fields_map = {
            "Registro digital:": "registro",
            "Instancia:": "instancia",
            "Materia(s):": "materia",
            "Tesis:": "clave",
            "Fuente:": "fuente",
            "Tipo:": "tipo",
        }

        for line in lines:
            if "Época" in line and "epoca" not in r:
                r["epoca"] = line.split("[")[0].strip()
            for prefix, key in fields_map.items():
                if prefix in line:
                    val = line.split(prefix)[-1].strip()
                    if val and val != "-1":
                        if "  " in val: val = val.split("  ")[0]
                        r[key] = val

        # Rubro: Línea en mayúsculas más larga que no sea metadato
        potential_rubros = [l for l in lines if len(l) > 60 and l == l.upper() and not any(p in l for p in fields_map)]
        if potential_rubros:
            r["rubro"] = potential_rubros[0]

        # Cuerpo completo: Capturar TODO lo que esté entre el rubro y el final de la página
        if "rubro" in r:
            content = []
            found_rubro = False
            for line in lines:
                if found_rubro:
                    if "Esta tesis se publicó" in line or "UBICACIÓN" in line or "Suprema Corte de Justicia" in line:
                        break
                    # No repetir metadatos que ya tenemos
                    if not any(line.startswith(p) for p in fields_map):
                        content.append(line)
                elif line == r["rubro"]:
                    found_rubro = True
            
            if content:
                r["texto"] = "\n".join(content)

        return r if r.get("registro") else None
    except Exception as e:
        print(f"Error extrayendo {url}: {e}")
        return None

def sort_results(results):
    """
    Ordena los resultados según la jerarquía establecida en SKILL.md:
    1. Jurisprudencia > Tesis Aislada
    2. SCJN Pleno > Salas > Plenos Regionales > TCC
    3. Noveno Circuito (San Luis Potosí) tiene prioridad en TCC
    """
    def rank(r):
        score = 0
        tipo = (r.get("tipo", "") or "").upper()
        if "JURISPRUDENCIA" in tipo: score += 1000
        elif "PRECEDENTE" in tipo: score += 900
        
        instancia = (r.get("instancia", "") or "").upper()
        if "PLENO" in instancia and "SUPREMA" in instancia: score += 500
        elif "SALA" in instancia: score += 400
        elif "PLENOS REGIONALES" in instancia: score += 300
        elif "TRIBUNALES COLEGIADOS" in instancia: score += 200
        
        fuente = (r.get("fuente", "") or "").upper()
        if "NOVENO CIRCUITO" in fuente: score += 50
        return score

    return sorted(results, key=rank, reverse=True)

def analyze_themes(results):
    """
    Analiza los rubros de los resultados para identificar subtemas comunes.
    """
    themes = {
        "Procedencia y Requisitos": [],
        "Oposición de la Víctima": [],
        "Plan de Reparación": [],
        "Revocación por Incumplimiento": [],
        "Sobreseimiento y Extinción": [],
        "Recursos y Amparo": [],
        "Otros (Medidas, etc.)": []
    }
    
    for r in results:
        rubro = (r.get("rubro", "") or "").upper()
        # Clasificación simple por palabras clave
        if any(x in rubro for x in ["PROCEDENCIA", "REQUISITOS", "PLAN DE REPARACIÓN"]):
            themes["Procedencia y Requisitos"].append(r)
        if any(x in rubro for x in ["OPOSICIÓN", "VÍCTIMA", "OFENDIDA"]):
            themes["Oposición de la Víctima"].append(r)
        if any(x in rubro for x in ["REVOCACIÓN", "INCUMPLIMIENTO"]):
            themes["Revocación por Incumplimiento"].append(r)
        if any(x in rubro for x in ["EXTINCIÓN", "SOBRESEIMIENTO", "CUMPLIMIENTO"]):
            themes["Sobreseimiento y Extinción"].append(r)
        if any(x in rubro for x in ["APELACIÓN", "AMPARO", "RECURSO", "DEFINITIVIDAD"]):
            themes["Recursos y Amparo"].append(r)
    
    # Filtrar temas vacíos
    return {k: v for k, v in themes.items() if v}

def main():
    p = argparse.ArgumentParser(description="Buscar tesis en el SJF")
    p.add_argument("--query", "-q", required=True)
    p.add_argument("--limit", "-l", type=int, default=10)
    p.add_argument("--analyze", action="store_true", help="Analizar subtemas")
    a = p.parse_args()

    start_time = time.time()
    results = search_sjf(a.query, a.limit)
    sorted_results = sort_results(results)
    end_time = time.time()

    if not sorted_results:
        print(f"Sin resultados para: '{a.query}'")
        sys.exit(0)

    if a.analyze:
        themes = analyze_themes(sorted_results)
        print(f"\nMAPA JURÍDICO: '{a.query}' ({len(sorted_results)} resultados)")
        print("="*60)
        for theme, items in themes.items():
            print(f"\n[ {theme} ] - {len(items)} tesis")
            for i, it in enumerate(items[:3], 1): # Mostrar top 3 por tema
                tag = "[J]" if "JURISPRUDENCIA" in (it.get('tipo','') or '').upper() else "[TA]"
                print(f"  {i}. {tag} {it.get('rubro','')}")
        
        print("\n" + "="*60)
        print("¿Sobre cuál de estos subtemas específicos deseas profundizar?")
    else:
        print(f"\nSe encontraron {len(sorted_results)} resultados en {end_time - start_time:.2f} s")
        # Mostrar resultados resumidos si son muchos
        for i, r in enumerate(sorted_results, 1):
            tipo_tag = "[J]" if "JURISPRUDENCIA" in (r.get('tipo','') or '').upper() else "[TA]"
            print(f"\n[{i}] {tipo_tag} {r.get('rubro', 'SIN RUBRO')}")
            print(f"    Registro: {r.get('registro')} | {r.get('instancia')}")
            if a.limit <= 5: # Solo mostrar texto completo si el límite es bajo
                print(f"    URL: {r.get('url')}")
                print(f"    TEXTO: {r.get('texto','')[:500]}...")

if __name__ == "__main__":
    main()

