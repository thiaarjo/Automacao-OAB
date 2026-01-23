import os
import sys
from tqdm import tqdm
import limpador_final 

# --- CONFIGURACOES ---
PASTA_RAIZ = "Downloads_OAB"
PASTA_DESTINO = "Provas_Limpas"

def listar_conteudo():
    if not os.path.exists(PASTA_RAIZ):
        print(f"Pasta '{PASTA_RAIZ}' nao encontrada.")
        return None

    exames = {}
    pastas_exames = [d for d in os.listdir(PASTA_RAIZ) if os.path.isdir(os.path.join(PASTA_RAIZ, d))]
    
    for nome_exame in pastas_exames:
        caminho_exame = os.path.join(PASTA_RAIZ, nome_exame)
        conteudo = {"1_Fase_Provas": [], "1_Fase_Gabaritos": [], "2_Fase_Provas": [], "2_Fase_Padrao": []}
        tem_arquivo = False
        
        for categoria in conteudo.keys():
            caminho_cat = os.path.join(caminho_exame, categoria)
            if os.path.exists(caminho_cat):
                arquivos = [f for f in os.listdir(caminho_cat) if f.lower().endswith(".pdf")]
                if arquivos:
                    conteudo[categoria] = arquivos
                    tem_arquivo = True
        
        if tem_arquivo:
            exames[nome_exame] = conteudo
            
    return exames

def main():
    modo_automatico = "--auto" in sys.argv

    while True:
        dados = listar_conteudo()
        if not dados: break

        lista_exames = sorted(list(dados.keys()))
        
        if not modo_automatico:
            print("\n" + "="*60)
            print(f" PAINEL DE CONTROLE (Arquivos Baixados)")
            print("="*60)
            for i, exame in enumerate(lista_exames, 1):
                f1 = len(dados[exame]["1_Fase_Provas"])
                gab = len(dados[exame]["1_Fase_Gabaritos"])
                f2 = len(dados[exame]["2_Fase_Provas"])
                print(f"[{i}] {exame} (F1: {f1} | Gab: {gab} | F2: {f2})")
            print("="*60)
            
            entrada = input("Qual exame processar? (0=Sair, T=Todos): ").upper()
            if entrada == "0": break
        else:
            entrada = "T" 

        exames_alvo = []
        if entrada == "T":
            exames_alvo = lista_exames
        elif entrada.isdigit() and 1 <= int(entrada) <= len(lista_exames):
            exames_alvo = [lista_exames[int(entrada)-1]]
        else:
            print("Opcao invalida.")
            continue

        fila_de_trabalho = []
        
        for exame_escolhido in exames_alvo:
            conteudo = dados[exame_escolhido]
            for cat, arquivos in conteudo.items():
                for arq in arquivos:
                    fila_de_trabalho.append((exame_escolhido, cat, arq))

        if fila_de_trabalho:
            print(f"\nProcessando {len(fila_de_trabalho)} arquivos...")
            
            for nome_exame, categoria, arquivo in tqdm(fila_de_trabalho):
                caminho_origem = os.path.join(PASTA_RAIZ, nome_exame, categoria, arquivo)
                resultado = limpador_final.processar_arquivo_especifico(
                    caminho_origem, PASTA_DESTINO, nome_exame, categoria
                )
            
            print(f"\nLimpeza Concluida.")
        else:
            print("Nada para processar.")

        if modo_automatico:
            break

if __name__ == "__main__":
    main()