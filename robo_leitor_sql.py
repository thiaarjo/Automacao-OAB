import sqlite3
import os
import re
import fitz  # PyMuPDF
import pdfplumber 
from tqdm import tqdm

# --- CONFIGURAÇÕES ---
PASTA_LIMPOS = "Provas_Limpas"
NOME_BANCO = "OAB_Questoes.db"

def criar_banco():
    conn = sqlite3.connect(NOME_BANCO)
    cursor = conn.cursor()
    
    cursor.execute('''CREATE TABLE IF NOT EXISTS exames (id INTEGER PRIMARY KEY AUTOINCREMENT, nome_exame TEXT UNIQUE)''')
    
    cursor.execute('''CREATE TABLE IF NOT EXISTS arquivos (id INTEGER PRIMARY KEY AUTOINCREMENT, exame_id INTEGER, nome_arquivo TEXT UNIQUE, fase TEXT, materia TEXT, cor_prova TEXT, tipo_arquivo TEXT, FOREIGN KEY(exame_id) REFERENCES exames(id))''')
    
    cursor.execute('''CREATE TABLE IF NOT EXISTS questoes (
        id INTEGER PRIMARY KEY AUTOINCREMENT, 
        arquivo_id INTEGER, 
        numero INTEGER, 
        tipo TEXT, 
        enunciado TEXT, 
        alternativa_a TEXT,
        alternativa_b TEXT,
        alternativa_c TEXT,
        alternativa_d TEXT,
        gabarito_letra TEXT, 
        gabarito_texto TEXT, 
        FOREIGN KEY(arquivo_id) REFERENCES arquivos(id)
    )''')
    
    cursor.execute('''CREATE TABLE IF NOT EXISTS gabaritos_objetivas (id INTEGER PRIMARY KEY AUTOINCREMENT, exame_id INTEGER, cor_prova TEXT, numero_questao INTEGER, letra_resposta TEXT, FOREIGN KEY(exame_id) REFERENCES exames(id), UNIQUE(exame_id, cor_prova, numero_questao) ON CONFLICT REPLACE)''')
    
    conn.commit()
    return conn

# ==============================================================================
# 1. FUNÇÕES AUXILIARES (NORMALIZAÇÃO)
# ==============================================================================

def roman_to_int(s):
    """Converte XXXIX para 39"""
    rom_val = {'I': 1, 'V': 5, 'X': 10, 'L': 50, 'C': 100, 'D': 500, 'M': 1000}
    int_val = 0
    for i in range(len(s)):
        if i > 0 and rom_val[s[i]] > rom_val[s[i - 1]]:
            int_val += rom_val[s[i]] - 2 * rom_val[s[i - 1]]
        else:
            int_val += rom_val[s[i]]
    return int_val

def normalizar_nome_exame(texto):
    """Padroniza para 'XXº EXAME DE ORDEM'"""
    texto_upper = texto.upper()
    
    # Procura Numeral Romano (XXXIX)
    match_romano = re.search(r'\b([IVXLCDM]+)\b[\s\n]+EXAME', texto_upper)
    if match_romano:
        try:
            numero = roman_to_int(match_romano.group(1))
            return f"{numero}º EXAME DE ORDEM"
        except: pass

    # Procura Numeral Arábico (39)
    match_num = re.search(r'(\d{2,3})[ºo]?[\s\n]+EXAME', texto_upper)
    if match_num:
        return f"{int(match_num.group(1))}º EXAME DE ORDEM"
    
    # Procura no nome do arquivo se o texto falhar
    match_solto = re.search(r'(\d{2,3})', texto_upper)
    if match_solto:
        return f"{int(match_solto.group(1))}º EXAME DE ORDEM"

    return "EXAME DESCONHECIDO"

def identificar_cor_prova(texto, nome_arquivo):
    texto_upper = texto.upper()
    nome_upper = nome_arquivo.upper()
    scores = {
        "TIPO_1_BRANCA": texto_upper.count("BRANCA") + (20 if "TIPO 1" in nome_upper or "BRANCA" in nome_upper else 0),
        "TIPO_2_VERDE": texto_upper.count("VERDE") + (20 if "TIPO 2" in nome_upper or "VERDE" in nome_upper else 0),
        "TIPO_3_AMARELA": texto_upper.count("AMARELA") + (20 if "TIPO 3" in nome_upper or "AMARELA" in nome_upper else 0),
        "TIPO_4_AZUL": texto_upper.count("AZUL") + (20 if "TIPO 4" in nome_upper or "AZUL" in nome_upper else 0)
    }
    melhor = max(scores, key=scores.get)
    return melhor if scores[melhor] > 0 else "TIPO_1_BRANCA"

# ==============================================================================
# 2. LEITORES DE PROVA E GABARITO
# ==============================================================================

def extrair_texto_ordenado(caminho_pdf):
    """Lê a prova respeitando as colunas"""
    doc = fitz.open(caminho_pdf)
    texto_completo = ""
    for pagina in doc:
        width = pagina.rect.width
        height = pagina.rect.height
        blocos = pagina.get_text("blocks")
        
        # Filtra cabeçalho/rodapé
        blocos_validos = [b for b in blocos if b[1] > 45 and b[3] < (height - 45)]
        
        # Ordena: Coluna Esquerda -> Direita
        def chave_ordenacao(b):
            coluna = 0 if b[0] < (width / 2) else 1
            y_pos = int(b[1]) 
            return (coluna, y_pos)
            
        blocos_validos.sort(key=chave_ordenacao)
        
        for b in blocos_validos:
            texto_limpo = b[4].replace('\n', ' ').strip()
            if len(texto_limpo) < 3 and not texto_limpo.replace('.', '').replace(')', '').isdigit():
                continue
            if "CONSELHO FEDERAL" in texto_limpo.upper(): continue
            texto_completo += texto_limpo + "\n"
            
    doc.close()
    return texto_completo

def extrair_questoes(texto_bruto):
    """Extrai enunciados e alternativas"""
    linhas = texto_bruto.split('\n')
    questoes = []
    q_atual = None
    estado = "BUSCANDO" 
    
    re_q = re.compile(r'^(?:QUESTÃO\s+)?(\d{1,2})(?:[\.\)\s]|$)', re.IGNORECASE)
    
    def salvar():
        if q_atual and (len(q_atual['alternativas']) >= 2 or q_atual['enunciado']):
            questoes.append(q_atual)

    for linha in linhas:
        linha = linha.strip()
        if not linha: continue
        
        match = re_q.match(linha)
        if match and len(linha) < 10: 
            numero = int(match.group(1))
            if 1 <= numero <= 100:
                if q_atual and abs(numero - q_atual['numero']) > 10 and numero != 1:
                    pass 
                else:
                    salvar()
                    q_atual = {"numero": numero, "enunciado": "", "alternativas": {}}
                    estado = "ENUNCIADO"
                    continue

        if q_atual is None: continue 

        # Split para separar alternativas na mesma linha
        pedacos = re.split(r'(?:\s|^)(A|B|C|D)[\)\.]\s*', linha)
        
        if len(pedacos) > 1:
            texto_ant = pedacos[0].strip()
            if texto_ant:
                if estado == "ENUNCIADO": q_atual['enunciado'] += " " + texto_ant
                elif "ALT" in estado: q_atual['alternativas'][estado.split("_")[1]] += " " + texto_ant
            
            i = 1
            while i < len(pedacos):
                letra = pedacos[i].upper()
                if i + 1 < len(pedacos):
                    texto = pedacos[i+1].strip()
                    if letra in "ABCD":
                        q_atual['alternativas'][letra] = texto
                        estado = f"ALT_{letra}"
                i += 2
            continue

        if estado == "ENUNCIADO": q_atual['enunciado'] += " " + linha
        elif "ALT" in estado: q_atual['alternativas'][estado.split("_")[1]] += " " + linha

    salvar()
    return questoes

def extrair_gabarito_layout_oab(caminho_pdf):
    """
    Lê gabaritos definitivos da OAB que usam layout de GRADE (Horizontal).
    Mapeia PROVA 1 -> BRANCA, PROVA 2 -> VERDE, etc.
    """
    respostas = []
    print(f"   -> Lendo Gabarito (Modo Grade Horizontal)...")
    
    mapa_cores = {
        "PROVA 1": "TIPO_1_BRANCA",
        "PROVA 2": "TIPO_2_VERDE",
        "PROVA 3": "TIPO_3_AMARELA",
        "PROVA 4": "TIPO_4_AZUL"
    }

    try:
        with pdfplumber.open(caminho_pdf) as pdf:
            for page in pdf.pages:
                tabelas = page.extract_tables()
                
                # Procura por tabelas que tenham "PROVA X" no texto próximo ou dentro
                texto_pagina = page.extract_text()
                
                for tabela in tabelas:
                    cor_atual = None
                    
                    # Tenta descobrir a cor baseada no conteúdo da tabela ou cabeçalho
                    # Simplificação: assume que a ordem das tabelas segue a lógica ou procura string
                    # Como pdfplumber extrai tabelas isoladas, vamos varrer as células
                    str_tabela = str(tabela).upper()
                    
                    for chave, valor in mapa_cores.items():
                        if chave in str_tabela or chave in texto_pagina:
                            # Refinamento: se a tabela atual tem muitos dados, e o texto da pagina tem "PROVA X"
                            # Assumimos a cor da pagina (geralmente uma prova por tabela/seção)
                            # Mas cuidado com tabelas de correspondência
                            if "CORRESPONDÊNCIA" not in texto_pagina and "CORRESPONDÊNCIA" not in str_tabela:
                                cor_atual = valor
                                # Se achou a cor específica na tabela, ganha prioridade
                                if chave in str_tabela: 
                                    break 
                    
                    if not cor_atual: continue

                    # Processa a Grade: Linha de Numeros -> Linha de Letras
                    ultima_linha_numeros = []
                    
                    for linha in tabela:
                        # Limpa a linha
                        linha_limpa = [str(c).replace('\n', '').strip() for c in linha if c]
                        if not linha_limpa: continue
                        
                        # Verifica se é uma linha de CABEÇALHO (só números)
                        eh_numero = all(c.isdigit() for c in linha_limpa)
                        
                        # Verifica se é uma linha de RESPOSTAS (A, B, C, D, *, X)
                        eh_resposta = all(c in "ABCD*X" for c in linha_limpa)
                        
                        if eh_numero:
                            ultima_linha_numeros = [int(x) for x in linha_limpa]
                        elif eh_resposta and ultima_linha_numeros:
                            # Pareia Números com Respostas
                            if len(ultima_linha_numeros) == len(linha_limpa):
                                for i, letra in enumerate(linha_limpa):
                                    num = ultima_linha_numeros[i]
                                    respostas.append({
                                        "cor": cor_atual,
                                        "num": num,
                                        "letra": letra
                                    })
                            ultima_linha_numeros = [] # Reseta após usar
                            
    except Exception as e:
        print(f"Erro na leitura de tabela: {e}")

    # --- FALLBACK PARA FORMATO ANTIGO (Tabela Vertical) ---
    if len(respostas) < 10:
        print("      ⚠️ Grade horizontal falhou, tentando layout vertical...")
        try:
            with pdfplumber.open(caminho_pdf) as pdf:
                for page in pdf.pages:
                    for tabela in page.extract_tables():
                        for linha in tabela:
                            linha = [str(c).strip() if c else "" for c in linha]
                            if not linha or not linha[0].isdigit(): continue
                            try:
                                num = int(linha[0])
                                if len(linha) >= 5: # Tabela completa
                                    respostas.append({"cor": "TIPO_1_BRANCA", "num": num, "letra": linha[1]})
                                    respostas.append({"cor": "TIPO_2_VERDE", "num": num, "letra": linha[2]})
                                    respostas.append({"cor": "TIPO_3_AMARELA", "num": num, "letra": linha[3]})
                                    respostas.append({"cor": "TIPO_4_AZUL", "num": num, "letra": linha[4]})
                            except: pass
        except: pass

    return respostas

# ==============================================================================
# 3. ORQUESTRAÇÃO
# ==============================================================================

def processar_tudo():
    if not os.path.exists(PASTA_LIMPOS):
        print(f"❌ Pasta '{PASTA_LIMPOS}' não encontrada!")
        return

    conn = criar_banco()
    cursor = conn.cursor()
    
    arquivos = [os.path.join(r, f) for r, d, fs in os.walk(PASTA_LIMPOS) for f in fs if f.lower().endswith(".pdf")]
    
    for caminho in tqdm(arquivos):
        nome_arquivo = os.path.basename(caminho)
        eh_gabarito = "GABARITO" in nome_arquivo.upper()
        
        # --- NORMALIZAÇÃO DO NOME DO EXAME ---
        try:
            doc = fitz.open(caminho)
            texto_inicial = (doc[0].get_text() + "\n" + doc[1].get_text()) if len(doc) > 1 else doc[0].get_text()
            doc.close()
        except: texto_inicial = ""

        nome_exame = normalizar_nome_exame(texto_inicial)
        if nome_exame == "EXAME DESCONHECIDO":
            nome_exame = normalizar_nome_exame(nome_arquivo)

        cursor.execute("INSERT OR IGNORE INTO exames (nome_exame) VALUES (?)", (nome_exame,))
        cursor.execute("SELECT id FROM exames WHERE nome_exame = ?", (nome_exame,))
        exame_id = cursor.fetchone()[0]

        # --- GABARITO ---
        if eh_gabarito:
            lista = extrair_gabarito_layout_oab(caminho)
            if lista:
                print(f"   ✅ Gabarito {nome_exame}: {len(lista)} respostas extraídas.")
                for item in lista:
                    cursor.execute("INSERT INTO gabaritos_objetivas (exame_id, cor_prova, numero_questao, letra_resposta) VALUES (?, ?, ?, ?)", (exame_id, item['cor'], item['num'], item['letra']))
            else:
                print(f"   ❌ AVISO: Gabarito vazio ou não reconhecido para {nome_arquivo}")

        # --- PROVA ---
        else:
            texto = extrair_texto_ordenado(caminho)
            cor = identificar_cor_prova(texto, nome_arquivo)
            print(f"   📄 Prova: {nome_exame} ({cor})")
            
            cursor.execute("INSERT OR IGNORE INTO arquivos (exame_id, nome_arquivo, fase, cor_prova, tipo_arquivo) VALUES (?, ?, '1_FASE', ?, 'PROVA')", (exame_id, nome_arquivo, cor))
            cursor.execute("SELECT id FROM arquivos WHERE nome_arquivo = ?", (nome_arquivo,))
            arquivo_id = cursor.fetchone()[0]

            questoes = extrair_questoes(texto)
            print(f"      -> {len(questoes)} questões extraídas.")
            
            for q in questoes:
                alt_a = q['alternativas'].get('A', '')
                alt_b = q['alternativas'].get('B', '')
                alt_c = q['alternativas'].get('C', '')
                alt_d = q['alternativas'].get('D', '')

                cursor.execute("""
                    INSERT INTO questoes 
                    (arquivo_id, numero, tipo, enunciado, alternativa_a, alternativa_b, alternativa_c, alternativa_d) 
                    VALUES (?, ?, 'OBJETIVA', ?, ?, ?, ?, ?)
                """, (arquivo_id, q['numero'], q['enunciado'], alt_a, alt_b, alt_c, alt_d))

        conn.commit()

    print("\n💍 Cruzando Questões com Gabaritos...")
    
    # Query de atualização reforçada
    cursor.execute("""
        UPDATE questoes
        SET gabarito_letra = (
            SELECT g.letra_resposta
            FROM gabaritos_objetivas g
            JOIN arquivos a ON a.id = questoes.arquivo_id
            WHERE g.exame_id = a.exame_id
            AND g.numero_questao = questoes.numero
            AND (
                g.cor_prova = a.cor_prova 
                OR 
                (a.cor_prova = 'TIPO_1_BRANCA' AND g.cor_prova = 'TIPO_1_BRANCA')
            )
            ORDER BY CASE WHEN g.cor_prova = a.cor_prova THEN 1 ELSE 2 END
            LIMIT 1
        )
        WHERE tipo = 'OBJETIVA'
    """)
    
    conn.commit()
    conn.close()
    print("✅ Banco atualizado! Verifique se os NULLs sumiram.")

if __name__ == "__main__":
    processar_tudo()