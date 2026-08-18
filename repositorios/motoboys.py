"""
=================================================================
CADASTRO DE MOTOBOYS — regras de validação e acesso ao banco
=================================================================
Segue o mesmo padrão de `repositorios/produtos.py` (ver aquele
arquivo para a explicação completa do porquê de `banco=None`
resolver via `conexao.banco` em vez de um import direto).
=================================================================
"""

from database import conexao


class MotoboyInvalido(Exception):
    """Erro de validação dos dados digitados no formulário — a
    mensagem já vem pronta pra mostrar ao usuário."""


def validar_nome(nome):

    nome = (nome or "").strip()

    if not nome:
        raise MotoboyInvalido("Informe o nome do motoboy.")

    return nome


# ==========================================================

def listar(banco=None):
    """Retorna [(id, nome, ativo), ...] todos os motoboys cadastrados."""

    banco = banco or conexao.banco

    return banco.buscar(
        "SELECT id, nome, ativo FROM motoboys ORDER BY nome"
    )


def listar_ativos(banco=None):
    """Retorna [(id, nome), ...] só dos motoboys ativos — é o que
    alimenta o combobox de Pedidos."""

    banco = banco or conexao.banco

    return banco.buscar(
        "SELECT id, nome FROM motoboys WHERE ativo=1 ORDER BY nome"
    )


def criar(nome, banco=None):
    """Valida e insere. Retorna o id do motoboy criado. Levanta
    MotoboyInvalido se o nome estiver vazio."""

    banco = banco or conexao.banco

    nome = validar_nome(nome)

    banco.executar(
        "INSERT INTO motoboys(nome) VALUES(?)",
        (nome,)
    )

    return banco.ultimo_id()


def alternar_ativo(motoboy_id, banco=None):
    """Inverte o ativo/inativo do motoboy e retorna o novo status
    (1 ou 0). Um motoboy inativo some do combobox de Pedidos mas
    continua aparecendo no histórico de pedidos já feitos."""

    banco = banco or conexao.banco

    atual = banco.buscar_um("SELECT ativo FROM motoboys WHERE id=?", (motoboy_id,))
    novo_status = 0 if atual and atual[0] else 1

    banco.executar(
        "UPDATE motoboys SET ativo=? WHERE id=?",
        (novo_status, motoboy_id)
    )

    return novo_status


def excluir(motoboy_id, banco=None):
    """Exclui de vez se o motoboy nunca apareceu num pedido; senão só
    desativa, pra manter o histórico de entregas intacto. Retorna
    'excluido' ou 'desativado'."""

    banco = banco or conexao.banco

    ja_usado = banco.buscar_um(
        "SELECT COUNT(*) FROM pedidos WHERE motoboy_id=?",
        (motoboy_id,)
    )

    if ja_usado and ja_usado[0] > 0:
        banco.executar("UPDATE motoboys SET ativo=0 WHERE id=?", (motoboy_id,))
        return "desativado"

    banco.executar("DELETE FROM motoboys WHERE id=?", (motoboy_id,))
    return "excluido"
