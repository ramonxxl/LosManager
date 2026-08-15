"""
=================================================================
CADASTRO DE PRODUTOS — regras de validação e acesso ao banco
=================================================================
Extraído de `screens/produtos.py` pra poder ser testado sem
depender do CustomTkinter/Tkinter (nada aqui importa GUI). A tela
continua dona dos widgets e chama estas funções; elas não sabem que
uma tela existe.

Todas as funções recebem `banco` opcionalmente — em produção usam o
`banco` singleton de `database.conexao`; em teste, recebem um
`Banco(":memory:")` isolado.

O padrão é resolvido como `conexao.banco` (atributo do módulo, lido
na hora da chamada) e não `from database.conexao import banco` (que
travaria a referência no banco que existia no instante em que ESTE
módulo foi importado pela primeira vez). Isso importa pra teste de
GUI: uma tela é montada e usada sem nunca passar `banco=` explícito,
então só o atributo do módulo sendo trocado (`conexao.banco = ...`)
antes de montar a tela consegue isolar a escrita — mesmo que este
módulo já tenha sido importado antes em outro teste.
=================================================================
"""

from database import conexao
from utils import busca


class ProdutoInvalido(Exception):
    """Erro de validação dos dados digitados no formulário — a
    mensagem já vem pronta pra mostrar ao usuário."""


def validar_nome(nome):

    nome = (nome or "").strip()

    if not nome:
        raise ProdutoInvalido("Informe o nome do produto.")

    return nome


def validar_preco(texto):

    texto = (texto or "").strip().replace(",", ".")

    try:
        return float(texto)
    except ValueError:
        raise ProdutoInvalido("Preço inválido. Use números, ex: 16,90")


def validar_estoque(texto):

    texto = (texto or "").strip()

    if not texto:
        return 0

    try:
        return int(texto)
    except ValueError:
        raise ProdutoInvalido("Estoque inválido. Use apenas números inteiros.")


# ==========================================================

def listar(termo="", campo="Nome", banco=None):
    """Retorna [(id, nome, categoria, preco, estoque, ativo), ...],
    já filtrado. O filtro roda em Python (não no SQL) — ver
    utils/busca.py pro motivo (acento/maiúscula)."""

    banco = banco or conexao.banco

    produtos = banco.buscar(
        "SELECT id, nome, categoria, preco, estoque, ativo FROM produtos ORDER BY id DESC"
    )

    termo = (termo or "").strip()

    if not termo:
        return produtos

    if campo == "ID":

        try:
            id_busca = int(termo)
        except ValueError:
            # Ainda digitando um número inválido: não mostra nada
            # em vez de dar erro.
            return []

        return [p for p in produtos if p[0] == id_busca]

    if campo == "Preço":
        return [p for p in produtos if termo in str(p[3])]

    return [p for p in produtos if busca.contem(termo, p[1])]  # Nome


def obter(produto_id, banco=None):
    """Retorna (nome, categoria, preco, estoque) ou None se não existir."""

    banco = banco or conexao.banco

    return banco.buscar_um(
        "SELECT nome, categoria, preco, estoque FROM produtos WHERE id=?",
        (produto_id,)
    )


def criar(nome, categoria, preco_texto, estoque_texto, banco=None):
    """Valida e insere. Retorna o id do produto criado. Levanta
    ProdutoInvalido se algum campo estiver errado."""

    banco = banco or conexao.banco

    nome = validar_nome(nome)
    preco = validar_preco(preco_texto)
    estoque = validar_estoque(estoque_texto)
    categoria = (categoria or "").strip()

    banco.executar(
        """
        INSERT INTO produtos(nome,categoria,preco,estoque)
        VALUES(?,?,?,?)
        """,
        (nome, categoria, preco, estoque)
    )

    return banco.ultimo_id()


def atualizar(produto_id, nome, categoria, preco_texto, estoque_texto, banco=None):
    """Valida e atualiza um produto existente. Levanta ProdutoInvalido
    se algum campo estiver errado."""

    banco = banco or conexao.banco

    nome = validar_nome(nome)
    preco = validar_preco(preco_texto)
    estoque = validar_estoque(estoque_texto)
    categoria = (categoria or "").strip()

    banco.executar(
        """
        UPDATE produtos
        SET nome=?, categoria=?, preco=?, estoque=?
        WHERE id=?
        """,
        (nome, categoria, preco, estoque, produto_id)
    )


def excluir(produto_id, banco=None):
    """Exclui de vez se o produto nunca apareceu num pedido; senão só
    desativa, pra manter o histórico de vendas intacto. Retorna
    'excluido' ou 'desativado'."""

    banco = banco or conexao.banco

    ja_vendido = banco.buscar_um(
        "SELECT COUNT(*) FROM itens_pedido WHERE produto_id=?",
        (produto_id,)
    )

    if ja_vendido and ja_vendido[0] > 0:
        banco.executar("UPDATE produtos SET ativo=0 WHERE id=?", (produto_id,))
        return "desativado"

    banco.executar("DELETE FROM produtos WHERE id=?", (produto_id,))
    return "excluido"


def alternar_ativo(produto_id, banco=None):
    """Inverte o ativo/inativo do produto e retorna o novo status
    (1 ou 0)."""

    banco = banco or conexao.banco

    atual = banco.buscar_um("SELECT ativo FROM produtos WHERE id=?", (produto_id,))
    novo_status = 0 if atual and atual[0] else 1

    banco.executar(
        "UPDATE produtos SET ativo=? WHERE id=?",
        (novo_status, produto_id)
    )

    return novo_status
