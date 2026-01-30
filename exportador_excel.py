import sqlite3
import pandas as pd
import os
import re
from datetime import datetime

# --- CONFIGURAÇÕES ---
NOME_BANCO = "OAB_Questoes.db"
NOME_ARQUIVO_SAIDA = "Exportacao_OAB_Template_Novo.xlsx"

# Colunas EXATAS do novo template (Não alterar)
COLUNAS_TEMPLATE = [
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

def conectar_banco():
    return sqlite3.connect(NOME_BANCO)

def limpar_texto(texto):
    """Remove quebras de linha extras e espaços desnecessários."""
    if not isinstance(texto, str): return ""
    texto = texto.replace('\n', ' ').replace('\r', '')
    return re.sub(r'\s+', ' ', texto).strip()

def identificar_disciplina_oab(numero):
    """
    Retorna a disciplina com base no número da questão (Padrão OAB 1ª Fase).
    """
    try:
        n = int(numero)
    except:
        return "A CLASSIFICAR"

    # Mapeamento oficial (Blocos)
    if 1 <= n <= 8: return "Ética Profissional"
    if 9 <= n <= 10: return "Filosofia do Direito"
    if 11 <= n <= 16: return "Direito Constitucional"
    if 17 <= n <= 18: return "Direitos Humanos"
    if 19 <= n <= 20: return "Direito Eleitoral"
    if 21 <= n <= 22: return "Direito Internacional"
    if 23 <= n <= 24: return "Direito Financeiro"
    if 25 <= n <= 29: return "Direito Tributário"
    if 30 <= n <= 34: return "Direito Administrativo"
    if 35 <= n <= 36: return "Direito Ambiental"
    if 37 <= n <= 42: return "Direito Civil"
    if 43 <= n <= 44: return "ECA"
    if 45 <= n <= 46: return "Direito do Consumidor"
    if 47 <= n <= 50: return "Direito Empresarial"
    if 51 <= n <= 56: return "Direito Processual Civil"
    if 57 <= n <= 62: return "Direito Penal"
    if 63 <= n <= 68: return "Direito Processual Penal"
    if 69 <= n <= 70: return "Direito Previdenciário"
    if 71 <= n <= 75: return "Direito do Trabalho"
    if 76 <= n <= 80: return "Direito Processual do Trabalho"
    
    return "OUTROS"

def exportar_objetivas(conn):
    print("📋 Processando Questões Objetivas...")
    
    query = """
    SELECT 
        e.nome_exame,
        q.numero,
        q.enunciado,
        q.alternativa_a,
        q.alternativa_b,
        q.alternativa_c,
        q.alternativa_d,
        q.gabarito_letra
    FROM questoes q
    JOIN arquivos arq ON q.arquivo_id = arq.id
    JOIN exames e ON arq.exame_id = e.id
    WHERE q.tipo = 'OBJETIVA'
    ORDER BY e.id, q.numero
    """
    
    df_raw = pd.read_sql_query(query, conn)
    
    if df_raw.empty:
        print("⚠️ Nenhuma questão objetiva encontrada.")
        return pd.DataFrame(columns=COLUNAS_TEMPLATE)

    linhas_excel = []
    ano_atual = datetime.now().year

    for index, row in df_raw.iterrows():
        # Aplica a função de mapeamento aqui
        disciplina = identificar_disciplina_oab(row['numero'])
        
        linhas_excel.append({
            "Enunciado da Questão": limpar_texto(row['enunciado']),
            "Código da Disciplina": disciplina.upper(), # Coloca em MAIÚSCULO para padronizar
            "Dificuldade": "Médio",
            "Tipo de Uso": "Simulado",
            "Alternativa A": limpar_texto(row['alternativa_a']),
            "Alternativa B": limpar_texto(row['alternativa_b']),
            "Alternativa C": limpar_texto(row['alternativa_c']),
            "Alternativa D": limpar_texto(row['alternativa_d']),
            "Resposta Correta": str(row['gabarito_letra']).strip().upper() if row['gabarito_letra'] else "",
            "Explicação (opcional)": "", 
            "Fonte (opcional)": row['nome_exame'],
            "Ano do Exame (opcional)": ano_atual
        })

    return pd.DataFrame(linhas_excel)

def exportar_discursivas(conn):
    print("⏳ Processando Questões Discursivas...")
    
    query = """
    SELECT 
        e.nome_exame,
        arq.materia,
        q.numero,
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
        return pd.DataFrame(columns=COLUNAS_TEMPLATE)

    linhas_excel = []

    for index, row in df_raw.iterrows():
        # Na 2ª Fase, a matéria vem do nome do arquivo (já salvo na coluna materia)
        materia = row['materia'] if row['materia'] else "PRÁTICA JURÍDICA"
        gabarito = limpar_texto(row['gabarito_texto']) if row['gabarito_texto'] else "Gabarito indisponível."

        linhas_excel.append({
            "Enunciado da Questão": limpar_texto(row['enunciado']),
            "Código da Disciplina": materia.upper(),
            "Dificuldade": "Médio",
            "Tipo de Uso": "Prática",
            "Alternativa A": "-",
            "Alternativa B": "-",
            "Alternativa C": "-",
            "Alternativa D": "-",
            "Resposta Correta": "-",
            "Explicação (opcional)": f"PADRÃO DE RESPOSTA: {gabarito}",
            "Fonte (opcional)": f"{row['nome_exame']} - 2ª Fase",
            "Ano do Exame (opcional)": datetime.now().year
        })

    return pd.DataFrame(linhas_excel)

def main():
    print(f"🚀 INICIANDO EXPORTAÇÃO PARA FORMATO: {NOME_ARQUIVO_SAIDA}")
    
    if not os.path.exists(NOME_BANCO):
        print(f"❌ Banco de dados {NOME_BANCO} não encontrado.")
        return

    conn = conectar_banco()
    
    # 1. Gera DataFrames
    df_objetivas = exportar_objetivas(conn)
    df_discursivas = exportar_discursivas(conn)
    
    conn.close()

    print(f"\n💾 Gravando arquivo Excel...")
    
    try:
        with pd.ExcelWriter(NOME_ARQUIVO_SAIDA, engine='openpyxl') as writer:
            # Consolida tudo numa aba só
            df_total = pd.concat([df_objetivas, df_discursivas])
            
            # Garante a ordem das colunas e preenche vazios
            df_total = df_total[COLUNAS_TEMPLATE].fillna("")
            
            df_total.to_excel(writer, sheet_name='Questoes', index=False)
            
            print(f"   -> Total exportado: {len(df_total)} questões.")
        
        print(f"\n✅ SUCESSO! Exportação concluída.")
        print(f"📂 Arquivo: {os.path.abspath(NOME_ARQUIVO_SAIDA)}")
        
    except Exception as e:
        print(f"❌ Erro ao salvar Excel: {e}")
        print("⚠️ Dica: Feche o arquivo Excel se ele estiver aberto!")

if __name__ == "__main__":
    main()