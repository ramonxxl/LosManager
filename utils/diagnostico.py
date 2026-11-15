"""
=================================================================
DIAGNÓSTICO DE TRAVAMENTOS (arquivo travamentos.log)
=================================================================
Quando o programa trava, ninguém vê o motivo: o .exe roda sem
console e o erro some. Este módulo deixa um registro no arquivo
`travamentos.log` (ao lado do banco):

- a cada 2 s a janela principal "dá sinal de vida"; se ficar mais
  de LIMITE_SEGUNDOS sem dar, o Python grava a pilha de TODAS as
  threads — mostra exatamente a linha em que a interface parou
  (impressora, banco, rede...). Se o programa se recuperar sozinho,
  fica registrado também;
- erros que o Tkinter engolia em silêncio dentro de botões e
  `after()` passam a ser gravados com a pilha completa;
- queda do próprio Python (access violation) grava a pilha.

O arquivo é limitado (~1 MB): passou disso, recomeça.
=================================================================
"""

import datetime
import faulthandler
import os
import sys
import traceback

from utils import config

NOME_ARQUIVO = "travamentos.log"
LIMITE_SEGUNDOS = 15          # sem sinal de vida por tanto tempo = travado
BATIMENTO_MS = 2000
TAMANHO_MAXIMO = 1_000_000

_arquivo = None


def caminho_log():
    return os.path.join(config.caminho_base(), NOME_ARQUIVO)


def _abrir():
    global _arquivo

    if _arquivo is not None:
        return _arquivo

    caminho = caminho_log()

    try:
        if os.path.exists(caminho) and os.path.getsize(caminho) > TAMANHO_MAXIMO:
            os.remove(caminho)
        _arquivo = open(caminho, "a", encoding="utf-8", buffering=1)
    except OSError:
        _arquivo = None

    return _arquivo


def _agora():
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def escrever(texto):
    """Linha com data e hora no log (silenciosa se não der pra gravar)."""

    arquivo = _abrir()

    if arquivo is None:
        return

    try:
        arquivo.write(f"[{_agora()}] {texto}\n")
    except Exception:
        pass


def registrar_excecao(onde, tipo=None, valor=None, pilha=None):
    """Grava um erro (o atual, se nenhum for passado) com a pilha."""

    if tipo is None:
        tipo, valor, pilha = sys.exc_info()

    detalhe = "".join(traceback.format_exception(tipo, valor, pilha))
    escrever(f"ERRO em {onde}:\n{detalhe}")


def iniciar(janela):
    """Liga o registro na janela principal. Nunca levanta erro: o
    diagnóstico não pode ser a causa de um problema."""

    try:
        arquivo = _abrir()

        if arquivo is None:
            return

        escrever(f"=== Los Manager aberto (Python {sys.version.split()[0]}) ===")

        faulthandler.enable(file=arquivo, all_threads=True)

        def erro_de_callback(tipo, valor, pilha):
            registrar_excecao("callback do Tkinter", tipo, valor, pilha)

        janela.report_callback_exception = erro_de_callback

        def batimento():
            # Re-arma o alarme: só dispara se este batimento parar de rodar.
            faulthandler.dump_traceback_later(LIMITE_SEGUNDOS, repeat=True, file=arquivo)
            janela.after(BATIMENTO_MS, batimento)

        batimento()

    except Exception:
        pass
