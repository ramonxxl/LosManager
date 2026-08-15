"""
=================================================================
SAÍDA AMIGÁVEL DOS TESTES
=================================================================
O `unittest.TextTestRunner` padrão mostra o caminho técnico de cada
teste (ex: "test_criar_produto_valido
(testes.test_repositorio_produtos.TesteRepositorio...) ... ok"), que
não diz nada pra quem não mexe no código.

`rodar(suite)` troca isso por: um título por classe de teste (extraído
da docstring da classe) agrupando os testes relacionados, e uma linha
✓/✗ por teste com a descrição da docstring do método — cada arquivo em
testes/ já segue essa convenção (uma docstring de uma linha por classe
e por método). Sem docstring, cai pro nome técnico mesmo, então nada
quebra se um teste novo esquecer de documentar.

`python -m testes` (testes/__main__.py) usa isso; `python -m unittest`
direto (numa classe/arquivo específico) continua com a saída padrão do
unittest — este módulo não interfere nela.
=================================================================
"""

import sys
import time
import unittest


class _Cores:
    VERDE = "\033[32m"
    VERMELHO = "\033[31m"
    AMARELO = "\033[33m"
    CINZA = "\033[2m"
    NEGRITO = "\033[1m"
    RESET = "\033[0m"


class _ResultadoAmigavel(unittest.TestResult):

    def __init__(self, stream, usar_cor):
        super().__init__()
        self.stream = stream
        self.usar_cor = usar_cor
        self._classe_atual = None

    def _cor(self, codigo, texto):
        if not self.usar_cor:
            return texto
        return f"{codigo}{texto}{_Cores.RESET}"

    def _descricao(self, test):
        doc = test.shortDescription()
        return doc if doc else test._testMethodName

    def _titulo_classe(self, test):
        doc = test.__class__.__doc__
        if doc:
            return doc.strip().splitlines()[0]
        return test.__class__.__name__

    def startTest(self, test):
        super().startTest(test)

        if test.__class__ is not self._classe_atual:
            self._classe_atual = test.__class__
            self.stream.write("\n" + self._cor(_Cores.NEGRITO, self._titulo_classe(test)) + "\n")

    def addSuccess(self, test):
        super().addSuccess(test)
        self.stream.write(f"  {self._cor(_Cores.VERDE, '✓')} {self._descricao(test)}\n")

    def addError(self, test, err):
        super().addError(test, err)
        self.stream.write(f"  {self._cor(_Cores.VERMELHO, '✗')} {self._descricao(test)}  (erro inesperado)\n")

    def addFailure(self, test, err):
        super().addFailure(test, err)
        self.stream.write(f"  {self._cor(_Cores.VERMELHO, '✗')} {self._descricao(test)}\n")

    def addSkip(self, test, reason):
        super().addSkip(test, reason)
        self.stream.write(f"  {self._cor(_Cores.AMARELO, '○')} {self._descricao(test)}  (pulado: {reason})\n")


def _imprimir_falhas(resultado, stream, usar_cor):

    problemas = resultado.failures + resultado.errors

    if not problemas:
        return

    titulo = "Detalhes das falhas"
    if usar_cor:
        titulo = f"{_Cores.VERMELHO}{titulo}{_Cores.RESET}"

    stream.write(f"\n{titulo}\n" + "-" * 70 + "\n")

    for test, traceback_texto in problemas:
        doc = test.shortDescription() or test._testMethodName
        cabecalho = f"✗ {doc}"
        if usar_cor:
            cabecalho = f"{_Cores.VERMELHO}{cabecalho}{_Cores.RESET}"
        stream.write(f"\n{cabecalho}\n  {test.id()}\n")
        stream.write(traceback_texto)


def _imprimir_resumo(resultado, stream, usar_cor, duracao):

    total = resultado.testsRun
    falhas = len(resultado.failures) + len(resultado.errors)
    pulados = len(resultado.skipped)
    passaram = total - falhas - pulados

    partes = [f"{passaram} de {total} teste{'s' if total != 1 else ''} passaram"]

    if pulados:
        partes.append(f"{pulados} pulado{'s' if pulados != 1 else ''}")

    if falhas:
        partes.append(f"{falhas} falhou" if falhas == 1 else f"{falhas} falharam")

    linha = ", ".join(partes) + f" em {duracao:.2f}s"

    if usar_cor:
        cor = _Cores.VERDE if falhas == 0 else _Cores.VERMELHO
        linha = f"{cor}{linha}{_Cores.RESET}"

    stream.write("\n" + "-" * 70 + "\n" + linha + "\n")


def _garantir_utf8(stream):
    """O console do Windows às vezes usa um codepage antigo (cp1252)
    que não sabe codificar ✓/✗/○ — sem isso, a suíte quebra com
    UnicodeEncodeError bem no meio do primeiro teste (foi exatamente
    o que aconteceu na Action, que roda em windows-latest). Força
    UTF-8 na saída quando o stream permitir; streams que não suportam
    `reconfigure` (ex: um StringIO de teste) já são texto puro e não
    têm esse problema, então seguem sem alteração.

    De quebra, força `line_buffering` também: um stdout redirecionado
    pra um arquivo/pipe (como o da Action) normalmente usa buffer de
    bloco, então sem isso a saída só aparece toda de uma vez no fim —
    ou nem aparece, se o processo travar/for morto no meio."""

    reconfigure = getattr(stream, "reconfigure", None)

    if reconfigure is None:
        return

    try:
        reconfigure(encoding="utf-8", errors="backslashreplace", line_buffering=True)
    except (ValueError, OSError):
        pass


def rodar(suite, stream=None):
    """Roda `suite` com a saída amigável (agrupada por classe, com
    descrição em vez do nome técnico) e devolve um `unittest.TestResult`
    normal — `.wasSuccessful()` funciona igual ao runner padrão."""

    stream = stream or sys.stdout
    _garantir_utf8(stream)
    usar_cor = hasattr(stream, "isatty") and stream.isatty()

    resultado = _ResultadoAmigavel(stream, usar_cor)

    inicio = time.time()
    suite.run(resultado)
    duracao = time.time() - inicio

    _imprimir_falhas(resultado, stream, usar_cor)
    _imprimir_resumo(resultado, stream, usar_cor, duracao)

    return resultado
