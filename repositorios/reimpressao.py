"""
=================================================================
REIMPRESSÃO DE CUPOM — 2ª via de um pedido já gravado
=================================================================
Relatórios > "🖨 Reimprimir Cupom" lê o pedido do banco e devolve
os mesmos dicionários que Pedidos.gravar_pedido() monta na hora de
finalizar, no formato que utils/impressora.montar_cupom() espera.
Só lê: não mexe em estoque, caixa nem fidelidade.

Mesmo padrão de `repositorios/produtos.py`: nada de tkinter,
`banco=None` resolve via `conexao.banco` na hora da chamada.
=================================================================
"""

from database import conexao


class ReimpressaoInvalida(Exception):
    """Mensagem pronta (pt-BR) para a tela mostrar ao usuário."""


def endereco_principal(cliente_id, banco=None):
    """Endereço principal do cliente numa linha só, pro cupom — o
    motoboy não pode ter que abrir o cadastro pra saber pra onde
    entregar. Cliente Balcão (sem cliente_id) ou cliente sem nenhum
    endereço cadastrado devolve string vazia."""

    banco = banco or conexao.banco

    if cliente_id is None:
        return ""

    endereco = banco.buscar_um(
        """
        SELECT endereco, numero, bairro, cidade
        FROM enderecos_cliente
        WHERE cliente_id=? AND principal=1
        """,
        (cliente_id,)
    )

    if not endereco:
        return ""

    rua, numero, bairro, cidade = endereco

    linha = ", ".join(p for p in (rua, numero) if p)
    complemento = " - ".join(p for p in (bairro, cidade) if p)

    if complemento:
        linha = f"{linha} - {complemento}" if linha else complemento

    return linha


def dados_do_pedido(pedido_id, banco=None):
    """Devolve (pedido, itens) prontos para impressora.imprimir_cupom().
    Pedido inexistente ou cancelado levanta ReimpressaoInvalida."""

    banco = banco or conexao.banco

    linha = banco.buscar_um(
        """
        SELECT p.numero, p.cliente_id, COALESCE(c.nome, 'Cliente Balcão'),
               p.data, p.hora, p.subtotal, p.desconto, p.acrescimo,
               p.total, p.pagamento, p.status, p.observacao
        FROM pedidos p
        LEFT JOIN clientes c ON c.id = p.cliente_id
        WHERE p.id = ?
        """,
        (pedido_id,)
    )

    if linha is None:
        raise ReimpressaoInvalida("Pedido não encontrado.")

    (numero, cliente_id, cliente, data, hora, subtotal, desconto,
     acrescimo, total, pagamento, status, observacao) = linha

    if status == "Cancelado":
        raise ReimpressaoInvalida(
            f"O pedido Nº {int(numero):04d} está cancelado. "
            "Reverta o cancelamento antes de reimprimir o cupom."
        )

    pedido = {
        "numero": int(numero),
        "cliente": cliente,
        "endereco_cliente": endereco_principal(cliente_id, banco=banco),
        "data": data,
        "hora": hora,
        "subtotal": subtotal or 0.0,
        "desconto": desconto or 0.0,
        "acrescimo": acrescimo or 0.0,
        "total": total or 0.0,
        "pagamento": pagamento or "",
        "observacao": observacao or "",
    }

    itens = [
        {
            "nome": nome,
            "qtd": qtd,
            "valor_unitario": valor_unitario or 0.0,
            "subtotal": item_subtotal or 0.0,
            "observacao": observacao_item or "",
        }
        for nome, qtd, valor_unitario, item_subtotal, observacao_item in banco.buscar(
            """
            SELECT COALESCE(pr.nome, 'Produto removido'), i.quantidade,
                   i.valor_unitario, i.subtotal, i.observacao
            FROM itens_pedido i
            LEFT JOIN produtos pr ON pr.id = i.produto_id
            WHERE i.pedido_id = ?
            ORDER BY i.id
            """,
            (pedido_id,)
        )
    ]

    return pedido, itens
