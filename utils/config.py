"""
=================================================================
CONFIGURAÇÕES DO SISTEMA (persistentes, salvas no banco)
=================================================================
Guarda dados da loja e da impressora numa tabela simples de
chave/valor (`configuracoes`), pra não precisar editar código
toda vez que trocar de computador, impressora ou dados da loja.
=================================================================
"""

from database.conexao import banco
import sys
import os
import glob
import shutil
from datetime import datetime


PADROES = {
    "loja_nome": "PASTELARIA DO RAMON",
    "loja_endereco": "Rua Exemplo, 123 - Bairro",
    "loja_telefone": "(11) 99999-9999",
    "impressora_nome": "",
    "impressora_largura": "32",   # 32 = bobina 58mm | 48 = bobina 80mm
    "fidelidade_meta_pedidos": "10",
}

_TABELA_CRIADA = False


def _garantir_tabela():

    global _TABELA_CRIADA

    if _TABELA_CRIADA:
        return

    banco.executar("""
        CREATE TABLE IF NOT EXISTS configuracoes(
            chave TEXT PRIMARY KEY,
            valor TEXT
        )
    """)

    _TABELA_CRIADA = True


def obter(chave, padrao=None):

    _garantir_tabela()

    resultado = banco.buscar_um(
        "SELECT valor FROM configuracoes WHERE chave=?",
        (chave,)
    )

    if resultado is not None and resultado[0] not in (None, ""):
        return resultado[0]

    if padrao is not None:
        return padrao

    return PADROES.get(chave, "")


def definir(chave, valor):

    _garantir_tabela()

    banco.executar(
        """
        INSERT INTO configuracoes(chave, valor)
        VALUES(?, ?)
        ON CONFLICT(chave) DO UPDATE SET valor=excluded.valor
        """,
        (chave, valor)
    )


def obter_dados_loja():

    return {
        "nome": obter("loja_nome"),
        "endereco": obter("loja_endereco"),
        "telefone": obter("loja_telefone"),
    }


def obter_impressora_nome():

    return obter("impressora_nome")


def obter_largura_papel():

    try:
        return int(obter("impressora_largura"))
    except (TypeError, ValueError):
        return 32


def obter_meta_fidelidade():
    """Quantos pedidos concluídos o cliente precisa juntar pra ganhar 1
    recompensa no Programa de Fidelidade — o único lugar onde esse
    número mora, editável em Configurações (repositorios/fidelidade.py
    e as telas sempre leem daqui, nunca hardcoded)."""

    try:
        meta = int(obter("fidelidade_meta_pedidos"))
    except (TypeError, ValueError):
        return 10

    return meta if meta > 0 else 10


def bloquear_venda_sem_estoque_ingrediente():
    """Se True, o pedido não deixa adicionar um item quando algum
    ingrediente da receita não tem estoque suficiente. Se False
    (padrão), só avisa e deixa continuar — igual ao aviso de estoque
    de produto que já existe."""

    return obter("bloquear_venda_sem_estoque_ingrediente", "0") == "1"


# =================================================================
# CAMINHOS DE ARQUIVOS (funciona rodando .py OU já como .exe)
# =================================================================

def caminho_base():
    """Pasta raiz do projeto (ou pasta do .exe, se já estiver compilado).
    Usada para arquivos EXTERNOS ao pacote, como o banco de dados,
    que ficam soltos do lado do .exe de propósito."""

    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)

    # utils/ está uma pasta abaixo da raiz do projeto
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def caminho_recursos():
    """Pasta onde ficam os arquivos EMBUTIDOS no pacote (ícones, logos,
    etc). Rodando como .py, é a raiz do projeto (igual caminho_base).
    Já compilado como .exe, o PyInstaller extrai/copia esses arquivos
    para uma pasta interna (ex: '_internal'), que é diferente da pasta
    onde o .exe fica — o próprio PyInstaller expõe esse caminho em
    sys._MEIPASS em tempo de execução."""

    caminho_interno = getattr(sys, "_MEIPASS", None)

    if caminho_interno:
        return caminho_interno

    return caminho_base()


def caminho_asset(nome_arquivo):
    """Retorna o caminho completo de um arquivo dentro da pasta assets/."""

    return os.path.join(caminho_recursos(), "assets", nome_arquivo)


# =================================================================
# BACKUP DO BANCO DE DADOS
# =================================================================

MAXIMO_BACKUPS = 15


def fazer_backup_banco():
    """Copia o losmanager.db para uma pasta backups/ (do lado do banco),
    com data/hora no nome, e apaga os backups mais antigos, mantendo só
    os últimos MAXIMO_BACKUPS. Deixa qualquer erro (ex: sem permissão de
    disco) subir para quem chamou decidir como avisar o usuário."""

    caminho_banco = os.path.join(caminho_base(), "losmanager.db")

    if not os.path.isfile(caminho_banco):
        return

    pasta_backups = os.path.join(caminho_base(), "backups")
    os.makedirs(pasta_backups, exist_ok=True)

    nome_backup = "losmanager_" + datetime.now().strftime("%Y%m%d_%H%M%S") + ".db"
    caminho_backup = os.path.join(pasta_backups, nome_backup)

    shutil.copy2(caminho_banco, caminho_backup)

    _limpar_backups_antigos(pasta_backups)


def _limpar_backups_antigos(pasta_backups):

    backups = sorted(glob.glob(os.path.join(pasta_backups, "losmanager_*.db")))

    excedentes = len(backups) - MAXIMO_BACKUPS

    for caminho_antigo in backups[:max(excedentes, 0)]:
        os.remove(caminho_antigo)
