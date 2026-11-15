"""
Fila que leva o resultado das threads de rede para a thread da
interface (utils/fila_interface.py) e registro de travamentos
(utils/diagnostico.py). Sem tela: nada de Tkinter.

Rodar com:
    python -m testes
"""

import os
import tempfile
import threading
import unittest
from unittest import mock

from utils import diagnostico, fila_interface


class TesteFilaInterface(unittest.TestCase):
    """Fila entre as threads de rede e a thread da interface"""

    def setUp(self):
        fila_interface.processar()   # esvazia sobra de outros testes

    def test_roda_na_ordem_em_que_foi_agendado(self):
        """As funções agendadas rodam na ordem de chegada"""
        saida = []
        for n in range(5):
            fila_interface.agendar(lambda n=n: saida.append(n))
        self.assertEqual(fila_interface.processar(), 5)
        self.assertEqual(saida, [0, 1, 2, 3, 4])

    def test_agendar_de_outra_thread_e_rodar_na_principal(self):
        """Agendado por uma thread de rede, só roda quando a thread principal processa"""
        saida = []
        principal = threading.get_ident()
        t = threading.Thread(target=lambda: fila_interface.agendar(lambda: saida.append(threading.get_ident())))
        t.start()
        t.join()
        self.assertEqual(saida, [])
        fila_interface.processar()
        self.assertEqual(saida, [principal])

    def test_erro_numa_funcao_nao_derruba_as_outras(self):
        """Uma função que dá erro é registrada e as seguintes continuam"""
        saida = []
        fila_interface.agendar(lambda: 1 / 0)
        fila_interface.agendar(lambda: saida.append("ok"))
        with mock.patch.object(diagnostico, "registrar_excecao") as registro:
            self.assertEqual(fila_interface.processar(), 2)
        self.assertEqual(saida, ["ok"])
        registro.assert_called_once()

    def test_nao_prende_a_interface_com_fila_enorme(self):
        """Cada rodada processa no máximo MAX_POR_RODADA funções"""
        for _ in range(fila_interface.MAX_POR_RODADA + 10):
            fila_interface.agendar(lambda: None)
        self.assertEqual(fila_interface.processar(), fila_interface.MAX_POR_RODADA)
        self.assertEqual(fila_interface.processar(), 10)


class TesteDiagnostico(unittest.TestCase):
    """Registro de erros e travamentos em travamentos.log"""

    def test_registra_erro_com_pilha_no_arquivo(self):
        """registrar_excecao grava o local e a pilha do erro no travamentos.log"""
        pasta = tempfile.mkdtemp()
        with mock.patch.object(diagnostico.config, "caminho_base", return_value=pasta), \
             mock.patch.object(diagnostico, "_arquivo", None):
            try:
                raise ValueError("falha de teste")
            except ValueError:
                diagnostico.registrar_excecao("teste")
            diagnostico._arquivo.close()
        with open(os.path.join(pasta, diagnostico.NOME_ARQUIVO), encoding="utf-8") as f:
            texto = f.read()
        self.assertIn("ERRO em teste", texto)
        self.assertIn("ValueError: falha de teste", texto)

    def test_log_grande_recomeca(self):
        """Passou de ~1 MB, o log é apagado na próxima abertura"""
        pasta = tempfile.mkdtemp()
        caminho = os.path.join(pasta, diagnostico.NOME_ARQUIVO)
        with open(caminho, "w", encoding="utf-8") as f:
            f.write("x" * (diagnostico.TAMANHO_MAXIMO + 1))
        with mock.patch.object(diagnostico.config, "caminho_base", return_value=pasta), \
             mock.patch.object(diagnostico, "_arquivo", None):
            diagnostico.escrever("novo")
            diagnostico._arquivo.close()
        self.assertLess(os.path.getsize(caminho), 1000)


if __name__ == "__main__":
    unittest.main()
