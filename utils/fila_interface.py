"""
=================================================================
FILA SEGURA: THREAD DE REDE -> THREAD DA INTERFACE
=================================================================
O Tkinter só pode ser mexido pela thread principal. Chamar
`widget.after(...)` (ou `.configure(...)`) de dentro de uma thread
de rede já derrubou o programa e também deixa a janela "Não
respondendo" quando a thread principal está ocupada — era o que
as consultas de atualização, o CEP e o download da nova versão
faziam.

Aqui a thread de rede só coloca a função numa fila (thread-safe,
sem tocar no Tk) e a janela principal esvazia a fila a cada 100 ms
na própria thread da interface:

    fila_interface.agendar(lambda: self._concluir(pasta))   # qualquer thread
    fila_interface.iniciar(janela_principal)                # uma vez, no main.py
=================================================================
"""

import queue

from utils import diagnostico

_fila = queue.SimpleQueue()

INTERVALO_MS = 100
MAX_POR_RODADA = 50   # nunca prende a interface esvaziando uma fila enorme


def agendar(funcao):
    """Pode ser chamada de QUALQUER thread. `funcao` roda depois, na
    thread da interface."""
    _fila.put(funcao)


def processar():
    """Roda (na thread da interface) o que estiver na fila. Devolve
    quantas funções rodou. Erro numa função não derruba as outras."""

    rodadas = 0

    while rodadas < MAX_POR_RODADA:
        try:
            funcao = _fila.get_nowait()
        except queue.Empty:
            break

        rodadas += 1

        try:
            funcao()
        except Exception:
            diagnostico.registrar_excecao("fila_interface")

    return rodadas


def iniciar(janela):
    """Liga o esvaziamento periódico da fila na janela principal."""

    def ciclo():
        processar()
        janela.after(INTERVALO_MS, ciclo)

    janela.after(INTERVALO_MS, ciclo)
