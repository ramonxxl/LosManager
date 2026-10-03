"""
=================================================================
TEMA VISUAL - LOS MANAGER
=================================================================
Paleta oficial baseada na identidade visual da Los Pastelles.
=================================================================
"""

from tkinter import ttk


# ================================================================
# CORES DA MARCA
# ================================================================

# Laranja principal
COR_LARANJA = "#F2891E"
COR_LARANJA_ESCURO = "#D4740A"
COR_LARANJA_CLARO = "#FDBF41"

# Fundo do menu (cor real da logo)
COR_MENU = "#FDF0E1"
COR_MENU_HOVER = "#F6E3D3"

# Texto
COR_TEXTO = "#3B1F12"
COR_TEXTO_CLARO = "#5A3524"

# Fundo geral
COR_FUNDO = "#FCF6F0"
COR_CARD = "#FFF8EF"
COR_BRANCO = "#FFFFFF"

# Destaques
COR_VERMELHO = "#DB4402"
COR_VERDE = "#2E8B57"


# ================================================================
# COMPATIBILIDADE
# (para não quebrar os arquivos antigos)
# ================================================================

COR_MARROM = COR_TEXTO
COR_MARROM_CLARO = COR_TEXTO_CLARO
COR_SALMAO = COR_MENU
COR_SALMAO_ESCURO = COR_MENU_HOVER
COR_CREME = COR_FUNDO
COR_CREME_CLARO = COR_CARD


# ================================================================
# ESTILO DAS TABELAS
# ================================================================

def aplicar_estilo_tabela():

    style = ttk.Style()
    style.theme_use("clam")

    style.configure(
        "Treeview",
        background=COR_BRANCO,
        fieldbackground=COR_BRANCO,
        foreground=COR_TEXTO,
        rowheight=32,
        borderwidth=0,
        font=("Arial", 11)
    )

    style.map(
        "Treeview",
        background=[("selected", COR_LARANJA)],
        foreground=[("selected", COR_BRANCO)]
    )

    style.configure(
        "Treeview.Heading",
        background=COR_LARANJA,
        foreground=COR_BRANCO,
        font=("Arial", 12, "bold"),
        borderwidth=0,
        relief="flat"
    )

    style.map(
        "Treeview.Heading",
        background=[("active", COR_LARANJA_ESCURO)]
    )


# Fica aqui (e não no main.py) para o teste poder importar sem carregar as telas,
# que guardam o banco no momento da importação.
def medidas_menu(altura_tela):
    """Tamanhos do menu lateral. Na tela da loja (1366x768) o menu normal
    pedia ~770px e o botão Configurações ficava cortado embaixo (sobram
    ~670px tirando barra de tarefas e título da janela); abaixo de 900px
    de altura usa logo menor e botões mais baixos."""

    if altura_tela < 900:
        return {"logo_largura": 120, "logo_pady": (12, 8), "botao_altura": 42, "botao_pady": 3}

    return {"logo_largura": 170, "logo_pady": (25, 20), "botao_altura": 52, "botao_pady": 6}
