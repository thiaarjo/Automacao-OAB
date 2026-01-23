import sqlite3
import pandas as pd
import os

# --- CONFIGURAÇÕES ---
NOME_BANCO = "OAB_Questoes.db"
NOME_ARQUIVO_SAIDA = "Importacao_Prova_OAB.xlsx"

def conectar_banco():
    return sqlite3.connect(NOME_BANCO)

def gerar_codigo_questao(nome_exame, numero, tipo, materia="GERAL"):
    """
    Gera um código único para a questão (Ex: XIV_OAB_OBJ_Q1 ou XIV_OAB_PENAL_Q2).
    Remove espaços e caracteres especiais para ficar limpo.
    """
    exame_limpo = nome_exame.replace(" ", "_").replace("ª", "").replace("º", "").upper()
    exame_curto = exame_limpo.split("_")[0] # Pega só o prefixo (Ex: XIV)
    
    if tipo == "OBJ":
        return f"{exame_curto}_OBJ_Q{numero}"
    else:
        mat_limpa = materia.replace(" ", "").upper()[:4] # Pega 4 letras da materia
        return f"{exame_curto}_{mat_limpa}_Q{numero}"

def exportar_objetivas(conn):
    print(" Processando Questões Objetivas...")
    
    query = """
    SELECT 
        e.nome_exame,
        q.numero,
        q.enunciado,
        q.gabarito_letra,
        alt.letra,
        alt.texto as texto_alternativa
    FROM questoes q
    JOIN arquivos arq ON q.arquivo_id = arq.id
    JOIN exames e ON arq.exame_id = e.id
    JOIN alternativas alt ON alt.questao_id = q.id
    WHERE q.tipo = 'OBJETIVA'
    ORDER BY e.id, q.numero, alt.letra
    """
    
    # Lê do banco
    df_raw = pd.read_sql_query(query, conn)
    
    if df_raw.empty:
        print(" Nenhuma questão objetiva encontrada.")
        return pd.DataFrame()

    # Lista para montar as linhas do Excel
    linhas_excel = []

    for index, row in df_raw.iterrows():
        # Lógica de Código Único
        cod_questao = gerar_codigo_questao(row['nome_exame'], row['numero'], "OBJ")
        
        # Verifica se é a correta
        # (Trata caso de gabarito nulo ou minúsculo)
        gabarito_oficial = str(row['gabarito_letra']).upper().strip()
        letra_atual = str(row['letra']).upper().strip()
        eh_correta = "S" if gabarito_oficial == letra_atual else "N"

        linhas_excel.append({
            "COD_ULTIMO_NIVEL_CONTEUDO": "OAB_1FASE",  # Código fixo de agrupamento
            "NOME_ULTIMO_NIVEL_CONTEUDO": "OAB - 1ª Fase (Objetiva)",
            "COD_QUESTAO": cod_questao,
            "TIPO_QUESTAO": "o",
            "NIVEL_QUESTAO": "Médio",
            "JUSTIFICATIVA": "", # Objetivas geralmente não têm justificativa no seu banco atual (fase 1)
            "ENUNCIADO": row['enunciado'],
            "DESC_ALTERNATIVA": row['texto_alternativa'],
            "ALTER_CORRETA": eh_correta,
            "CAMPOS_CUSTOMIZADOS": ""
        })

    return pd.DataFrame(linhas_excel)

def exportar_discursivas(conn):
    print("⏳ Processando Questões Discursivas...")
    
    query = """
    SELECT 
        e.nome_exame,
        arq.materia,
        q.numero,
        q.tipo,
        q.enunciado,
        q.gabarito_texto
    FROM questoes q
    JOIN arquivos arq ON q.arquivo_id = arq.id
    JOIN exames e ON arq.exame_id = e.id
    WHERE q.tipo IN ('DISCURSIVA', 'PECA')
    ORDER BY e.id, arq.materia, q.numero
    """
    
    df_raw = pd.read_sql_query(query, conn)
    
    if df_raw.empty:
        print(" Nenhuma questão discursiva encontrada.")
        return pd.DataFrame()

    linhas_excel = []

    for index, row in df_raw.iterrows():
        materia = row['materia'] if row['materia'] else "GERAL"
        cod_questao = gerar_codigo_questao(row['nome_exame'], row['numero'], "DISC", materia)
        
        # O Gabarito Comentado entra no campo JUSTIFICATIVA (para o professor ver)
        justificativa = row['gabarito_texto'] if row['gabarito_texto'] else "Gabarito não disponível."

        linhas_excel.append({
            "COD_ULTIMO_NIVEL_CONTEUDO": f"OAB_2FASE_{materia.replace(' ', '_')}",
            "NOME_ULTIMO_NIVEL_CONTEUDO": f"OAB 2ª Fase - {materia}",
            "COD_QUESTAO": cod_questao,
            "TIPO_QUESTAO": "t", # t = teórica/discursiva
            "NIVEL_QUESTAO": "Difícil",
            "JUSTIFICATIVA": justificativa,
            "ENUNCIADO": row['enunciado'],
            "TIPO_RESPOSTA": 1, # 1 = Linhas
            "TAMANHO_RESPOSTA": 30, # Padrão de 30 linhas
            "IMPRIMIR_PAUTA": "S",
            "CAMPOS_CUSTOMIZADOS": ""
        })

    return pd.DataFrame(linhas_excel)

def main():
    if not os.path.exists(NOME_BANCO):
        print(f" Banco de dados {NOME_BANCO} não encontrado.")
        return

    conn = conectar_banco()
    
    # 1. Gera DataFrames
    df_objetivas = exportar_objetivas(conn)
    df_discursivas = exportar_discursivas(conn)
    
    conn.close()

    # 2. Grava no Excel
    print(f"\n Gravando arquivo Excel: {NOME_ARQUIVO_SAIDA}...")
    
    try:
        with pd.ExcelWriter(NOME_ARQUIVO_SAIDA, engine='openpyxl') as writer:
            # Aba 1: Objetivas
            if not df_objetivas.empty:
                df_objetivas.to_excel(writer, sheet_name='questoes_objetivas', index=False)
                print(f"   Aba 'questoes_objetivas' criada com {len(df_objetivas)} linhas.")
            
            # Aba 2: Discursivas
            if not df_discursivas.empty:
                df_discursivas.to_excel(writer, sheet_name='questoes_discursivas', index=False)
                print(f"   Aba 'questoes_discursivas' criada com {len(df_discursivas)} questões.")
        
        print(f"\n SUCESSO! Arquivo pronto para importação.")
        print(f"Local: {os.path.abspath(NOME_ARQUIVO_SAIDA)}")
        
    except Exception as e:
        print(f"Erro ao salvar Excel: {e}")
        print("Dica: Verifique se o arquivo Excel já não está aberto.")

if __name__ == "__main__":
    main()