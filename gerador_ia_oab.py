import sqlite3
import pandas as pd
import requests
import json
import os
import time
import re
from datetime import datetime

# --- CONFIGURAÇÕES ---
ARQUIVO_BANCO = "OAB_Questoes.db"
URL_WEBHOOK_N8N = "http://localhost:5678/webhook-test/gerar-oab" 

# LISTA PADRÃO DA OAB
MATERIAS_OAB_OBJETIVA = [
    "ÉTICA PROFISSIONAL", "FILOSOFIA DO DIREITO", "DIREITO CONSTITUCIONAL",
    "DIREITOS HUMANOS", "DIREITO ADMINISTRATIVO", "DIREITO AMBIENTAL",
    "DIREITO CIVIL", "ECA (CRIANÇA E ADOLESCENTE)", "DIREITO DO CONSUMIDOR",
    "DIREITO EMPRESARIAL", "PROCESSO CIVIL", "DIREITO PENAL",
    "PROCESSO PENAL", "DIREITO DO TRABALHO", "PROCESSO DO TRABALHO",
    "DIREITO TRIBUTÁRIO", "DIREITO INTERNACIONAL"
]

def conectar_banco():
    return sqlite3.connect(ARQUIVO_BANCO)

def limpar_texto(texto):
    if not isinstance(texto, str): return ""
    texto = texto.replace('\n', ' ').replace('\r', '')
    texto = re.sub(r'\s+', ' ', texto)
    return texto.strip()

def menu_inicial():
    print("\n========================================")
    print("   🤖 GERADOR OAB - STRICT TEMPLATE     ")
    print("========================================")
    print("Qual fase você quer usar como base?")
    print("[ 1 ] 1ª FASE - OBJETIVA (Prova Unificada)")
    print("[ 2 ] 2ª FASE - DISCURSIVA (Por Matéria)")
    
    while True:
        opt = input(">>> Escolha (1 ou 2): ").strip()
        if opt in ['1', '2']:
            return "1_FASE" if opt == '1' else "2_FASE"
        print("⚠️ Opção inválida.")

def listar_exames_objetivos(conn):
    cursor = conn.cursor()
    query = """
        SELECT e.id, e.nome_exame, GROUP_CONCAT(a.nome_arquivo, ', ') as arquivos
        FROM exames e
        JOIN arquivos a ON a.exame_id = e.id
        WHERE a.fase = '1_FASE'
        GROUP BY e.id, e.nome_exame
        ORDER BY e.id DESC
    """
    cursor.execute(query)
    exames = cursor.fetchall()

    if not exames:
        print("❌ Nenhum exame encontrado.")
        return None, None

    print("\n📅 EXAMES DISPONÍVEIS:")
    print("-" * 60)
    for i, (eid, nome, arqs) in enumerate(exames):
        arqs_fmt = arqs.replace(".pdf", "") if arqs else ""
        if len(arqs_fmt) > 50: arqs_fmt = arqs_fmt[:47] + "..."
        print(f"[ {i+1:02d} ] {nome}")
    print("-" * 60)

    while True:
        try:
            escolha = int(input(">>> Digite o NÚMERO do Exame: "))
            if 1 <= escolha <= len(exames):
                return exames[escolha - 1][0], exames[escolha - 1][1]
            print("⚠️ Inválido.")
        except ValueError: pass

def escolher_materia_objetiva_padrao():
    print("\n📚 DISCIPLINA ALVO:")
    print("="*40)
    for i, mat in enumerate(MATERIAS_OAB_OBJETIVA):
        print(f"[ {i+1:02d} ] {mat}")
    print("="*40)
    while True:
        try:
            escolha = int(input(">>> Digite o NÚMERO da disciplina: "))
            if 1 <= escolha <= len(MATERIAS_OAB_OBJETIVA):
                return MATERIAS_OAB_OBJETIVA[escolha - 1]
        except ValueError: pass

def listar_materias_discursivas(conn):
    cursor = conn.cursor()
    query = "SELECT DISTINCT materia FROM arquivos WHERE fase = '2_FASE' AND materia IS NOT NULL ORDER BY materia ASC"
    cursor.execute(query)
    materias = [row[0] for row in cursor.fetchall()]
    print("\n📚 DISCIPLINA ALVO (2ª FASE):")
    print("="*40)
    for i, mat in enumerate(materias):
        print(f"[ {i+1:02d} ] {mat}")
    print("="*40)
    while True:
        try:
            escolha = int(input(">>> Digite o NÚMERO da matéria: "))
            if 1 <= escolha <= len(materias): return materias[escolha - 1]
        except ValueError: pass

def buscar_exemplos(tipo_fase, id_ou_materia, filtro_tema=None, qtd=3):
    conn = conectar_banco()
    cursor = conn.cursor()
    exemplos_txt = ""
    try:
        if tipo_fase == "1_FASE":
            exame_id = id_ou_materia
            termo = f"%{filtro_tema.split(' ')[-1]}%"
            print(f"🔍 Filtrando por '{termo}' no Exame ID {exame_id}...")
            
            query = """
                SELECT q.enunciado, COALESCE(q.gabarito_letra, go.letra_resposta, 'N/A')
                FROM questoes q
                JOIN arquivos a ON q.arquivo_id = a.id
                LEFT JOIN gabaritos_objetivas go ON (go.exame_id = a.exame_id AND go.numero_questao = q.numero AND go.cor_prova = a.cor_prova)
                WHERE a.exame_id = ? AND a.fase = '1_FASE' AND q.enunciado LIKE ?
                ORDER BY RANDOM() LIMIT ?
            """
            cursor.execute(query, (exame_id, termo, qtd))
            rows = cursor.fetchall()
            if not rows:
                 cursor.execute(query.replace("AND q.enunciado LIKE ?", ""), (exame_id, qtd))
                 rows = cursor.fetchall()

            for i, (enunc, gab) in enumerate(rows):
                exemplos_txt += f"--- EXEMPLO {i+1} ---\nENUNCIADO: {limpar_texto(enunc)}\nGABARITO: {gab}\n\n"
        else:
            materia = id_ou_materia
            query = """
                SELECT q.enunciado, gd.texto_resposta
                FROM questoes q
                JOIN arquivos a ON q.arquivo_id = a.id
                LEFT JOIN gabaritos_discursivas gd ON (gd.exame_id = a.exame_id AND gd.numero_questao = q.numero AND gd.materia = a.materia)
                WHERE a.materia = ? AND a.fase = '2_FASE'
                ORDER BY RANDOM() LIMIT ?
            """
            cursor.execute(query, (materia, qtd))
            rows = cursor.fetchall()
            for i, (enunc, resp) in enumerate(rows):
                resp = resp if resp else "Sem padrão."
                exemplos_txt += f"--- EXEMPLO {i+1} ---\nPERGUNTA: {limpar_texto(enunc)}\nRESPOSTA: {limpar_texto(resp)[:500]}...\n\n"
    except Exception as e: print(f"❌ Erro SQL: {e}")
    finally: conn.close()
    return exemplos_txt

def chamar_agente_ia(materia, tipo_fase, exemplos, qtd):
    payload = {
        "disciplina": materia,
        "tipo_prova": "OBJETIVA" if tipo_fase == "1_FASE" else "DISCURSIVA",
        "contexto_exemplos": exemplos,
        "quantidade_gerar": qtd
    }
    print(f"📡 Enviando pedido de {qtd} questões para n8n...")
    try:
        response = requests.post(URL_WEBHOOK_N8N, json=payload, timeout=300)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"❌ Erro n8n: {e}")
        return []

def salvar_excel_fiel(dados_json, materia, tipo_fase, nome_exame_base):
    if not dados_json: 
        print("❌ Nenhum dado recebido.")
        return

    timestamp = int(time.time())
    nome_arquivo = f"Importacao_Strict_{materia.replace(' ', '_')}_{timestamp}.xlsx"
    
    # --- COLUNAS OBRIGATÓRIAS DO TEMPLATE (NÃO MUDAR) ---
    colunas_strict = [
        "Enunciado da Questão",
        "Código da Disciplina",
        "Dificuldade",
        "Tipo de Uso",
        "Alternativa A",
        "Alternativa B",
        "Alternativa C",
        "Alternativa D",
        "Resposta Correta",
        "Explicação (opcional)",
        "Fonte (opcional)",
        "Ano do Exame (opcional)"
    ]

    linhas = []
    ano_atual = datetime.now().year

    print(f"⚙️ Gerando Excel seguindo o template fielmente...")

    for q in dados_json:
        # Cria um dicionário com chaves vazias para garantir a ordem
        row = {col: "" for col in colunas_strict}
        
        row["Enunciado da Questão"] = q.get('enunciado', '')
        # Tenta pegar apenas o primeiro nome da disciplina para ficar curto (ex: ETICA)
        # Se preferir nome completo, use apenas 'materia'
        row["Código da Disciplina"] = materia 
        row["Ano do Exame (opcional)"] = ano_atual
        row["Fonte (opcional)"] = f"IA - Base: {nome_exame_base}"

        if tipo_fase == "1_FASE": # OBJETIVAS
            row["Dificuldade"] = "Médio"
            row["Tipo de Uso"] = "Simulado"
            row["Alternativa A"] = q.get('alternativa_A', '')
            row["Alternativa B"] = q.get('alternativa_B', '')
            row["Alternativa C"] = q.get('alternativa_C', '')
            row["Alternativa D"] = q.get('alternativa_D', '')
            row["Resposta Correta"] = q.get('correta', '').strip().upper()
            row["Explicação (opcional)"] = q.get('justificativa', '')

        else: # DISCURSIVAS
            row["Dificuldade"] = "Difícil"
            row["Tipo de Uso"] = "Prática"
            # Preenche com hífen para satisfazer o template que exige colunas
            row["Alternativa A"] = "-"
            row["Alternativa B"] = "-"
            row["Alternativa C"] = "-"
            row["Alternativa D"] = "-"
            row["Resposta Correta"] = "-" 
            # Coloca a resposta discursiva na explicação
            row["Explicação (opcional)"] = f"PADRÃO DE RESPOSTA: {q.get('padrao_resposta', '')}"

        linhas.append(row)

    try:
        # Garante a ordem exata das colunas
        df = pd.DataFrame(linhas, columns=colunas_strict)
        df.to_excel(nome_arquivo, index=False)
        print(f"\n✅ SUCESSO! Arquivo gerado: {nome_arquivo}")
        print("   Este arquivo segue estritamente o cabeçalho do template.")
    except Exception as e:
        print(f"❌ Erro ao salvar Excel: {e}")

def main():
    if not os.path.exists(ARQUIVO_BANCO): return print("❌ Banco não encontrado.")
    conn = conectar_banco()
    tipo_fase = menu_inicial()
    
    nome_exame_base = "Banco Geral"

    if tipo_fase == "1_FASE":
        exame_id, nome_exame_base = listar_exames_objetivos(conn)
        materia_alvo = escolher_materia_objetiva_padrao()
        exemplos = buscar_exemplos(tipo_fase, exame_id, filtro_tema=materia_alvo)
    else:
        materia_alvo = listar_materias_discursivas(conn)
        exemplos = buscar_exemplos(tipo_fase, materia_alvo)

    conn.close()
    
    try: qtd = int(input("\n🔢 Quantas questões gerar? (Padrão: 5): ") or 5)
    except: qtd = 5
    
    novas = chamar_agente_ia(materia_alvo, tipo_fase, exemplos, qtd)
    salvar_excel_fiel(novas, materia_alvo, tipo_fase, nome_exame_base)

if __name__ == "__main__":
    main()