"""
=================================================================
AUTOATUALIZAÇÃO (baixa o release mais novo e substitui a instalação)
=================================================================
Complementa utils/atualizacao.py: aquele módulo só CONSULTA se existe
uma versão mais nova. Este módulo baixa o .zip do release, descompacta
e troca os arquivos da instalação atual pelos novos sozinho — o
usuário não precisa mais abrir o navegador, baixar, descompactar e
substituir a pasta na mão.

Só faz sentido ser chamado a partir de um .exe já compilado
(`sys.frozen`), porque só nesse caso existe uma "instalação" (a pasta
ao lado do .exe, ver utils/config.caminho_base()) pra substituir.

Como o Windows não deixa um .exe sobrescrever a si mesmo (nem os
arquivos abertos por ele) enquanto está rodando, o fluxo é:
  1. baixa o .zip do release pra uma pasta temporária;
  2. descompacta numa subpasta temporária;
  3. escreve um script .bat, também numa pasta temporária, que espera
     este processo (pelo PID) terminar, copia os arquivos novos por
     cima da pasta de instalação e reabre o programa;
  4. dispara esse script como processo independente e encerra o app —
     o resto acontece depois que este processo Python já não existe
     mais.
=================================================================
"""

import os
import sys
import tempfile
import threading
import subprocess
import urllib.request
import zipfile

import customtkinter as ctk
from tkinter import messagebox

from utils import config
from utils import fila_interface
from utils import tema


def baixar_e_preparar(url_download, ao_progresso=None):
    """Baixa o .zip do release e descompacta numa pasta temporária.
    Bloqueante — sempre rodar em thread separada. `ao_progresso(recebido,
    total)` é chamado a cada pedaço baixado (`total` fica 0 se o servidor
    não informar o tamanho no cabeçalho). Retorna o caminho da pasta já
    descompactada, pronta para `aplicar_e_reiniciar`."""

    pasta_temp = tempfile.mkdtemp(prefix="losmanager_update_")
    caminho_zip = os.path.join(pasta_temp, "atualizacao.zip")

    requisicao = urllib.request.Request(
        url_download,
        headers={"Accept": "application/octet-stream"}
    )

    with urllib.request.urlopen(requisicao, timeout=30) as resposta:

        total = int(resposta.headers.get("Content-Length") or 0)
        recebido = 0

        with open(caminho_zip, "wb") as arquivo:

            while True:

                pedaco = resposta.read(262144)

                if not pedaco:
                    break

                arquivo.write(pedaco)
                recebido += len(pedaco)

                if ao_progresso:
                    ao_progresso(recebido, total)

    pasta_extraida = os.path.join(pasta_temp, "extraido")
    os.makedirs(pasta_extraida, exist_ok=True)

    with zipfile.ZipFile(caminho_zip, "r") as zip_arquivo:
        zip_arquivo.extractall(pasta_extraida)

    os.remove(caminho_zip)

    return pasta_extraida


def aplicar_e_reiniciar(pasta_extraida):
    """Dispara, como processo independente, um script .bat que espera
    este processo (pelo PID) terminar, copia os arquivos novos por cima
    da pasta de instalação e reabre o programa. O robocopy roda sem
    /MIR nem /PURGE de propósito: só sobrescreve/adiciona arquivo,
    nunca apaga — o banco de dados (losmanager.db) e a pasta backups/
    moram do lado do .exe mas não fazem parte do .zip do release, então
    um espelhamento (/MIR) os apagaria junto."""

    pasta_instalacao = config.caminho_base()
    caminho_exe = sys.executable
    pid_atual = os.getpid()

    caminho_script = os.path.join(tempfile.gettempdir(), "losmanager_atualizar.bat")

    conteudo_script = (
        "@echo off\n"
        ":esperar\n"
        f'tasklist /FI "PID eq {pid_atual}" 2>NUL | find "{pid_atual}" >NUL\n'
        "if not errorlevel 1 (\n"
        "    timeout /t 1 /nobreak >nul\n"
        "    goto esperar\n"
        ")\n"
        f'robocopy "{pasta_extraida}" "{pasta_instalacao}" /E /IS /IT /R:3 /W:1 /NFL /NDL /NJH /NJS\n'
        f'start "" "{caminho_exe}"\n'
        f'rmdir /S /Q "{os.path.dirname(pasta_extraida)}"\n'
        '(goto) 2>nul & del "%~f0"\n'
    )

    with open(caminho_script, "w", encoding="utf-8") as arquivo:
        arquivo.write(conteudo_script)

    subprocess.Popen(
        ["cmd", "/c", caminho_script],
        creationflags=subprocess.CREATE_NO_WINDOW,
        close_fds=True
    )


class JanelaAtualizacao(ctk.CTkToplevel):
    """Popup modal de progresso mostrado durante o download da
    atualização. O app inteiro fecha e reabre sozinho logo em seguida,
    então não tem por que oferecer um botão de fechar no meio do
    processo."""

    def __init__(self, master, url_download):
        super().__init__(master.winfo_toplevel())

        self.master_app = master.winfo_toplevel()

        self.title("Atualizando o Los Manager")
        self.resizable(False, False)
        self.transient(self.master_app)
        self.protocol("WM_DELETE_WINDOW", lambda: None)

        ctk.CTkLabel(
            self,
            text="Baixando atualização...",
            font=("Arial", 15, "bold")
        ).pack(padx=30, pady=(24, 10))

        self.barra = ctk.CTkProgressBar(self, width=340, progress_color=tema.COR_LARANJA)
        self.barra.set(0)
        self.barra.pack(padx=30, pady=(0, 8))

        self.lbl_status = ctk.CTkLabel(
            self,
            text="Conectando...",
            font=("Arial", 12),
            text_color="gray"
        )
        self.lbl_status.pack(padx=30, pady=(0, 24))

        # O tamanho só é aplicado depois que o Tk processa os `after`
        # internos do CustomTkinter — mesmo motivo dos outros popups
        # do sistema (ver utils/calendario.py).
        self.after(60, self._ajustar_tamanho)

        self.grab_set()

        threading.Thread(target=self._baixar, args=(url_download,), daemon=True).start()

    # ======================================================

    def _ajustar_tamanho(self):

        self.update_idletasks()

        largura = max(self.winfo_reqwidth(), 400)
        altura = max(self.winfo_reqheight(), 160)

        self.geometry(f"{largura}x{altura}")
        self.minsize(largura, altura)

    # ======================================================

    def _baixar(self, url_download):

        try:
            pasta_extraida = baixar_e_preparar(url_download, self._progresso)
        except Exception as erro:
            fila_interface.agendar(lambda: self._erro(erro))
            return

        fila_interface.agendar(lambda: self._concluir(pasta_extraida))

    # ======================================================

    def _progresso(self, recebido, total):

        if total > 0:
            fracao = min(recebido / total, 1.0)
            texto = f"{recebido // 1024} KB / {total // 1024} KB"
        else:
            fracao = None
            texto = f"{recebido // 1024} KB baixados"

        def atualizar():

            if not self.winfo_exists():
                return

            if fracao is not None:
                self.barra.set(fracao)

            self.lbl_status.configure(text=texto)

        fila_interface.agendar(atualizar)

    # ======================================================

    def _erro(self, erro):

        self.grab_release()
        self.destroy()

        messagebox.showerror(
            "Atualização",
            f"Não foi possível baixar a atualização automaticamente:\n\n{erro}\n\n"
            "Você pode baixar e instalar manualmente pela página de releases "
            "do GitHub."
        )

    # ======================================================

    def _concluir(self, pasta_extraida):

        self.lbl_status.configure(text="Instalando e reiniciando...")

        try:
            aplicar_e_reiniciar(pasta_extraida)
        except Exception as erro:

            self.grab_release()
            self.destroy()

            messagebox.showerror(
                "Atualização",
                f"O download terminou, mas não foi possível preparar a "
                f"instalação automática:\n\n{erro}"
            )
            return

        # Encerra o processo já — o script .bat disparado em
        # aplicar_e_reiniciar() é quem termina o trabalho (copiar os
        # arquivos e reabrir o programa) depois que este processo sair
        # do caminho.
        self.master_app.destroy()
        os._exit(0)


def iniciar(master, url_download):
    """Ponto de entrada usado pelas telas: abre o popup de progresso e
    cuida de todo o fluxo (baixar, aplicar, reiniciar). Chamado tanto
    pelo aviso automático de abertura (main.py) quanto pelo botão
    "Verificar Atualização" (Configurações)."""

    JanelaAtualizacao(master, url_download)
