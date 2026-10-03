"""
=================================================================
CLIENTES — exclusão segura
=================================================================
Mesmo padrão de `repositorios/motoboys.py`: sem GUI aqui e `banco`
opcional (resolvido via `conexao.banco` na hora da chamada), pra os
testes usarem um banco ":memory:".

Excluir um cliente nunca apaga venda: os pedidos dele continuam no
caixa e nos relatórios, só passam a ser de "Cliente Balcão"
(cliente_id NULL — os relatórios já fazem LEFT JOIN em clientes).
Some junto o que só existe por causa do cliente: endereços e a
fidelidade (cache + histórico de pontos). Tudo numa transação só.
=================================================================
"""

from database import conexao


def resumo_exclusao(cliente_id, banco=None):
    """O que a exclusão vai mexer — para a tela confirmar antes:
    {'nome', 'pedidos', 'enderecos', 'pontos'} ou None se não existe."""

    banco = banco or conexao.banco

    registro = banco.buscar_um("SELECT nome FROM clientes WHERE id=?", (cliente_id,))
    if not registro:
        return None

    pontos = banco.buscar_um("SELECT total_pedidos FROM fidelidade WHERE cliente_id=?", (cliente_id,))

    return {
        "nome": registro[0],
        "pedidos": banco.buscar_um("SELECT COUNT(*) FROM pedidos WHERE cliente_id=?", (cliente_id,))[0],
        "enderecos": banco.buscar_um("SELECT COUNT(*) FROM enderecos_cliente WHERE cliente_id=?", (cliente_id,))[0],
        "pontos": pontos[0] if pontos else 0,
    }


def excluir(cliente_id, banco=None):
    """Exclui o cliente; os pedidos dele viram de Cliente Balcão.
    Retorna quantos pedidos foram desvinculados."""

    banco = banco or conexao.banco

    try:
        desvinculados = banco.buscar_um("SELECT COUNT(*) FROM pedidos WHERE cliente_id=?", (cliente_id,))[0]
        banco.executar_sem_commit("UPDATE pedidos SET cliente_id=NULL WHERE cliente_id=?", (cliente_id,))
        banco.executar_sem_commit("DELETE FROM historico_fidelidade WHERE cliente_id=?", (cliente_id,))
        banco.executar_sem_commit("DELETE FROM fidelidade WHERE cliente_id=?", (cliente_id,))
        banco.executar_sem_commit("DELETE FROM enderecos_cliente WHERE cliente_id=?", (cliente_id,))
        banco.executar_sem_commit("DELETE FROM clientes WHERE id=?", (cliente_id,))
        banco.commit()
    except Exception:
        banco.rollback()
        raise

    return desvinculados
