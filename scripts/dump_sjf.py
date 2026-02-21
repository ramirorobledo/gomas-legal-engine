from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import sys
import time

def dump_detail(registro):
    url = f"https://sjf2.scjn.gob.mx/detalle/tesis/{registro}"
    o = Options()
    o.add_argument("--headless=new")
    o.add_experimental_option("excludeSwitches", ["enable-logging"])
    d = webdriver.Chrome(options=o)
    wait = WebDriverWait(d, 20)
    try:
        d.get(url)
        # Esperar a que el registro digital sea el correcto
        wait.until(EC.text_to_be_present_in_element((By.TAG_NAME, "body"), f"Registro digital: {registro}"))
        time.sleep(1) # Un segundo extra para renderizado
        text = d.find_element(By.TAG_NAME, "body").text
        filename = f"dump_{registro}.txt"
        with open(filename, "w", encoding="utf-8") as f:
            f.write(text)
        print(f"Dump complete for {registro}. Saved to {filename}")
    except Exception as e:
        print(f"Error dumping {registro}: {e}")
    finally:
        d.quit()

if __name__ == "__main__":
    reg = sys.argv[1] if len(sys.argv) > 1 else "2031785"
    dump_detail(reg)
