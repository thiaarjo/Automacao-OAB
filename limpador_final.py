import os
import fitz  # PyMuPDF

def garantir_pasta(caminho):
    if not os.path.exists(caminho):
        os.makedirs(caminho)

def limpar_pdf_inteligente(doc, categoria):
    """
    Reconstrói o PDF mantendo APENAS as páginas com conteúdo real de questões.
    Remove: Capa, Contracapa, Questionários, Rascunhos e Páginas em Branco.
    """
    doc_novo = fitz.open()
    modo = "Limpeza Inteligente"
    
    # Se NÃO for prova (ex: for gabarito de 1 pagina), copia tudo e sai
    if "PROVA" not in categoria.upper():
        doc_novo.insert_pdf(doc)
        return doc_novo, "Cópia Integral (Gabarito/Padrão)"

    bloquear_resto = False # Trava de segurança para o final do arquivo

    for i, pagina in enumerate(doc):
        # Extrai o texto para analisar o conteudo
        texto = pagina.get_text().upper()
        
        # --- FILTRO 1: REMOVER CAPA ---
        # Geralmente a página 0 ou 1 contendo instrucoes
        if i == 0 and ("SUA PROVA" in texto or "CADERNO DE PROVA" in texto or "INSTRUÇÕES" in texto):
            continue # Pula a capa

        # --- FILTRO 2: DETECTAR O FIM (QUESTIONÁRIO / RASCUNHO) ---
        # A OAB coloca um questionário no final. Assim que acharmos, paramos tudo.
        if "QUESTIONÁRIO DE PERCEPÇÃO" in texto or "FOLHA DE RASCUNHO" in texto:
            bloquear_resto = True
        
        if bloquear_resto:
            continue # Ignora esta página e todas as seguintes

        # --- FILTRO 3: PÁGINAS EM BRANCO ---
        # Se a página tiver menos de 50 caracteres (sujeira ou numeração apenas), ignora.
        # CUIDADO: Imagens sem texto podem cair aqui, mas na OAB é raro ter imagem sem enunciado.
        if len(texto.strip()) < 50:
            continue

        # --- SUCESSO: PÁGINA VÁLIDA ---
        # Copia a página original para o novo documento
        doc_novo.insert_pdf(doc, from_page=i, to_page=i)
    
    return doc_novo, modo

def processar_arquivo_especifico(caminho_origem, pasta_destino_raiz, nome_exame, categoria):
    if not os.path.exists(caminho_origem):
        return f"Arquivo nao encontrado: {caminho_origem}"

    try:
        pasta_final = os.path.join(pasta_destino_raiz, nome_exame, categoria)
        garantir_pasta(pasta_final)
        
        nome_arquivo = os.path.basename(caminho_origem)
        # Adiciona prefixo se não tiver
        if not nome_arquivo.startswith("LIMPO_"):
            nome_saida = f"LIMPO_{nome_arquivo}"
        else:
            nome_saida = nome_arquivo
            
        caminho_final = os.path.join(pasta_final, nome_saida)

        print(f"Processando: {nome_arquivo}...")
        doc_original = fitz.open(caminho_origem)
        
        # Chama a nova função inteligente
        doc_limpo, modo_usado = limpar_pdf_inteligente(doc_original, categoria)
        
        # Salva (com 'deflate' para comprimir e otimizar)
        doc_limpo.save(caminho_final, deflate=True)
        
        # Fecha tudo
        doc_limpo.close()
        doc_original.close()
        
        return f"✅ Processado: {nome_arquivo} ({modo_usado})"

    except Exception as e:
        return f"❌ Erro critico: {e}"

# --- SE VOCÊ TIVER UM LOOP PRINCIPAL DE TESTE, PODE USAR ISSO PARA RODAR ---
if __name__ == "__main__":
    # Exemplo de uso manual para teste
    arquivo_teste = "19112023 - Caderno de Prova - Tipo 1.pdf" # Mude para seu arquivo
    if os.path.exists(arquivo_teste):
        print(processar_arquivo_especifico(arquivo_teste, "Provas_Limpas", "Teste_Manual", "1_PROVA"))