"""
=================================================================
TAMANHO DO PASTEL — Grande (22 cm) ou Mini (11 cm)
=================================================================
O preço cadastrado do pastel é o do Grande. O Mini custa o Grande
menos a diferença entre os tamanhos que o iFood usa em cada linha —
a MESMA regra do cardápio online (scripts/minis.mjs no projeto do
cardápio), pra o mini custar igual no balcão e no site:

    Tradicionais / Clássicos da Casa ........ − R$ 8,00
    Especiais (Carne, Frango, Calabresa,
      Bacon), Linha Fit, Pastéis Doces ...... − R$ 9,00
    Especiais - Linha Costela ............... − R$ 10,00
    Premium ................................. − R$ 11,00

Exceção: se a conta deixar o mini com menos de 45% do grande (ex.:
Explosão de Queijo, premium de R$ 16,90), usa − R$ 9,00 como os
outros pastéis desse preço. Categoria fora da lista (bebidas,
adicionais, caldos...) não tem mini.

Sem GUI e sem banco aqui — só a conta, testável à parte.
=================================================================
"""

import unicodedata

OBSERVACAO_MINI = "MINI (11 CM)"   # igual ao que o pedido online manda pra cozinha

_DIFERENCA = {
    "tradicionais": 8.0,
    "classicos da casa": 8.0,
    "especiais linha carne": 9.0,
    "especiais linha frango": 9.0,
    "especiais linha calabresa": 9.0,
    "especiais linha bacon": 9.0,
    "linha fit": 9.0,
    "pasteis doces": 9.0,
    "especiais linha costela": 10.0,
    "premium": 11.0,
}


def _normal(texto):
    """Sem acento, minúsculo e sem traço ("Especiais – Linha Carne" e
    "Especiais - Linha Carne" viram a mesma chave)."""
    t = str(texto or "").replace("–", " ").replace("—", " ").replace("-", " ")
    t = unicodedata.normalize("NFD", t).encode("ascii", "ignore").decode()
    return " ".join(t.lower().split())


def preco_mini(categoria, preco_grande):
    """Preço do mini (float, 2 casas) ou None se esse produto não tem mini."""

    diferenca = _DIFERENCA.get(_normal(categoria))

    if diferenca is None or not preco_grande:
        return None

    mini = preco_grande - diferenca

    if mini < preco_grande * 0.45:
        mini = preco_grande - 9.0

    return round(mini, 2) if mini > 0 else None
