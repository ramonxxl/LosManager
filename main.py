import customtkinter as ctk
from tkinter import messagebox
import webbrowser
from PIL import Image

from database.conexao import banco
from screens.dashboard import Dashboard
from screens.produtos import Produtos
from screens.ingredientes import Ingredientes
from screens.clientes import Clientes
from screens.pedidos import Pedidos
from screens.configuracoes import Configuracoes
from screens.caixa import Caixa
from screens.relatorios import Relatorios
from screens.fidelidade import Fidelidade
from utils import config
from utils import tema
from utils import atualizacao
from utils import autoatualizador
from utils import caixa_estado

ctk.set_appearance_mode("light")
ctk.set_default_color_theme("blue")


class LosManager(ctk.CTk):

    def __init__(self):
        super().__init__()

        self.title("Los Manager")
        self.geometry("1400x800")
        self.minsize(1200, 700)
        self.configure(fg_color=tema.COR_CREME_CLARO)

        tema.aplicar_estilo_tabela()

        _ = banco

        self.fazer_backup_inicial()

        self.definir_icone()

        self.criar_interface()

        # Só depois da janela estar montada e do loop de eventos rodando —
        # e com uma folga de 2s. Consultar o GitHub no meio da inicialização
        # dava atualização que nunca aparecia: num PC recém-ligado a rede
        # ainda não subiu nesses primeiros segundos, a consulta falhava e o
        # erro é engolido de propósito, sem segunda chance. Foi o que
        # aconteceu na loja.
        self.after(2000, self.verificar_atualizacao)

    # ==================================================

    def definir_icone(self):

        try:
            caminho_icone = config.caminho_asset("icone.ico")
            self.iconbitmap(caminho_icone)
        except Exception as e:
            print(f"[ERRO ICONE] {e}")

    # ==================================================

    def fazer_backup_inicial(self):

        try:
            config.fazer_backup_banco()
        except Exception as e:
            print(f"[ERRO BACKUP] {e}")

    # ==================================================

    def verificar_atualizacao(self):
        """Confere em segundo plano se já tem uma versão mais nova no
        GitHub. Só avisa o usuário se REALMENTE houver uma (fica quieto
        se já estiver atualizado, sem internet, ou rodando via `python
        main.py`) — ver utils/atualizacao.py."""

        atualizacao.verificar_silenciosamente(
            self._notificar_atualizacao,
            self._notificar_repositorio_invalido
        )

    def _notificar_atualizacao(self, versao_atual, versao_nova, url_release, url_download):

        # Chamado de dentro da thread de rede: precisa voltar pra
        # thread principal do Tkinter antes de mexer na interface.
        self.after(0, lambda: self._mostrar_aviso_atualizacao(versao_atual, versao_nova, url_release, url_download))

    def _notificar_repositorio_invalido(self, repositorio):

        self.after(0, lambda: self._mostrar_aviso_repositorio(repositorio))

    def _mostrar_aviso_repositorio(self, repositorio):
        """Repositório errado nas Configurações: diferente de ficar sem
        internet, isso não se resolve sozinho — sem avisar, o programa
        nunca mais oferece atualização e ninguém descobre por quê."""

        # Marca ANTES de mostrar: o aviso é uma vez por valor configurado,
        # senão vira incômodo em toda abertura.
        atualizacao.marcar_aviso_repositorio(repositorio)

        messagebox.showwarning(
            "Atualização automática",
            f"Não consegui consultar o repositório \"{repositorio}\" no GitHub.\n\n"
            "Ele pode estar escrito errado, ser privado ou não ter nenhuma "
            "versão publicada. Confira o campo \"Repositório no GitHub\" em "
            "Configurações — o padrão é "
            f"{atualizacao.REPOSITORIO_PADRAO}.\n\n"
            "Enquanto isso, o programa não vai avisar quando sair uma "
            "versão nova."
        )

    def _mostrar_aviso_atualizacao(self, versao_atual, versao_nova, url_release, url_download):

        # Sem um .zip anexado ao release não tem o que baixar/instalar
        # sozinho — cai pro fluxo antigo de abrir a página no navegador.
        if not url_download:

            abrir = messagebox.askyesno(
                "Atualização disponível",
                f"Você está usando a versão {atualizacao.formatar_versao(versao_atual)}.\n"
                f"A versão {atualizacao.formatar_versao(versao_nova)} já está disponível no GitHub.\n\n"
                "Não foi possível encontrar o arquivo de instalação automática "
                "nesse release. Deseja abrir a página de download agora?"
            )

            if abrir:
                webbrowser.open(url_release)

            return

        atualizar = messagebox.askyesno(
            "Atualização disponível",
            f"Você está usando a versão {atualizacao.formatar_versao(versao_atual)}.\n"
            f"A versão {atualizacao.formatar_versao(versao_nova)} já está disponível.\n\n"
            "Deseja atualizar agora? O programa vai baixar a nova versão, "
            "fechar e abrir de novo sozinho."
        )

        if atualizar:
            autoatualizador.iniciar(self, url_download)

    # ==================================================

    def criar_interface(self):

        self.menu = ctk.CTkFrame(
            self,
            width=250,
            corner_radius=20,
            fg_color=tema.COR_MENU      # ALTERADO
        )

        self.menu.pack(
            side="left",
            fill="y",
            padx=15,
            pady=15
        )

        self.menu.pack_propagate(False)

        self.mostrar_logo_menu()

        self.definicao_botoes = [

            ("dashboard", "🏠 Dashboard", self.abrir_dashboard),
            ("produtos", "🍔 Produtos", self.abrir_produtos),
            ("ingredientes", "🧂 Ingredientes", self.abrir_ingredientes),
            ("clientes", "👥 Clientes", self.abrir_clientes),
            ("pedidos", "🛒 Pedidos", self.abrir_pedidos),
            ("caixa", "💰 Caixa", self.abrir_caixa),
            ("relatorios", "📊 Relatórios", self.abrir_relatorios),
            ("fidelidade", "🎁 Fidelidade", self.abrir_fidelidade),
            ("configuracoes", "⚙ Configurações", self.abrir_configuracoes)

        ]

        self.botoes = {}

        for chave, texto, comando in self.definicao_botoes:

            botao = ctk.CTkButton(
                self.menu,
                text=texto,
                height=52,
                corner_radius=16,
                font=("Segoe UI", 15, "bold"),
                fg_color="transparent",
                hover_color=tema.COR_LARANJA_CLARO,
                text_color=tema.COR_TEXTO,      # ALTERADO
                command=lambda c=comando, k=chave: self.navegar(k, c)
            )

            botao.pack(
                fill="x",
                padx=15,
                pady=6
            )

            self.botoes[chave] = botao

        self.area = ctk.CTkFrame(
            self,
            corner_radius=20,
            fg_color=tema.COR_CREME
        )

        self.area.pack(
            side="right",
            fill="both",
            expand=True,
            padx=(0,15),
            pady=15
        )

        # Sem caixa aberto o sistema começa travado na tela de Caixa —
        # ver `navegar()`.
        if caixa_estado.esta_aberto():
            self.navegar("dashboard", self.abrir_dashboard)
        else:
            self.navegar("caixa", self.abrir_caixa)

    # ==================================================

    def navegar(self, chave, comando):

        # Enquanto não tiver caixa aberto, a única tela liberada é a de
        # Caixa: nada de cadastrar, vender ou consultar relatório com o
        # caixa fechado (o movimento do dia não teria onde entrar).
        if chave != "caixa" and not caixa_estado.esta_aberto():

            messagebox.showwarning(
                "Caixa fechado",
                "Nenhum caixa aberto no momento.\n\n"
                "Abra o caixa para liberar o restante do sistema."
            )

            chave = "caixa"
            comando = self.abrir_caixa

        for k, botao in self.botoes.items():

            if k == chave:
                botao.configure(
                    fg_color=tema.COR_LARANJA,
                    hover_color=tema.COR_LARANJA,
                    text_color=tema.COR_BRANCO
                )
            else:
                botao.configure(
                    fg_color="transparent",
                    text_color=tema.COR_TEXTO     # ALTERADO
                )

        comando()

    # ==================================================

    def mostrar_logo_menu(self):

        caminho_logo = config.caminho_asset("logo_menu.png")

        try:

            imagem_pil = Image.open(caminho_logo)

            largura, altura = imagem_pil.size
            proporcao = altura / largura

            largura_exibida = 170
            altura_exibida = int(largura_exibida * proporcao)

            logo_ctk = ctk.CTkImage(
                light_image=imagem_pil,
                dark_image=imagem_pil,
                size=(largura_exibida, altura_exibida)
            )

            ctk.CTkLabel(
                self.menu,
                image=logo_ctk,
                text=""
            ).pack(pady=(25, 20))

        except Exception:

            ctk.CTkLabel(
                self.menu,
                text="LOS MANAGER",
                font=("Arial", 26, "bold"),
                text_color=tema.COR_TEXTO
            ).pack(pady=(30, 25))

    # ==================================================

    def limpar_area(self):

        for widget in self.area.winfo_children():
            widget.destroy()

    # ==================================================

    def abrir_dashboard(self):

        self.limpar_area()
        Dashboard(self.area)

    # ==================================================

    def abrir_produtos(self):

        self.limpar_area()
        Produtos(self.area)

    # ==================================================

    def abrir_ingredientes(self):

        self.limpar_area()
        Ingredientes(self.area)

    # ==================================================

    def abrir_clientes(self):

        self.limpar_area()
        Clientes(self.area)

    # ==================================================

    def abrir_pedidos(self):

        self.limpar_area()
        Pedidos(self.area)

    # ==================================================

    def abrir_relatorios(self):

        self.limpar_area()
        Relatorios(self.area)

    # ==================================================

    def abrir_caixa(self):

        self.limpar_area()
        Caixa(self.area)

    # ==================================================

    def abrir_fidelidade(self):

        self.limpar_area()
        Fidelidade(self.area)

    # ==================================================

    def abrir_configuracoes(self):

        self.limpar_area()
        Configuracoes(self.area)

    # ==================================================

    def em_desenvolvimento(self):

        self.limpar_area()

        frame = ctk.CTkFrame(self.area)
        frame.pack(expand=True)

        ctk.CTkLabel(
            frame,
            text="🚧",
            font=("Arial", 60)
        ).pack(pady=(30, 10))

        ctk.CTkLabel(
            frame,
            text="Módulo em desenvolvimento",
            font=("Arial", 28, "bold")
        ).pack()

        ctk.CTkLabel(
            frame,
            text="Esta funcionalidade será adicionada nas próximas versões.",
            font=("Arial", 16)
        ).pack(pady=10)


if __name__ == "__main__":
    app = LosManager()
    app.mainloop()