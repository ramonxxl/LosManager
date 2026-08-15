"""
=================================================================
RESPONSIVIDADE - LOS MANAGER
=================================================================
Telas com uma tabela grande (Produtos, Ingredientes, Clientes,
Relatórios, o carrinho de Pedidos...) pediam uma altura fixa de
linhas (ex: height=15) pra Treeview. Em janelas pequenas (o
tamanho mínimo de 1200x700, notebooks antigos) isso sobra da tela
e obriga a rolar; em janelas grandes, sobra espaço vazio embaixo.

`linhas_para_tabela` calcula, com base no tamanho real já ocupado
pelos outros widgets da tela (medido de verdade via
`winfo_reqheight`/`pack_info`, não estimado), quantas linhas cabem
sem precisar da barra de rolagem da tela.

`tornar_dinamica` é o que faz isso valer durante o uso: prende um
recálculo no redimensionamento da janela principal (com debounce)
e aplica a nova contagem de linhas na tabela de verdade — sem isso,
a conta só rodava uma vez, no instante em que a tela era aberta, e
a tabela ficava com tamanho fixo dali em diante.
=================================================================
"""

# Precisa bater com o rowheight/heading configurados em
# utils/tema.py (aplicar_estilo_tabela) — se mudar lá, mude aqui.
ALTURA_LINHA_TABELA = 32
ALTURA_CABECALHO_TABELA = 29

MINIMO_LINHAS_PADRAO = 4
MARGEM_SEGURANCA = 8

# Tempo parado (ms) depois do último evento de redimensionamento
# antes de recalcular de verdade — evita recalcular a cada pixel
# arrastado durante o resize.
ATRASO_DEBOUNCE_MS = 150


def _pady_total(pady):
    """Normaliza o valor de `pady` do pack() (int único ou tupla
    top/bottom) pro total de pixels que ele consome."""

    if isinstance(pady, (tuple, list)):
        return sum(int(p) for p in pady)

    return int(pady) * 2


def _altura_ocupada(widget):
    """Altura que um widget filho de um pack() realmente ocupa,
    somando o pady usado ao empacotar (winfo_reqheight sozinho não
    inclui isso)."""

    altura = widget.winfo_reqheight()

    try:
        pady = widget.pack_info().get("pady", 0)
    except Exception:
        pady = 0

    return altura + _pady_total(pady)


def linhas_para_tabela(
    tela,
    scroll,
    pady_tabela=0,
    reservar_depois=0,
    excluir=(),
    minimo=MINIMO_LINHAS_PADRAO,
    maximo=None
):
    """
    tela: o frame da própria tela (ex.: `self` em Produtos/Clientes/
    etc.) — já empacotado com fill="both", expand=True dentro da
    área de conteúdo, então sua altura real (winfo_height) reflete
    o espaço realmente disponível na janela atual.

    scroll: o CTkScrollableFrame da tela. Devem já estar dentro dele
    TODOS os widgets que ficam acima (e, se for o caso, abaixo) da
    tabela — título, filtros, formulário, rodapé...

    pady_tabela: o `pady` que será passado pro `.pack()` da própria
    tabela — precisa ser o mesmo valor, senão a conta sobra ou falta
    exatamente por essa diferença.

    excluir: widgets a ignorar na soma (tipicamente a própria tabela,
    quando ela já existe e está sendo recalculada de novo depois de
    um redimensionamento — senão o tamanho ANTIGO dela entraria na
    conta do tamanho NOVO).

    reservar_depois: altura (px) a reservar pra widgets que ainda não
    existem no momento da chamada (uso só na primeira montagem).
    """

    tela.update_idletasks()

    altura_disponivel = tela.winfo_height()

    # O CTkScrollableFrame desenha cantos arredondados (+ borda) ao
    # redor do canvas de rolagem — esse espaço não é aproveitável.
    borda = scroll.cget("corner_radius") + scroll.cget("border_width")
    altura_disponivel -= 2 * borda

    ja_usado = reservar_depois + _pady_total(pady_tabela) + MARGEM_SEGURANCA

    for widget in scroll.winfo_children():
        if widget in excluir:
            continue
        ja_usado += _altura_ocupada(widget)

    livre = altura_disponivel - ja_usado

    linhas = (livre - ALTURA_CABECALHO_TABELA) // ALTURA_LINHA_TABELA

    if maximo is not None:
        linhas = min(linhas, maximo)

    return int(max(minimo, linhas))


def tornar_dinamica(tela, scroll, obter_tabela, **kwargs_linhas):
    """
    Faz a tabela reagir de verdade a redimensionamentos da janela
    principal — recalcula `linhas_para_tabela` (excluindo a própria
    tabela da soma) e aplica via `.configure(height=...)` sempre que
    o usuário parar de arrastar a borda da janela por um instante.

    tela / scroll: mesmos parâmetros de `linhas_para_tabela`.
    obter_tabela: função sem argumentos que devolve o Treeview atual
    (ex.: `lambda: self.tabela`) — indireto assim porque, no momento
    em que essa função é chamada pela 1ª vez, o widget já existe, mas
    passar uma referência direta obrigaria uma ordem de criação mais
    rígida.

    Se cancela sozinha quando a tela é destruída (troca de tela pelo
    menu lateral) — sem isso, o evento continuaria preso na janela
    principal apontando pra widgets que não existem mais.
    """

    janela = tela.winfo_toplevel()
    id_pendente = [None]
    id_bind = [None]
    desativada = [False]

    def recalcular():
        id_pendente[0] = None

        if desativada[0] or not tela.winfo_exists():
            return

        tabela = obter_tabela()
        novas_linhas = linhas_para_tabela(tela, scroll, excluir=(tabela,), **kwargs_linhas)

        if int(tabela.cget("height")) != novas_linhas:
            tabela.configure(height=novas_linhas)

    def ao_redimensionar(_evento):
        if desativada[0] or not tela.winfo_exists():
            if id_bind[0] is not None:
                janela.unbind("<Configure>", id_bind[0])
            return

        if id_pendente[0] is not None:
            janela.after_cancel(id_pendente[0])

        id_pendente[0] = janela.after(ATRASO_DEBOUNCE_MS, recalcular)

    def desativar():
        """Desliga o binding e cancela qualquer recálculo pendente.
        Chamado por `fechar_janela` antes do destroy, pra evitar que
        o <Configure> emitido pelo próprio destroy agende um after()
        que dispara contra widgets já destruídos."""
        desativada[0] = True
        if id_pendente[0] is not None:
            janela.after_cancel(id_pendente[0])
            id_pendente[0] = None
        if id_bind[0] is not None:
            janela.unbind("<Configure>", id_bind[0])
            id_bind[0] = None

    id_bind[0] = janela.bind("<Configure>", ao_redimensionar, add="+")

    # Expõe o desativador no frame da tela pra que fechar_janela()
    # possa chamar antes do destroy.
    if not hasattr(tela, "_responsivo_desativar"):
        tela._responsivo_desativar = []
    tela._responsivo_desativar.append(desativar)
