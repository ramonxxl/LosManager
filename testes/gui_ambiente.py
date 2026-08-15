"""
=================================================================
AMBIENTE GRÁFICO PARA TESTES DE GUI DE VERDADE (Tk/CustomTkinter)
=================================================================
Um teste que instancia uma tela de verdade (ex: Produtos) precisa de
um Tcl/Tk com display pra existir — não dá pra "mockar" isso. Esse
módulo decide sozinho o que já está disponível e cobre os três casos:

- Windows sempre tem uma sessão gráfica própria — nada a fazer.
- Linux/Mac com display real (monitor, ou X encaminhado por SSH) usa
  esse display direto.
- Linux só de terminal (sem display nenhum funcionando) sobe um Xvfb
  (servidor de display virtual) sozinho.

Se nada disso for possível (ex: Linux sem Xvfb instalado), os testes
que dependerem disso são pulados (unittest.SkipTest) com uma mensagem
explicando o que falta, em vez de quebrar a suíte inteira.

O Xvfb, uma vez ligado, fica vivo pelo resto do processo (um único
processo reaproveitado por todo `python -m testes`, desligado só via
atexit) em vez de subir/derrubar um a cada teste — matar o Xvfb no
meio do processo já causou um "XIO: fatal IO error" que derrubava o
interpretador inteiro, porque o customtkinter mantém uma thread de
fundo (ScalingTracker) que reagenda `.after()` em cima de QUALQUER
janela CTk existente no processo, e ela não sabe que o display morreu.
=================================================================
"""

import atexit
import contextlib
import os
import platform
import shutil
import subprocess
import time
import unittest


def _display_funciona():
    """Único jeito confiável de saber se o display atual (real ou
    Xvfb) está utilizável: tenta abrir e fechar uma janela Tk de
    verdade."""

    try:
        import tkinter
        raiz = tkinter.Tk()
        raiz.withdraw()
        raiz.destroy()
        return True
    except Exception:
        return False


def _numero_display_livre():
    """Escolhe um número de display (":N") verificando que nenhum
    outro Xvfb/X já está usando ele (evita bater com o :0 real ou com
    outra execução de teste em paralelo)."""

    for numero in range(50, 200):
        if not os.path.exists(f"/tmp/.X11-unix/X{numero}"):
            return numero

    raise RuntimeError("Não achei um número de display livre para o Xvfb.")


_xvfb = {"processo": None, "display": None}


def _encerrar_xvfb():
    """Registrado via atexit — só roda uma vez, na saída do processo
    de teste, nunca entre um teste de GUI e outro."""

    processo = _xvfb["processo"]

    if processo is None:
        return

    processo.terminate()

    try:
        processo.wait(timeout=5)
    except subprocess.TimeoutExpired:
        processo.kill()

    _xvfb["processo"] = None


def _obter_display_xvfb():
    """Sobe o Xvfb na primeira chamada e devolve o mesmo display nas
    chamadas seguintes (dentro do mesmo processo) em vez de derrubar e
    subir um novo a cada teste."""

    processo = _xvfb["processo"]

    if processo is not None and processo.poll() is None:
        return _xvfb["display"]

    if shutil.which("Xvfb") is None:
        raise unittest.SkipTest(
            "Sem display gráfico disponível e o Xvfb (servidor de "
            "display virtual) não está instalado. Instale com "
            "'sudo apt install xvfb' (Debian/Ubuntu) para rodar os "
            "testes de GUI num Linux sem monitor."
        )

    numero_display = _numero_display_livre()
    display = f":{numero_display}"

    _xvfb["processo"] = subprocess.Popen(
        # Mais alto que o 1366x768 do PC da loja de propósito: alguns
        # testes de GUI (ex: test_tela_produtos_responsividade.py)
        # precisam conseguir pedir uma janela bem mais alta que 768px
        # pra provar a diferença de linhas, e um display virtual do
        # tamanho exato da loja não deixa espaço pra isso.
        ["Xvfb", display, "-screen", "0", "1366x1400x24"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )
    _xvfb["display"] = display

    atexit.register(_encerrar_xvfb)

    return display


def fechar_janela(root):
    """Destrói uma janela Tk/CustomTkinter criada num teste, cancelando
    antes qualquer job `after()` pendente (o debounce de
    utils/responsivo.py, os timers internos do customtkinter) — sem
    isso eles disparam depois do destroy, contra widgets que não
    existem mais, e o Tcl imprime "invalid command name" no stderr."""

    # Desativa os bindings de tornar_dinamica ANTES de cancelar os
    # after() e destruir — senão o próprio destroy() emite <Configure>,
    # que agenda um novo after() tarde demais pra ser cancelado.
    for widget in _todos_os_filhos(root):
        for desativar in getattr(widget, "_responsivo_desativar", []):
            desativar()

    for id_job in root.tk.call("after", "info"):
        root.after_cancel(id_job)

    root.destroy()


def _todos_os_filhos(widget):
    """Percorre recursivamente todos os filhos de um widget."""
    filhos = []
    for filho in widget.winfo_children():
        filhos.append(filho)
        filhos.extend(_todos_os_filhos(filho))
    return filhos


@contextlib.contextmanager
def ambiente_grafico():
    """Context manager: garante um display Tk utilizável dentro do
    `with`, subindo um Xvfb se for a única forma de conseguir um.
    Uso:

        with ambiente_grafico():
            root = ctk.CTk()
            ...
    """

    sistema = platform.system()

    if sistema == "Windows" or _display_funciona():
        yield
        return

    if sistema != "Linux":
        raise unittest.SkipTest(
            f"Sem display gráfico utilizável em {sistema}, e o "
            "fallback automático de display virtual (Xvfb) só existe "
            "para Linux."
        )

    display = _obter_display_xvfb()

    display_anterior = os.environ.get("DISPLAY")
    os.environ["DISPLAY"] = display

    try:

        # Espera o Xvfb terminar de subir, tentando por até uns 3s em
        # vez de um sleep fixo — mais rápido na maioria das máquinas e
        # ainda tolerante em máquinas carregadas. Só relevante na
        # primeira chamada; nas seguintes o Xvfb já está de pé.
        for _ in range(30):
            if _display_funciona():
                break
            time.sleep(0.1)
        else:
            raise unittest.SkipTest(
                "O Xvfb iniciou mas o Tk não conseguiu usar o display "
                f"virtual {display}."
            )

        yield

    finally:

        # O processo do Xvfb continua vivo (ver _obter_display_xvfb) —
        # só desfaz a variável de ambiente, pra não vazar pros testes
        # que não são de GUI.
        if display_anterior is None:
            os.environ.pop("DISPLAY", None)
        else:
            os.environ["DISPLAY"] = display_anterior
