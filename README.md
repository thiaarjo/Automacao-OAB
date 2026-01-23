#  Automação de Extração de Provas da OAB

Este projeto é uma suíte completa de automação (RPA) desenvolvida em Python para **baixar, limpar, estruturar e exportar** questões do Exame de Ordem Unificado da OAB (Ordem dos Advogados do Brasil).

O robô transforma arquivos PDF desestruturados em um Banco de Dados Relacional (SQLite) e gera uma planilha Excel formatada pronta para importação em sistemas de gestão de provas (LMS).

## Funcionalidades

* **Download Automático:** Navega no site da FGV/OAB via Selenium, identifica as provas (Fase 1 e 2) e realiza o download organizado.
* **Limpeza de PDF (OCR/Crop):** Processa os arquivos PDF brutos, removendo cabeçalhos/rodapés de cadernos de prova e preservando integralmente os gabaritos comentados.
* **Parser Inteligente (ETL):** Lê o texto dos PDFs, identifica padrões (Regex) e extrai:
    * Enunciados e Alternativas (Objetivas).
    * Peças Prático-Profissionais e Questões Discursivas.
    * Gabaritos Oficiais e Padrões de Resposta (removendo tabelas de pontuação).
* **Banco de Dados SQL:** Armazena tudo em um banco SQLite (`OAB_Questoes.db`) com relacionamentos entre Exame, Matéria e Questões.
* **Exportação Excel:** Gera um arquivo `.xlsx` com duas abas ("Objetivas" e "Discursivas") formatado com metadados (Nível de dificuldade, Tipo, Justificativa) para importação em plataformas de ensino.

##  Tecnologias Utilizadas

* **Python 3.x**
* **Selenium WebDriver:** Automação Web e Download.
* **PyMuPDF (fitz):** Manipulação e leitura de arquivos PDF.
* **Pandas:** Manipulação de dados e exportação para Excel.
* **SQLite3:** Banco de dados local.
* **Regular Expressions (Regex):** Mineração de texto.

##  Instalação

1.  **Clone o repositório:**
    ```bash
    git clone [https://github.com/SEU_USUARIO/Automacao-OAB-Python.git](https://github.com/SEU_USUARIO/Automacao-OAB-Python.git)
    cd Automacao-OAB-Python
    ```

2.  **Crie um ambiente virtual (Recomendado):**
    ```bash
    python -m venv .venv
    # Windows:
    .venv\Scripts\activate
    # Linux/Mac:
    source .venv/bin/activate
    ```

3.  **Instale as dependências:**
    ```bash
    pip install -r requirements.txt
    ```
    *(Se não tiver o arquivo requirements.txt, instale manualmente: `pip install pandas openpyxl selenium webdriver-manager pymupdf requests tqdm`)*

##  Como Usar

O projeto possui um **"Maestro"** que gerencia todo o fluxo.

1.  Execute o arquivo principal:
    ```bash
    python fluxo_total.py
    ```

2.  **Fluxo de Execução:**
    * **Passo 1 (Interativo):** Uma janela do navegador abrirá. Escolha o Exame e o tipo de download (Tudo, Provas ou Gabaritos).
    * **Passo 2 (Automático):** O robô organiza os arquivos e aplica a limpeza nos PDFs.
    * **Passo 3 (Automático):** O robô lê o conteúdo e alimenta o banco de dados `OAB_Questoes.db`.
    * **Passo 4 (Automático):** O robô gera o arquivo `Importacao_Prova_OAB.xlsx`.

3.  **Resultado:**
    Ao final, verifique o arquivo **`Importacao_Prova_OAB.xlsx`** gerado na raiz do projeto.

##  Estrutura do Projeto

* `fluxo_total.py`: Script principal. Orquestra a chamada de todos os outros módulos.
* `robo_OAB.py`: Responsável pelo acesso ao site e download dos arquivos.
* `gestor_provas.py`: Gerencia as pastas e envia os arquivos para limpeza.
* `limpador_final.py`: Contém a lógica de manipulação de PDF (Corte de bordas vs. Cópia integral).
* `robo_leitor_sql.py`: O "cérebro" que lê os textos e salva no SQL.
* `exportador_excel.py`: Consulta o SQL e formata a planilha final.

##  Logs

O sistema roda a maior parte do tempo em segundo plano. Para acompanhar o progresso ou erros, consulte o arquivo **`log_execucao.txt`** que será criado automaticamente.

---
**Aviso:** Este projeto foi desenvolvido para fins educacionais e de automação de processos de estudo.