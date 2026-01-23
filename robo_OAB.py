import os
import time
import requests
from tqdm import tqdm
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import Select
from webdriver_manager.chrome import ChromeDriverManager

# --- CONFIGURACAO ---
PASTA_DOWNLOADS = "Downloads_OAB"

def iniciar_navegador():
    options = webdriver.ChromeOptions()
    options.add_argument("--start-maximized")
    # options.add_argument("--headless")
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)
    return driver

def baixar_arquivo(url, nome_arquivo, pasta_destino):
    if not os.path.exists(pasta_destino):
        os.makedirs(pasta_destino)
    
    caminho_completo = os.path.join(pasta_destino, nome_arquivo)
    
    if os.path.exists(caminho_completo):
        print(f"Arquivo ja existe: {nome_arquivo}")
        return

    try:
        resposta = requests.get(url, stream=True)
        tamanho_total = int(resposta.headers.get('content-length', 0))
        
        with open(caminho_completo, 'wb') as arquivo, tqdm(
            desc=nome_arquivo[:20],
            total=tamanho_total,
            unit='iB',
            unit_scale=True,
            unit_divisor=1024,
            leave=False
        ) as barra:
            for chunk in resposta.iter_content(chunk_size=1024):
                size = arquivo.write(chunk)
                barra.update(size)
        print(f"Salvo em '{os.path.basename(pasta_destino)}': {nome_arquivo}")
    except Exception as e:
        print(f"Erro ao baixar: {e}")

def limpar_nome_arquivo(texto):
    proibidos = ['<', '>', ':', '"', '/', '\\', '|', '?', '*']
    for char in proibidos:
        texto = texto.replace(char, '')
    return texto.strip() + ".pdf"

def extrair_arquivos_fases(driver):
    print("\nBuscando Provas e Gabaritos (Fase 1 e 2)...")
    arquivos_mapa = {}
    contador = 1
    
    tabelas = driver.find_elements(By.CLASS_NAME, "tabela-padrao")
    
    if not tabelas:
        return {}

    for tabela in tabelas:
        try:
            titulo = tabela.find_element(By.TAG_NAME, "th").text.upper()
            
            # Filtro de conteudo relevante
            eh_fase_1 = "1ª" in titulo or "OBJETIVA" in titulo
            eh_fase_2 = "2ª" in titulo or "PRÁTICO" in titulo
            
            if not eh_fase_1 and not eh_fase_2:
                continue 

            links = tabela.find_elements(By.TAG_NAME, "a")
            
            for link in links:
                nome = link.text.strip()
                url = link.get_attribute("href")
                nome_upper = nome.upper()
                
                if nome and url and ".pdf" in url.lower():
                    
                    pasta_final = "Outros"
                    tag_visual = "[?]"

                    if eh_fase_1:
                        if "GABARITO" in nome_upper:
                            pasta_final = "1_Fase_Gabaritos"
                            tag_visual = "[GAB 1a]"
                        else:
                            pasta_final = "1_Fase_Provas"
                            tag_visual = "[PROVA 1a]"
                            
                    elif eh_fase_2:
                        if "PADRÃO" in nome_upper or "RESPOSTA" in nome_upper:
                            pasta_final = "2_Fase_Padrao"
                            tag_visual = "[PADRAO 2a]"
                        else:
                            pasta_final = "2_Fase_Provas"
                            tag_visual = "[PROVA 2a]"

                    arquivos_mapa[contador] = {
                        "tag": tag_visual,
                        "pasta_destino": pasta_final,
                        "nome_original": nome,
                        "nome_arquivo": limpar_nome_arquivo(nome),
                        "url": url
                    }
                    contador += 1
        except Exception:
            continue

    return arquivos_mapa

def main():
    driver = iniciar_navegador()
    try:
        print("Acessando site da OAB...")
        driver.get("https://examedeordem.oab.org.br/EditaisProvas?NumeroExame=11535")
        time.sleep(3)
        
        dropdown = Select(driver.find_element(By.ID, "cmb-edital"))
        opcoes = {i: opt.text.strip() for i, opt in enumerate(dropdown.options) if "Selecione" not in opt.text}
        
        chaves = sorted(list(opcoes.keys()))
        opcoes_final = {k: opcoes[k] for k in chaves}
        
        while True:
            print("\n" + "="*80)
            print(f" LISTA DE EXAMES DISPONIVEIS ")
            print("="*80)
            
            lista_visual = list(opcoes_final.values())
            for i, nome in enumerate(lista_visual, 1):
                print(f"[{i}] {nome}")
            
            print("="*80)
            entrada = input("\nDigite o NUMERO do exame (ou 0 para sair): ")
            if entrada == "0": break
            
            if entrada.isdigit() and 1 <= int(entrada) <= len(lista_visual):
                nome_exame = lista_visual[int(entrada)-1]
                print(f"\nCarregando exame: {nome_exame}...")
                
                Select(driver.find_element(By.ID, "cmb-edital")).select_by_visible_text(nome_exame)
                time.sleep(5) 
                
                arquivos = extrair_arquivos_fases(driver)
                
                if not arquivos:
                    print("Nenhum arquivo de PROVA encontrado neste exame.")
                    print(" (Verifique se o exame escolhido possui provas liberadas)")
                    continue

                print("\n" + "-"*80)
                print(f" MATERIAL DE ESTUDO: {nome_exame}")
                print("-"*80)
                
                for i, dados in arquivos.items():
                    print(f"[{i:02d}] {dados['tag']:<12} {dados['nome_original']}")
                
                print("-"*80)
                print("OPCOES:")
                print(" 'T'   = Baixar TUDO (Provas + Gabaritos + Padroes)")
                print(" 'PRO' = Baixar apenas CADERNOS DE PROVA (Fase 1 e 2)")
                print(" 'GAB' = Baixar apenas GABARITOS E PADROES")
                
                escolha = input("O que baixar? ").strip().upper()
                
                downloads = []
                if escolha == 'T':
                    downloads = list(arquivos.values())
                elif escolha == 'PRO':
                    downloads = [a for a in arquivos.values() if "PROVA" in a['tag']]
                elif escolha == 'GAB':
                    downloads = [a for a in arquivos.values() if "GAB" in a['tag'] or "PADRAO" in a['tag']]
                else:
                    try:
                        ids = [int(x.strip()) for x in escolha.split(',')]
                        for i in ids:
                            if i in arquivos: downloads.append(arquivos[i])
                    except: pass
                
                if downloads:
                    print(f"\nBaixando {len(downloads)} arquivos...")
                    for item in downloads:
                        pasta_final = os.path.join(PASTA_DOWNLOADS, nome_exame.replace(" ", "_"), item['pasta_destino'])
                        baixar_arquivo(item['url'], item['nome_arquivo'], pasta_final)
                    
                    try:
                        os.startfile(os.path.join(PASTA_DOWNLOADS, nome_exame.replace(" ", "_")))
                    except: pass
                    print("\nFinalizado.")
                
                input("\nPressione ENTER para voltar...")

    except Exception as e:
        print(f"Erro Fatal: {e}")
    finally:
        driver.quit()

if __name__ == "__main__":
    main()