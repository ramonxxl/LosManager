# Guarda o pedido em andamento na tela de Pedidos entre uma navegação e
# outra. Sem isso, sair da tela no meio de um pedido (pra conferir outro
# produto em Produtos, por exemplo) perdia o carrinho inteiro, porque
# `main.py` destrói e recria a tela do zero a cada navegação — ver
# "Entry point" no CLAUDE.md. Vive em memória (não no banco): fecha o
# programa, o rascunho some, e isso é intencional.

_rascunho = None


def salvar(estado):
    global _rascunho
    _rascunho = estado


def obter():
    return _rascunho


def limpar():
    global _rascunho
    _rascunho = None
