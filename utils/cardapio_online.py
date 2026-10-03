"""
=================================================================
CARDÁPIO ONLINE — comunicação com o site de pedidos
=================================================================
Busca os pedidos feitos no cardápio online e avisa o site quando
um deles foi lançado aqui. O endereço e o token ficam nas
Configurações (chaves `cardapio_url` e `cardapio_token`); sem
token configurado a integração fica desligada e nada é chamado.

O token é secreto: fica só no banco da loja, nunca no código
(o repositório do LosManager é público por causa das atualizações).

Quem chama as funções de rede deve rodá-las fora da thread da
interface (ver main.py), como já é feito com o ViaCEP e com as
atualizações: a internet da loja pode estar lenta ou fora.
=================================================================
"""

import json
import threading
import urllib.request
import urllib.error

from utils import config


URL_PADRAO = "https://cardapio-los-pastelles.vercel.app"
INTERVALO_MS = 20000          # de quanto em quanto tempo o main.py consulta
PLACAR_A_CADA = 30            # placar da fidelidade: a cada 30 consultas (~10 min), só se mudou
STATUS_EM_ABERTO = {"novo", "preparo", "pronto", "entrega"}


class ErroCardapio(Exception):
    """Falha ao falar com o cardápio online — mensagem pronta pra mostrar."""


def configurado():
    return bool(config.obter("cardapio_token", "").strip())


def credenciais():
    """(endereço, token) lidos do banco. Chamar SEMPRE na thread da
    interface: a conexão SQLite é uma só e compartilhada, e usá-la de
    outra thread ao mesmo tempo derruba o programa (access violation —
    aconteceu no teste desta integração)."""

    url = (config.obter("cardapio_url", URL_PADRAO).strip() or URL_PADRAO).rstrip("/")
    return url, config.obter("cardapio_token", "").strip()


def _chamar(caminho, dados=None, cred=None, timeout=15):
    """Só HTTP — pode rodar em outra thread desde que receba `cred` pronto."""

    url, token = cred or credenciais()

    if not token:
        raise ErroCardapio("Integração com o cardápio online não configurada (Configurações).")

    corpo = json.dumps(dados).encode("utf-8") if dados is not None else None
    req = urllib.request.Request(
        url + caminho,
        data=corpo,
        method="POST" if corpo is not None else "GET",
        headers={"X-Integracao-Token": token, "Content-Type": "application/json", "User-Agent": "LosManager"},
    )

    try:
        with urllib.request.urlopen(req, timeout=timeout) as resposta:
            return json.loads(resposta.read().decode("utf-8"))

    except urllib.error.HTTPError as erro:
        if erro.code == 401:
            raise ErroCardapio("Token do cardápio online recusado. Confira em Configurações.")
        raise ErroCardapio(f"O cardápio online respondeu com erro {erro.code}.")

    except (urllib.error.URLError, TimeoutError, OSError):
        raise ErroCardapio("Sem conexão com o cardápio online. Confira a internet.")


def buscar_pedidos(cred=None):
    """Pedidos de hoje/ontem e os ainda em andamento (mais novo primeiro)."""
    return _chamar("/api/integracao", cred=cred).get("pedidos", [])


def marcar_lancado(pedido_online_id, numero, cred=None):
    """Avisa o site que o pedido entrou no caixa (vira 'Em preparo' lá)."""
    return _chamar("/api/integracao", {"id": pedido_online_id, "numero": str(numero)}, cred=cred)


def enviar_placar(placar, meta, cred=None):
    """Manda o placar completo da fidelidade (substitui o anterior no site)."""
    return _chamar("/api/integracao", {"fidelidade": placar, "meta": meta}, cred=cred, timeout=30)


_placar = {"ultimo": None}


def enviar_placar_em_segundo_plano(placar, meta):
    """Envia numa thread só se mudou desde o último envio que deu certo.
    Montar o placar (SQLite) e ler as credenciais fica com quem chama,
    na thread da interface; a thread aqui só faz HTTP e não toca no Tk."""

    assinatura = json.dumps([placar, meta], sort_keys=True)
    if assinatura == _placar["ultimo"]:
        return False

    cred = credenciais()   # aqui, na thread da interface

    def tarefa():
        try:
            enviar_placar(placar, meta, cred)
            _placar["ultimo"] = assinatura
        except ErroCardapio:
            pass           # tenta de novo na próxima rodada

    threading.Thread(target=tarefa, daemon=True).start()
    return True


def pendentes(pedidos, ja_lancados=()):
    """Os que ainda faltam lançar: em aberto, nunca lançados no site e
    sem pedido gravado aqui com esse id."""

    return [
        p for p in pedidos
        if p.get("status") in STATUS_EM_ABERTO
        and not p.get("importadoEm")
        and p.get("id") not in ja_lancados
    ]


# ==========================================================
# ESTADO COMPARTILHADO (main.py consulta, as telas leem)
# ==========================================================

_estado = {"pedidos": [], "erro": None}
_ouvintes = []


def ultimo_resultado():
    return dict(_estado)


def registrar_ouvinte(funcao):
    """Chamada (na thread da interface) a cada consulta nova."""
    _ouvintes.append(funcao)


def remover_ouvinte(funcao):
    if funcao in _ouvintes:
        _ouvintes.remove(funcao)


def publicar(pedidos=None, erro=None):
    if pedidos is not None:
        _estado["pedidos"] = pedidos
    _estado["erro"] = erro
    for funcao in list(_ouvintes):
        try:
            funcao()
        except Exception:
            remover_ouvinte(funcao)   # tela destruída: para de avisar


def buscar_em_segundo_plano(widget, ao_receber):
    """Busca os pedidos numa thread e entrega o resultado na thread da
    interface: ao_receber(pedidos, erro). A thread nunca toca no Tk
    (chamar widget.after() de outra thread derrubava o programa) —
    quem confere se chegou é o próprio widget, com after()."""

    resultado = {}
    cred = credenciais()   # aqui, na thread da interface

    def tarefa():
        try:
            resultado["pedidos"], resultado["erro"] = buscar_pedidos(cred), None
        except ErroCardapio as e:
            resultado["pedidos"], resultado["erro"] = None, str(e)

    def conferir():
        try:
            if not widget.winfo_exists():
                return
        except Exception:
            return
        if "erro" in resultado:
            ao_receber(resultado["pedidos"], resultado["erro"])
        else:
            widget.after(150, conferir)

    threading.Thread(target=tarefa, daemon=True).start()
    widget.after(150, conferir)


def marcar_lancado_em_segundo_plano(pedido_online_id, numero, ao_terminar=None):
    """Não trava o caixa esperando a internet; se falhar, o pedido já
    está gravado aqui e o site continua mostrando como 'novo' — o
    próprio LosManager sabe que já lançou (coluna pedido_online_id)."""

    cred = credenciais()   # aqui, na thread da interface

    def tarefa():
        try:
            marcar_lancado(pedido_online_id, numero, cred)
            erro = None
        except ErroCardapio as e:
            erro = str(e)
        if ao_terminar:
            ao_terminar(erro)

    threading.Thread(target=tarefa, daemon=True).start()
