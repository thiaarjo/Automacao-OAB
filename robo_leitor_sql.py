import sqlite3
import os
import re
import fitz  # PyMuPDF
from tqdm import tqdm

# --- CONFIGURACOES ---
PASTA_LIMPOS = "Provas_Limpas"
NOME_BANCO = "OAB_Questoes.db"

def criar_banco():
    conn = sqlite3.connect(NOME_BANCO)
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS exames (id INTEGER PRIMARY KEY AUTOINCREMENT, nome_exame TEXT UNIQUE)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS arquivos (id INTEGER PRIMARY KEY AUTOINCREMENT, exame_id INTEGER, nome_arquivo TEXT UNIQUE, fase TEXT, materia TEXT, cor_prova TEXT, tipo_arquivo TEXT, FOREIGN KEY(exame_id) REFERENCES exames(id))''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS questoes (id INTEGER PRIMARY KEY AUTOINCREMENT, arquivo_id INTEGER, numero INTEGER, tipo TEXT, enunciado TEXT, gabarito_letra TEXT, gabarito_texto TEXT, FOREIGN KEY(arquivo_id) REFERENCES arquivos(id))''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS alternativas (id INTEGER PRIMARY KEY AUTOINCREMENT, questao_id INTEGER, letra TEXT, texto TEXT, FOREIGN KEY(questao_id) REFERENCES questoes(id))''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS gabaritos_objetivas (id INTEGER PRIMARY KEY AUTOINCREMENT, exame_id INTEGER, cor_prova TEXT, numero_questao INTEGER, letra_resposta TEXT, FOREIGN KEY(exame_id) REFERENCES exames(id), UNIQUE(exame_id, cor_prova, numero_questao) ON CONFLICT REPLACE)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS gabaritos_discursivas (id INTEGER PRIMARY KEY AUTOINCREMENT, exame_id INTEGER, materia TEXT, numero_questao INTEGER, texto_resposta TEXT, FOREIGN KEY(exame_id) REFERENCES exames(id), UNIQUE(exame_id, materia, numero_questao) ON CONFLICT REPLACE)''')
    conn.commit()
    return conn

# ==============================================================================
# PARSERS
# ==============================================================================

def identificar_cor_prova(texto):
    texto = texto.upper()
    contagem = {"BRANCO": texto.count("BRANCO")+texto.count("TIPO 1"), "VERDE": texto.count("VERDE")+texto.count("TIPO 2"), "AMARELO": texto.count("AMARELO")+texto.count("TIPO 3"), "AZUL": texto.count("AZUL")+texto.count("TIPO 4")}
    cor = max(contagem, key=contagem.get)
    return cor if contagem[cor] > 0 else "DESCONHECIDO"

def identificar_materia(texto, nome_arquivo):
    materias = ["ADMINISTRATIVO", "CIVIL", "CONSTITUCIONAL", "TRABALHO", "EMPRESARIAL", "PENAL", "TRIBUTÁRIO"]
    t = (texto + nome_arquivo).upper()
    for m in materias:
        if m in t: return m
    return "GERAL"

def extrair_questoes_objetivas(texto):
    lista = []
    partes = re.split(r'(QUESTÃO\s+\d+)', texto, flags=re.IGNORECASE)
    if len(partes) > 10:
        for i in range(1, len(partes), 2):
            try:
                num = int(re.search(r'\d+', partes[i]).group())
                processar_alternativas(num, partes[i+1], lista)
            except: pass
    else:
        partes = re.split(r'\n\s*(\d{1,2})\s*\n', texto)
        if len(partes) > 10:
            for i in range(1, len(partes), 2):
                try:
                    num = int(partes[i])
                    processar_alternativas(num, partes[i+1], lista)
                except: pass
    return lista

def processar_alternativas(numero, conteudo, lista_destino):
    alts = {}
    padrao = r'(?:\s|\n)(?:\(|)([A-D])(?:\)|\.)\s'
    partes = re.split(padrao, conteudo)
    if len(partes) >= 5: 
        enunciado = partes[0].strip()
        x = 1
        while x < len(partes) - 1:
            letra = partes[x]
            texto = partes[x+1].strip().replace('\n', ' ')
            if letra in "ABCD": alts[letra] = texto
            x += 2
        if len(alts) >= 2: lista_destino.append({"numero": numero, "enunciado": enunciado, "alternativas": alts})

def extrair_gabarito_objetivo_blocado(texto):
    mapa = {}
    texto_upper = texto.upper()
    posicoes = []
    for cor in ["BRANCO", "VERDE", "AMARELO", "AZUL"]:
        match = re.search(rf'TIPO.*?{cor}', texto_upper, flags=re.DOTALL)
        if match: posicoes.append({"cor": cor, "inicio": match.end()})
    posicoes.sort(key=lambda x: x["inicio"])
    for i, item in enumerate(posicoes):
        fim = posicoes[i+1]["inicio"] if i+1 < len(posicoes) else len(texto_upper)
        gab = re.sub(r'[^ABCD]', '', texto_upper[item["inicio"]:fim])[:80]
        if len(gab) >= 10: mapa[item["cor"]] = [(idx+1, l) for idx, l in enumerate(gab)]
    return mapa

# ==============================================================================
# FASE 2: TRATAMENTO DE GABARITOS
# ==============================================================================

def limpar_resposta_discursiva(texto_bruto):
    # Filtra linhas inuteis sem cortar o conteudo relevante
    linhas = texto_bruto.split('\n')
    linhas_boas = []
    
    ignorar_termos = [
        "GABARITO COMENTADO", "COMENTÁRIO SOBRE A QUESTÃO", 
        "DISTRIBUIÇÃO DOS PONTOS", "ITEM DA QUESTÃO", 
        "PONTUAÇÃO", "TOTAL"
    ]
    
    for linha in linhas:
        l = linha.strip()
        if not l: continue 
        
        eh_lixo = False
        for termo in ignorar_termos:
            if termo in l.upper():
                eh_lixo = True
                break
        if eh_lixo: continue
        
        # Filtro de notas numericas
        if re.match(r'^[\d\s.,\/]+$', l):
            continue
            
        linhas_boas.append(l)
        
    return "\n".join(linhas_boas)

def extrair_respostas_discursivas_complexas(texto):
    respostas = []
    
    # Processamento da Peca
    if "PEÇA" in texto.upper() or "GABARITO COMENTADO" in texto.upper():
        partes = re.split(r'QUESTÃO\s+1', texto, flags=re.IGNORECASE)
        resp_peca = limpar_resposta_discursiva(partes[0])
        
        if len(resp_peca) > 20: 
            respostas.append({"numero": 0, "resposta": resp_peca})
        
        resto = texto if len(partes) == 1 else partes[1]
    else:
        resto = texto

    # Processamento das Questoes (1 a 4)
    texto_completo = "QUESTÃO 1 " + resto
    qs = re.split(r'(QUESTÃO\s+\d+)', texto_completo, flags=re.IGNORECASE)
    
    for i in range(1, len(qs), 2):
        try:
            titulo = qs[i]
            conteudo = qs[i+1]
            n = int(re.search(r'\d+', titulo).group())
            
            resp_limpa = limpar_resposta_discursiva(conteudo)
            
            if len(resp_limpa) > 10:
                respostas.append({"numero": n, "resposta": resp_limpa})
        except: pass
        
    return respostas

def extrair_perguntas_discursivas(texto):
    itens = []
    if "PEÇA" in texto.upper():
        pedacos = re.split(r'PEÇA PRÁTICO', texto, flags=re.IGNORECASE)
        if len(pedacos) > 1:
            peca = re.split(r'QUESTÃO\s+1', pedacos[1], flags=re.IGNORECASE)[0]
            itens.append({"numero": 0, "tipo": "PECA", "enunciado": peca.strip()})
    qs = re.split(r'(QUESTÃO\s+\d+)', texto, flags=re.IGNORECASE)
    for i in range(1, len(qs), 2):
        try:
            n = int(re.search(r'\d+', qs[i]).group())
            itens.append({"numero": n, "tipo": "DISCURSIVA", "enunciado": qs[i+1].strip()})
        except: pass
    return itens

def sincronizar_banco(conn):
    cursor = conn.cursor()
    print("\nSincronizando dados...")
    cursor.execute('''UPDATE questoes SET gabarito_letra = (SELECT g.letra_resposta FROM gabaritos_objetivas g JOIN arquivos a ON a.id = questoes.arquivo_id WHERE g.exame_id = a.exame_id AND g.cor_prova = a.cor_prova AND g.numero_questao = questoes.numero) WHERE tipo = 'OBJETIVA' AND gabarito_letra IS NULL;''')
    cursor.execute('''UPDATE questoes SET gabarito_texto = (SELECT g.texto_resposta FROM gabaritos_discursivas g JOIN arquivos a ON a.id = questoes.arquivo_id WHERE g.exame_id = a.exame_id AND g.materia = a.materia AND g.numero_questao = questoes.numero) WHERE (tipo = 'DISCURSIVA' OR tipo = 'PECA') AND gabarito_texto IS NULL;''')
    conn.commit()
    print(f" Sincronizacao Finalizada.")

def processar_tudo():
    if not os.path.exists(PASTA_LIMPOS): 
        return print("Pasta Provas_Limpas nao encontrada.")
    
    conn = criar_banco()
    cursor = conn.cursor()
    print(f"Iniciando Leitor de Texto...\n")
    
    arquivos = []
    for r, d, f in os.walk(PASTA_LIMPOS):
        for file in f:
            if file.endswith(".pdf"): arquivos.append(os.path.join(r, file))

    novos = 0
    for caminho in tqdm(arquivos):
        nome = os.path.basename(caminho)
        cursor.execute("SELECT id FROM arquivos WHERE nome_arquivo = ?", (nome,))
        if cursor.fetchone(): continue
        
        novos += 1
        try:
            partes = caminho.split(os.sep)
            nome_exame = next((p for p in partes if "EXAME" in p.upper()), "Desconhecido")
            cat = ""
            if "1_Fase_Provas" in partes: cat = "1_PROVA"
            elif "1_Fase_Gabaritos" in partes: cat = "1_GABARITO"
            elif "2_Fase_Provas" in partes: cat = "2_PROVA"
            elif "2_Fase_Padrao" in partes: cat = "2_PADRAO"
            
            cursor.execute("INSERT OR IGNORE INTO exames (nome_exame) VALUES (?)", (nome_exame,))
            cursor.execute("SELECT id FROM exames WHERE nome_exame = ?", (nome_exame,))
            exame_id = cursor.fetchone()[0]

            doc = fitz.open(caminho)
            texto = "".join([p.get_text() + "\n" for p in doc])
            doc.close()

            print(f"\nProcessando: {nome} [{cat}]")

            if cat == "1_PROVA":
                cor = identificar_cor_prova(texto)
                cursor.execute("INSERT INTO arquivos (exame_id, nome_arquivo, fase, cor_prova, tipo_arquivo) VALUES (?, ?, ?, ?, ?)", (exame_id, nome, "1_FASE", cor, "PROVA"))
                arq_id = cursor.lastrowid
                qs = extrair_questoes_objetivas(texto)
                for q in qs:
                    cursor.execute("INSERT INTO questoes (arquivo_id, numero, tipo, enunciado) VALUES (?, ?, ?, ?)", (arq_id, q['numero'], "OBJETIVA", q['enunciado']))
                    qid = cursor.lastrowid
                    for l, t in q['alternativas'].items():
                        cursor.execute("INSERT INTO alternativas (questao_id, letra, texto) VALUES (?, ?, ?)", (qid, l, t))

            elif cat == "1_GABARITO":
                mapa = extrair_gabarito_objetivo_blocado(texto)
                for cor, resps in mapa.items():
                    for n, l in resps:
                        cursor.execute("INSERT INTO gabaritos_objetivas (exame_id, cor_prova, numero_questao, letra_resposta) VALUES (?, ?, ?, ?)", (exame_id, cor, n, l))

            elif cat == "2_PROVA":
                mat = identificar_materia(texto, nome)
                cursor.execute("INSERT INTO arquivos (exame_id, nome_arquivo, fase, materia, tipo_arquivo) VALUES (?, ?, ?, ?, ?)", (exame_id, nome, "2_FASE", mat, "PROVA"))
                arq_id = cursor.lastrowid
                itens = extrair_perguntas_discursivas(texto)
                for i in itens:
                    cursor.execute("INSERT INTO questoes (arquivo_id, numero, tipo, enunciado) VALUES (?, ?, ?, ?)", (arq_id, i['numero'], i['tipo'], i['enunciado']))

            elif cat == "2_PADRAO":
                mat = identificar_materia(texto, nome)
                itens_resp = extrair_respostas_discursivas_complexas(texto)
                print(f" Extraidas {len(itens_resp)} respostas/pecas.")
                if len(itens_resp) == 0:
                    print(" ALERTA: Nenhuma resposta encontrada. Verifique o PDF.")
                
                for i in itens_resp:
                    cursor.execute("INSERT INTO gabaritos_discursivas (exame_id, materia, numero_questao, texto_resposta) VALUES (?, ?, ?, ?)", (exame_id, mat, i['numero'], i['resposta']))

            conn.commit()
        except Exception as e: print(f"Erro: {e}")

    sincronizar_banco(conn)
    conn.close()
    if novos > 0: print(f"\nFinalizado. {novos} novos arquivos.")
    else: print("\nTudo atualizado.")

if __name__ == "__main__":
    processar_tudo()