import os
import subprocess
import time

def rodar_script(nome_script, argumentos=[]):
    """Roda um script Python e espera ele terminar."""
    print(f"\n{'='*70}")
    print(f"INICIANDO: {nome_script}")
    print(f"{'='*70}\n")
    
    comando = ["python", nome_script] + argumentos
    
    # Chama o processo e espera terminar
    # shell=True ajuda no Windows a achar o python corretamente
    codigo = subprocess.call(comando, shell=True)
    
    if codigo != 0:
        print(f"\n ERRO CRÍTICO ao rodar {nome_script}. O fluxo parou.")
        return False
    return True

def main():
    print("""
    ################################################
    #       AUTO-FLUXO OAB: O GRANDE ROBÔ      #
    ################################################
    """)

    # 1. BAIXAR (robo_OAB.py)
    if not rodar_script("robo_OAB.py"): return

    # 2. LIMPAR E ORGANIZAR (gestor_provas.py)
    # Aqui usamos o truque do "--auto" para ele não perguntar nada e limpar tudo.
    if not rodar_script("gestor_provas.py", ["--auto"]): return

    # 3. PERGUNTA DE SEGURANÇA DO BANCO
    if os.path.exists("OAB_Questoes.db"):
        print("\n⚠️  ATENÇÃO: Banco de Dados encontrado.")
        resp = input(">>> Deseja APAGAR o banco antigo e recriar do zero? (S/N): ").upper()
        if resp == 'S':
            try:
                os.remove("OAB_Questoes.db")
                print("Banco antigo deletado com sucesso.")
            except:
                print("Não foi possível deletar (feche o DB Browser).")
                return

    # 4. LER E EXPORTAR PARA SQL (robo_leitor_sql.py)
    if not rodar_script("robo_leitor_sql.py"): return

    # 5. EXPORTAR PARA EXCEL (exportador_excel.py) - NOVO!
    if not rodar_script("exportador_excel.py"): return

    print("\n" + "="*70)
    print("FLUXO COMPLETO FINALIZADO COM SUCESSO!")
    print("="*70)
    print("Seu banco de dados e o arquivo Excel estão prontos.")

if __name__ == "__main__":
    main()