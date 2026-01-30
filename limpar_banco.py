import os

NOME_BANCO = "OAB_Questoes.db"

# Verifica se o arquivo existe
if os.path.exists(NOME_BANCO):
    try:
        # Em vez de tentar limpar tabela por tabela, apagamos o arquivo todo
        os.remove(NOME_BANCO)
        print(f"✅ Arquivo '{NOME_BANCO}' deletado com sucesso!")
        print("🚀 O ambiente está limpo. O robô vai criar um banco novo do zero.")
    except PermissionError:
        print(f"❌ ERRO: O arquivo '{NOME_BANCO}' está aberto em outro programa.")
        print("⚠️ Feche qualquer visualizador de SQLite ou Excel e tente novamente.")
    except Exception as e:
        print(f"❌ Erro ao deletar: {e}")
else:
    print("Banco de dados não existe ainda (limpo). Pode rodar o robô!")