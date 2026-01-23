import os
import fitz  # PyMuPDF

def garantir_pasta(caminho):
    if not os.path.exists(caminho):
        os.makedirs(caminho)

def limpar_pdf_inteligente(doc, categoria):
    # Preserva integralmente o conteudo original do PDF
    doc_novo = fitz.open()
    
    margem_topo = 0       
    margem_base = 0       
    modo = "Modo Integral"

    for pagina in doc:
        rect = pagina.rect 
        novo_rect = fitz.Rect(0, margem_topo, rect.width, rect.height - margem_base)
        
        nova_pagina = doc_novo.new_page(width=novo_rect.width, height=novo_rect.height)
        nova_pagina.show_pdf_page(nova_pagina.rect, doc, pagina.number, clip=novo_rect)
    
    return doc_novo, modo

def processar_arquivo_especifico(caminho_origem, pasta_destino_raiz, nome_exame, categoria):
    if not os.path.exists(caminho_origem):
        return f"Arquivo nao encontrado: {caminho_origem}"

    try:
        pasta_final = os.path.join(pasta_destino_raiz, nome_exame, categoria)
        garantir_pasta(pasta_final)
        
        nome_arquivo = os.path.basename(caminho_origem)
        if not nome_arquivo.startswith("LIMPO_"):
            nome_saida = f"LIMPO_{nome_arquivo}"
        else:
            nome_saida = nome_arquivo
            
        caminho_final = os.path.join(pasta_final, nome_saida)

        doc_original = fitz.open(caminho_origem)
        doc_limpo, modo_usado = limpar_pdf_inteligente(doc_original, categoria)
        doc_limpo.save(caminho_final)
        doc_limpo.close()
        doc_original.close()
        
        return f"Processado: {nome_arquivo} -> {modo_usado}"

    except Exception as e:
        return f"Erro critico: {e}"