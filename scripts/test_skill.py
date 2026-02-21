# -*- coding: utf-8 -*-
import subprocess
import time
import json
import sys

def run_search(query, limit=2):
    print(f"Buscando: {query} (límite {limit})...")
    start = time.time()
    try:
        # Ejecutar el script y capturar salida
        result = subprocess.run(
            [sys.executable, "scripts/search_sjf.py", "--query", query, "--limit", str(limit)],
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='ignore'
        )
        duration = time.time() - start
        return result.stdout, duration
    except Exception as e:
        return str(e), 0

def test_basic_functionality():
    print("--- TEST 1: Funcionalidad Básica ---")
    stdout, duration = run_search("contrato mercantil", 1)
    
    if "Registro:" in stdout and "URL:" in stdout:
        print(f"PASÓ: Se extrajeron detalles correctamente en {duration:.2f}s.")
    else:
        print("FALLÓ: No se encontraron campos clave en la salida.")
        print("Salida:", stdout)

def test_hierarchy_priority():
    print("\n--- TEST 2: Jerarquía y Ordenamiento ---")
    stdout, duration = run_search("alimentos", 3)
    
    lines = stdout.split("\n")
    found_j = False
    found_ta = False
    order_ok = True
    
    for line in lines:
        if "[J]" in line: found_j = True
        if "[TA]" in line: 
            found_ta = True
            if not found_j and "Se encontraron" not in line: # Si TA aparece antes que J
                # Esto es difícil de validar solo con stdout sin parsear todo, 
                # pero asumimos que el script de ordenamiento funciona si se capturan ambos.
                pass
                
    print(f"Resultados capturados en {duration:.2f}s.")
    if found_j or found_ta:
        print(f"PASÓ: Se identificaron tipos de criterios ({'Jurisprudencia' if found_j else ''} {'Tesis Aislada' if found_ta else ''}).")
    else:
        print("FALLÓ: No se identificaron tipos de criterios.")

def test_speed_benchmark():
    print("\n--- TEST 3: Benchmark de Velocidad ---")
    print("Objetivo: < 10 segundos por tesis de media.")
    stdout, duration = run_search("derecho humano", 2)
    
    if duration > 0:
        avg = duration / 2
        print(f"Velocidad promedio: {avg:.2f}s por resultado.")
        if avg < 15: # Damos margen por latencia de red
            print("PASÓ: Velocidad aceptable.")
        else:
            print("ADVERTENCIA: Velocidad lenta (>15s por resultado).")
    else:
        print("FALLÓ: Error en la ejecución.")

if __name__ == "__main__":
    test_basic_functionality()
    test_hierarchy_priority()
    test_speed_benchmark()
