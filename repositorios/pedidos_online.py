"""
=================================================================
PEDIDOS DO CARDÁPIO ONLINE — conversão para o carrinho do caixa
=================================================================
O cardápio online (cardapio-los-pastelles.vercel.app) recebe o
pedido do cliente; aqui ele vira o mesmo rascunho que a tela de
Pedidos usa (ver utils/pedido_rascunho.py). O atendente confere,
escolhe o motoboy e finaliza como qualquer pedido — por isso o
cupom, o estoque, o caixa e a fidelidade seguem o fluxo normal.

O que acontece aqui:
- cada item do pedido online é casado com um produto ativo do
  LosManager pelo nome (sem acento/maiúscula, com alguns apelidos);
- adicionais pagos (Catupiry, Bacon...) viram linhas separadas
  com o produto "<nome> (adicional)", igual ao lançamento manual;
- o sabor do refrigerante lata escolhe o próprio produto;
- adicional/opção sem produto correspondente vai para a observação
  do item (o valor continua no item); item inteiro sem produto entra
  marcado com ⚠ e a tela de Pedidos não finaliza até ser trocado;
- o cliente é encontrado pelo telefone (ou cadastrado), e o
  endereço da entrega vira o endereço principal dele.

Os valores são sempre os que o cliente viu no cardápio online
(o total do cupom bate com a mensagem do WhatsApp).

Mesmo padrão de `repositorios/produtos.py`: nada de tkinter,
`banco=None` resolve via `conexao.banco` na hora da chamada.
=================================================================
"""

import re
import unicodedata

from database import conexao


SEM_MOTOBOY = "— Selecione —"          # iguais aos de screens/pedidos.py
RETIRADA = "Retirada (sem motoboy)"

PAGAMENTOS = {
    "pix": "PIX",
    "dinheiro": "Dinheiro",
    "credito": "Crédito",
    "debito": "Débito",
    "vr": "Vale-refeição",
}

# Nome no cardápio online (já normalizado) -> nome no LosManager
# (também normalizado). Só onde os dois são diferentes.
APELIDOS = {
    "explosao de camarao": "pastel de camarao",
    "camarao com catupiry": "pastel de camarao c/ catupiry",
    "caldinho de mandioca com costela 500ml": "caldinho de costela",
    "caldinho verde 500ml": "caldinho verde",
    "caldinho de feijao 500ml": "caldinho de feijao",
    "caldinho de quirera 500ml": "caldinho quirera",
    "caldinho de batata-salsa 500ml": "caldinho de mandioquinha salsa",
    "agua 500ml": "agua 500 ml",
    "suco tropical 500ml": "suco tropical 500 ml",
    "coca-cola 2l": "coca-cola 2 l",
    "guarana antarctica 2l": "guarana antarctica 2 l",
    "guarana joaninha 2l": "guarana joaninha 2 l",
    # sabor escolhido no "Refrigerante Lata"
    "coca-cola": "coca cola lata",
    "coca-cola zero": "coca cola zero lata",
    "guarana antarctica": "guarana antarctica lata",
    "fanta laranja": "fanta laranja lata",
}

GRUPOS_QUE_ESCOLHEM_O_PRODUTO = {"sabor"}


class PedidoOnlineInvalido(Exception):
    """Pedido online que não dá para lançar — a mensagem já vem
    pronta para mostrar ao atendente."""


# ==========================================================
# NOMES E TELEFONES
# ==========================================================

def normalizar(texto):
    """'Guaraná  Antarctica' -> 'guarana antarctica' (sem acento,
    minúsculo, espaços simples)."""

    texto = unicodedata.normalize("NFD", str(texto or ""))
    texto = "".join(c for c in texto if unicodedata.category(c) != "Mn")
    return re.sub(r"\s+", " ", texto).strip().lower()


def so_digitos(texto):
    return re.sub(r"\D", "", str(texto or ""))


def telefone_local(whatsapp):
    """'5512991112222' -> '12991112222' (tira o 55 do Brasil)."""

    d = so_digitos(whatsapp)

    if d.startswith("55") and len(d) in (12, 13):
        d = d[2:]

    return d


def formatar_telefone(whatsapp):
    """'5512991112222' -> '(12) 99111-2222'."""

    d = telefone_local(whatsapp)

    if len(d) == 11:
        return f"({d[:2]}) {d[2:7]}-{d[7:]}"

    if len(d) == 10:
        return f"({d[:2]}) {d[2:6]}-{d[6:]}"

    return d


def reais(centavos):
    return round((centavos or 0) / 100, 2)


# ==========================================================
# PRODUTOS
# ==========================================================

def _indice_produtos(banco):
    """{nome normalizado: (id, nome, preco)} dos produtos ativos."""

    indice = {}

    for produto_id, nome, preco in banco.buscar(
        "SELECT id, nome, preco FROM produtos WHERE ativo=1 ORDER BY id"
    ):
        indice.setdefault(normalizar(nome), (produto_id, nome, preco))

    return indice


def encontrar_produto(nome_online, indice):
    """Produto do LosManager para um nome do cardápio online, ou None."""

    chave = normalizar(nome_online)

    for candidato in (APELIDOS.get(chave), chave, chave.replace(" com ", " c/ ")):
        if candidato and candidato in indice:
            return indice[candidato]

    return None


def encontrar_adicional(nome_opcao, indice):
    """'Catupiry' -> produto 'Catupiry (adicional)'; alguns adicionais
    estão cadastrados sem o '(adicional)' (ex: 'Porção de Vinagrete')."""

    chave = normalizar(nome_opcao)

    return indice.get(f"{chave} (adicional)") or indice.get(chave)


# ==========================================================
# ITENS
# ==========================================================

def montar_itens(pedido_online, banco=None):
    """Converte os itens do pedido online para o formato do carrinho
    da tela de Pedidos. Retorna (itens, avisos): `avisos` lista o que
    não achou produto e foi para a observação."""

    banco = banco or conexao.banco
    indice = _indice_produtos(banco)

    itens = []
    avisos = []

    def adicionar(produto, qtd, valor_unitario, observacao=""):
        itens.append({
            "produto_id": produto[0],
            "nome": produto[1],
            "qtd": qtd,
            "valor_unitario": round(valor_unitario, 2),
            "subtotal": round(valor_unitario * qtd, 2),
            "observacao": observacao,
        })

    for item in pedido_online.get("itens") or []:

        qtd = int(item.get("qtd") or 1)
        unitario_online = reais(item.get("unit"))
        escolhas = item.get("escolhas") or []
        produto = encontrar_produto(item.get("nome"), indice)

        # O sabor do refrigerante decide o produto (Coca Cola Lata...).
        for e in escolhas:
            if normalizar(e.get("grupo")) in GRUPOS_QUE_ESCOLHEM_O_PRODUTO:
                produto = encontrar_produto(e.get("nome"), indice) or produto

        extras_em_linha = []       # (produto adicional, qtd por unidade, preço unitário)
        notas = []                 # vão na observação do item
        valor_em_linha = 0.0

        for e in escolhas:

            grupo = normalizar(e.get("grupo"))
            n = int(e.get("n") or 1)
            preco = reais(e.get("preco"))
            rotulo = f"{n}x {e.get('nome')}" if n > 1 else str(e.get("nome"))

            if grupo in GRUPOS_QUE_ESCOLHEM_O_PRODUTO:
                continue

            adicional = encontrar_adicional(e.get("nome"), indice) if preco > 0 else None

            if adicional:
                extras_em_linha.append((adicional, n, preco))
                valor_em_linha += preco * n
            else:
                notas.append(f"+ {rotulo}")

        if item.get("obs"):
            notas.append(str(item["obs"]))

        observacao = " | ".join(notas)

        if produto is None:
            avisos.append(
                f"\"{item.get('nome')}\" não tem produto igual no LosManager: aparece com ⚠ "
                "no carrinho. Remova e lance o produto certo antes de finalizar."
            )
            # Fica no carrinho marcado com ⚠ e sem produto: a tela de
            # Pedidos não deixa finalizar enquanto ele estiver lá.
            itens.append({
                "produto_id": None,
                "nome": f"⚠ {item.get('nome')}",
                "qtd": qtd,
                "valor_unitario": unitario_online,
                "subtotal": round(unitario_online * qtd, 2),
                "observacao": observacao,
            })
            continue

        # O item principal leva o valor do cliente menos os adicionais
        # que ganharam linha própria (assim o total bate certinho).
        adicionar(produto, qtd, unitario_online - valor_em_linha, observacao)

        for adicional, n, preco in extras_em_linha:
            adicionar(adicional, qtd * n, preco, f"adicional do {produto[1]}")  # sai em tarja na cozinha: "no X" lia como "sem X"

    return itens, avisos


# ==========================================================
# CLIENTE E ENDEREÇO
# ==========================================================

def encontrar_ou_criar_cliente(pedido_online, banco=None):
    """Acha o cliente pelo telefone (últimos 8 dígitos, conferindo o
    DDD quando os dois têm) ou cadastra um novo. Se for entrega, o
    endereço do pedido vira o principal (é o que sai no cupom).
    Retorna {"id", "nome", "telefone"} no formato da tela de Pedidos."""

    banco = banco or conexao.banco

    cliente_online = pedido_online.get("cliente") or {}
    nome = (cliente_online.get("nome") or "").strip() or "Cliente do cardápio online"
    local = telefone_local(cliente_online.get("whatsapp"))

    if len(local) < 8:
        raise PedidoOnlineInvalido("O pedido online veio sem um telefone válido.")

    escolhido = None

    for cliente_id, nome_cad, telefone in banco.buscar(
        "SELECT id, nome, telefone FROM clientes ORDER BY id"
    ):
        d = so_digitos(telefone)

        if len(d) < 8 or d[-8:] != local[-8:]:
            continue

        mesmo_ddd = len(d) < 10 or d[-11:-9] == local[-11:-9] or d[-10:-8] == local[-10:-8]

        if mesmo_ddd:
            escolhido = (cliente_id, nome_cad, telefone)
            break

    if escolhido is None:
        banco.executar(
            "INSERT INTO clientes (nome, telefone) VALUES (?, ?)",
            (nome, formatar_telefone(local))
        )
        escolhido = (banco.ultimo_id(), nome, formatar_telefone(local))

    cliente_id = escolhido[0]

    entrega = pedido_online.get("entrega") or {}

    if entrega.get("tipo") == "entrega":
        _registrar_endereco(cliente_id, entrega, banco)

    return {"id": cliente_id, "nome": escolhido[1], "telefone": escolhido[2]}


def _registrar_endereco(cliente_id, entrega, banco):

    rua = (entrega.get("rua") or "").strip()
    numero = " - ".join(p for p in ((entrega.get("numero") or "").strip(), (entrega.get("complemento") or "").strip()) if p)
    bairro = (entrega.get("bairro") or "").strip()
    cidade = (entrega.get("cidade") or "").strip()
    cep = so_digitos(entrega.get("cep"))

    if cep and len(cep) == 8:
        cep = f"{cep[:5]}-{cep[5:]}"

    existente = None

    for endereco_id, rua_cad, numero_cad in banco.buscar(
        "SELECT id, endereco, numero FROM enderecos_cliente WHERE cliente_id=?",
        (cliente_id,)
    ):
        if normalizar(rua_cad) == normalizar(rua) and normalizar(numero_cad) == normalizar(numero):
            existente = endereco_id
            break

    banco.executar(
        "UPDATE enderecos_cliente SET principal=0 WHERE cliente_id=?",
        (cliente_id,)
    )

    if existente:
        banco.executar(
            "UPDATE enderecos_cliente SET principal=1, bairro=?, cidade=?, cep=? WHERE id=?",
            (bairro, cidade, cep, existente)
        )
    else:
        banco.executar(
            """
            INSERT INTO enderecos_cliente
                (cliente_id, apelido, endereco, numero, bairro, cidade, cep, principal)
            VALUES (?, ?, ?, ?, ?, ?, ?, 1)
            """,
            (cliente_id, "Cardápio online", rua, numero, bairro, cidade, cep)
        )


# ==========================================================
# RASCUNHO DA TELA DE PEDIDOS
# ==========================================================

def ja_lancado(pedido_online_id, banco=None):
    """Número do pedido do LosManager em que esse pedido online já foi
    lançado (e não cancelado), ou None."""

    banco = banco or conexao.banco

    linha = banco.buscar_um(
        "SELECT numero FROM pedidos WHERE pedido_online_id=? AND status != 'Cancelado' ORDER BY id DESC",
        (pedido_online_id,)
    )

    return linha[0] if linha else None


def observacao_do_pedido(pedido_online):
    """Linha de observação do pedido inteiro (sai no cupom)."""

    partes = [f"Cardápio online #{pedido_online.get('id')}"]

    if pedido_online.get("cupom"):
        frete = (pedido_online.get("entrega") or {}).get("freteGratis")
        partes.append(f"Cupom {pedido_online['cupom']}" + (" (entrega grátis)" if frete else ""))

    pagamento = pedido_online.get("pagamento") or {}

    if pagamento.get("forma") == "dinheiro":
        troco = pagamento.get("troco")
        partes.append(f"Troco p/ R$ {reais(troco):.2f}".replace(".", ",") if troco else "Sem troco")

    entrega = pedido_online.get("entrega") or {}

    if entrega.get("combinar"):
        partes.append("Taxa de entrega a combinar")

    if entrega.get("referencia"):
        partes.append(f"Ref.: {entrega['referencia']}")

    if pedido_online.get("obs"):
        partes.append(str(pedido_online["obs"]))

    return " | ".join(partes)


def montar_rascunho(pedido_online, banco=None):
    """Estado no formato de utils/pedido_rascunho.py, pronto para a
    tela de Pedidos restaurar. Retorna (estado, avisos)."""

    banco = banco or conexao.banco

    if not pedido_online.get("itens"):
        raise PedidoOnlineInvalido("O pedido online não tem itens.")

    itens, avisos = montar_itens(pedido_online, banco)
    cliente = encontrar_ou_criar_cliente(pedido_online, banco)

    entrega = pedido_online.get("entrega") or {}
    taxa = reais(pedido_online.get("taxa"))
    forma = (pedido_online.get("pagamento") or {}).get("forma")

    estado = {
        "itens": itens,
        "total": round(sum(i["subtotal"] for i in itens), 2),
        "cliente_selecionado": cliente,
        "pagamento": PAGAMENTOS.get(forma, "PIX"),
        "valor_entrega": f"{taxa:.2f}".replace(".", ",") if taxa else "",
        "motoboy": RETIRADA if entrega.get("tipo") == "retirada" else SEM_MOTOBOY,
        "imprimir_cupom": True,
        "recompensa_pendente": None,
        "pedido_online": {
            "id": pedido_online.get("id"),
            "observacao": observacao_do_pedido(pedido_online),
            "total": reais(pedido_online.get("total")),
            # desconto do cupom do site: entra no campo desconto do pedido (o caixa já desconta das vendas)
            "desconto": reais(pedido_online.get("desconto")),
        },
    }

    return estado, avisos
