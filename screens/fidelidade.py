import customtkinter as ctk
from tkinter import ttk, messagebox

from database.conexao import banco
from utils import config
from utils import tema
from utils import responsivo
from repositorios import fidelidade as repositorio_fidelidade


TIPOS_LEGIVEIS = {
    repositorio_fidelidade.TIPO_PEDIDO_CONCLUIDO: "Pedido concluído",
    repositorio_fidelidade.TIPO_RECOMPENSA_GERADA: "Recompensa gerada",
    repositorio_fidelidade.TIPO_RECOMPENSA_RESGATADA: "Recompensa resgatada",
    repositorio_fidelidade.TIPO_AJUSTE_MANUAL: "Ajuste manual",
}


class Fidelidade(ctk.CTkFrame):

    def __init__(self, master):
        super().__init__(master)

        self.pack(fill="both", expand=True, padx=20, pady=20)

        self.criar_interface()
        self.carregar()

    # ======================================================

    def criar_interface(self):

        self.scroll = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.scroll.pack(fill="both", expand=True)

        titulo = ctk.CTkLabel(
            self.scroll,
            text="🎁 Programa de Fidelidade",
            font=("Arial", 28, "bold")
        )
        titulo.pack(pady=(5, 15))

        topo = ctk.CTkFrame(self.scroll)
        topo.pack(fill="x")

        ctk.CTkLabel(
            topo, text="🔍 Buscar (nome ou telefone)"
        ).pack(side="left", padx=(15, 10), pady=15)

        self.busca = ctk.CTkEntry(topo, width=280, placeholder_text="Ex: João")
        self.busca.pack(side="left", pady=15)
        self.busca.bind("<KeyRelease>", lambda evento: self.carregar())

        meta = config.obter_meta_fidelidade()
        ctk.CTkLabel(
            topo,
            text=f"A cada {meta} pedidos concluídos, o cliente ganha 1 recompensa.",
            font=("Arial", 12),
            text_color="gray",
            wraplength=380,
            justify="left"
        ).pack(side="left", padx=(30, 15))

        # ---------------- Ações (antes da tabela, pra medir altura) ----------------
        # Criado (e empacotado) antes da tabela só para medir a altura
        # real que ocupa; a tabela é inserida visualmente ANTES dele
        # via pack(before=...) logo abaixo — mesmo padrão de
        # screens/relatorios.py.

        acoes = ctk.CTkFrame(self.scroll, fg_color="transparent")
        acoes.pack(fill="x", pady=(10, 0))

        botoes = ctk.CTkFrame(acoes, fg_color="transparent")
        botoes.pack(fill="x")

        ctk.CTkButton(
            botoes,
            text="🔍 Ver Histórico",
            width=160,
            command=self.ver_historico
        ).pack(side="left", padx=(0, 10))

        ctk.CTkButton(
            botoes,
            text="🎁 Resgatar Recompensa",
            width=200,
            fg_color=tema.COR_LARANJA,
            hover_color=tema.COR_LARANJA_ESCURO,
            command=self.resgatar
        ).pack(side="left", padx=(0, 10))

        ctk.CTkButton(
            botoes,
            text="✏️ Ajustar Pontuação",
            width=180,
            fg_color="#777",
            hover_color="#555",
            command=self.ajustar
        ).pack(side="left")

        ctk.CTkLabel(
            acoes,
            text="Resgatar e Ajustar Pontuação exigem a senha de administrador "
                 "cadastrada em Configurações → Segurança.",
            font=("Arial", 12),
            text_color="gray",
            wraplength=900,
            justify="left"
        ).pack(anchor="w", pady=(8, 10))

        # ---------------- Tabela ----------------

        linhas = responsivo.linhas_para_tabela(self, self.scroll, pady_tabela=10)

        self.tabela = ttk.Treeview(
            self.scroll,
            columns=("cliente_id", "cliente", "telefone", "pedidos", "faltam", "recompensas", "status"),
            show="headings",
            height=linhas
        )

        colunas = [
            ("cliente", "Cliente", 220, "w"),
            ("telefone", "Telefone", 130, "center"),
            ("pedidos", "Total de Pedidos", 120, "center"),
            ("faltam", "Faltam p/ Próxima", 130, "center"),
            ("recompensas", "Recompensas", 110, "center"),
            ("status", "Status", 200, "w"),
        ]

        for chave, texto, largura, ancora in colunas:
            self.tabela.heading(chave, text=texto)
            self.tabela.column(chave, width=largura, anchor=ancora)

        # "cliente_id" fica fora de displaycolumns: guarda o id do
        # cliente sem mostrar na tela (é só pra saber quem resgatar/ajustar).
        self.tabela["displaycolumns"] = [chave for chave, *_ in colunas]

        self.tabela.pack(fill="both", expand=True, pady=10, before=acoes)

        responsivo.tornar_dinamica(self, self.scroll, lambda: self.tabela, pady_tabela=10)

    # ======================================================

    def carregar(self):

        termo = self.busca.get().strip()
        participantes = repositorio_fidelidade.listar_participantes(termo)

        for linha in self.tabela.get_children():
            self.tabela.delete(linha)

        for cliente_id, nome, telefone, total_pedidos, faltam, recompensas, status in participantes:
            self.tabela.insert(
                "", "end",
                values=(cliente_id, nome, telefone, total_pedidos, faltam, recompensas, status)
            )

    # ======================================================

    def _cliente_selecionado(self):

        selecionado = self.tabela.selection()

        if not selecionado:
            messagebox.showwarning("Fidelidade", "Selecione um cliente na lista.")
            return None

        valores = self.tabela.item(selecionado[0], "values")

        return {"id": int(valores[0]), "nome": valores[1]}

    # ======================================================

    def _confirmar_senha(self, titulo_acao):

        senha_cadastrada = config.obter("senha_reset").strip()

        if not senha_cadastrada:
            messagebox.showwarning(
                "Segurança",
                "Você ainda não cadastrou uma senha de administrador.\n\n"
                "Vá em Configurações → Segurança e cadastre uma senha antes "
                f"de {titulo_acao}."
            )
            return False

        janela = ctk.CTkInputDialog(
            text=f"Digite a senha de administrador para {titulo_acao}:",
            title="Confirmar Senha"
        )
        senha_digitada = janela.get_input()

        if senha_digitada is None:
            return False

        if senha_digitada != senha_cadastrada:
            messagebox.showerror("Segurança", "Senha incorreta.")
            return False

        return True

    # ======================================================
    # VER HISTÓRICO
    # ======================================================

    def ver_historico(self):

        cliente = self._cliente_selecionado()

        if cliente is None:
            return

        JanelaHistoricoFidelidade(self, cliente["id"], cliente["nome"])

    # ======================================================
    # RESGATAR RECOMPENSA
    # ======================================================

    def resgatar(self):

        cliente = self._cliente_selecionado()

        if cliente is None:
            return

        if not self._confirmar_senha("resgatar a recompensa"):
            return

        janela_usuario = ctk.CTkInputDialog(
            text="Nome de quem está autorizando o resgate:",
            title="Resgatar Recompensa"
        )
        usuario = janela_usuario.get_input()

        if usuario is None:
            return

        try:
            repositorio_fidelidade.resgatar_recompensa(cliente["id"], usuario=usuario, banco=banco)
        except repositorio_fidelidade.FidelidadeInvalida as erro:
            banco.rollback()
            messagebox.showwarning("Fidelidade", str(erro))
            return

        banco.commit()

        messagebox.showinfo("Fidelidade", f"Recompensa resgatada para {cliente['nome']}.")
        self.carregar()

    # ======================================================
    # AJUSTAR PONTUAÇÃO
    # ======================================================

    def ajustar(self):

        cliente = self._cliente_selecionado()

        if cliente is None:
            return

        if not self._confirmar_senha("ajustar a pontuação"):
            return

        JanelaAjusteFidelidade(self, cliente["id"], cliente["nome"], self.carregar)


# ==========================================================
# HISTÓRICO DE FIDELIDADE DE 1 CLIENTE (só leitura)
# ==========================================================

class JanelaHistoricoFidelidade(ctk.CTkToplevel):

    def __init__(self, master, cliente_id, nome_cliente):
        super().__init__(master.winfo_toplevel())

        self.cliente_id = cliente_id
        self.nome_cliente = nome_cliente

        self.title("Histórico de Fidelidade")
        self.transient(master.winfo_toplevel())

        self.montar_conteudo()

        # Tamanho aplicado só depois que o Tk roda os `after` internos
        # do CustomTkinter — direto no __init__ a janela abre minúscula.
        self.after(60, self._ajustar_tamanho)

        self.grab_set()

    # ======================================================

    def _ajustar_tamanho(self):

        self.update_idletasks()

        largura = min(max(self.winfo_reqwidth(), 700), max(int(self.winfo_screenwidth() * 0.9), 700))
        altura = min(max(self.winfo_reqheight(), 480), max(int(self.winfo_screenheight() * 0.85), 480))

        self.geometry(f"{largura}x{altura}")
        self.minsize(700, 480)

    # ======================================================

    def montar_conteudo(self):

        status = repositorio_fidelidade.obter_status_cliente(self.cliente_id)

        scroll = ctk.CTkScrollableFrame(self, fg_color="transparent")
        scroll.pack(fill="both", expand=True, padx=15, pady=15)

        ctk.CTkLabel(
            scroll,
            text=f"Cliente: {self.nome_cliente}",
            font=("Arial", 20, "bold")
        ).pack(anchor="w")

        ctk.CTkLabel(
            scroll,
            text=f"Total de pedidos: {status['total_pedidos']}  •  "
                 f"Recompensas disponíveis: {status['recompensas_disponiveis']}  •  "
                 f"Faltam {status['faltam']} para a próxima",
            font=("Arial", 13),
            text_color="gray"
        ).pack(anchor="w", pady=(4, 12))

        linhas = repositorio_fidelidade.historico_cliente(self.cliente_id)

        tabela = ttk.Treeview(
            scroll,
            columns=("data", "pedido", "tipo", "quantidade", "observacao", "usuario"),
            show="headings",
            height=max(len(linhas), 6)
        )

        for chave, texto, largura, ancora in [
            ("data", "Data/Hora", 130, "center"),
            ("pedido", "Pedido", 80, "center"),
            ("tipo", "Movimentação", 190, "w"),
            ("quantidade", "Quantidade", 110, "center"),
            ("observacao", "Observação", 230, "w"),
            ("usuario", "Usuário", 120, "w"),
        ]:
            tabela.heading(chave, text=texto)
            tabela.column(chave, width=largura, anchor=ancora)

        for tipo, alvo, quantidade, pedido_id, numero, data, hora, observacao, usuario, estornado in linhas:

            pedido_texto = f"#{int(numero):04d}" if numero else "-"

            tipo_texto = TIPOS_LEGIVEIS.get(tipo, tipo)
            if estornado:
                tipo_texto += " (estornado)"

            sinal = "+" if quantidade >= 0 else ""
            quantidade_texto = f"{sinal}{quantidade} {alvo}"

            tabela.insert(
                "", "end",
                values=(f"{data} {hora}", pedido_texto, tipo_texto, quantidade_texto, observacao or "", usuario or "")
            )

        tabela.pack(fill="both", expand=True, pady=(0, 12))

        if not linhas:
            ctk.CTkLabel(
                scroll,
                text="Este cliente ainda não tem nenhuma movimentação de fidelidade.",
                text_color="gray"
            ).pack(anchor="w", pady=(0, 12))

        ctk.CTkButton(
            scroll,
            text="Fechar",
            width=120,
            command=self.destroy
        ).pack(anchor="e", pady=(12, 0))


# ==========================================================
# AJUSTE MANUAL DE PONTUAÇÃO/RECOMPENSA
# ==========================================================

class JanelaAjusteFidelidade(ctk.CTkToplevel):

    def __init__(self, master, cliente_id, nome_cliente, ao_salvar):
        super().__init__(master.winfo_toplevel())

        self.cliente_id = cliente_id
        self.ao_salvar = ao_salvar

        self.title("Ajustar Pontuação")
        self.transient(master.winfo_toplevel())

        self.montar_conteudo(nome_cliente)

        # Tamanho aplicado só depois que o Tk roda os `after` internos
        # do CustomTkinter — direto no __init__ a janela abre minúscula.
        self.after(60, self._ajustar_tamanho)

        self.grab_set()

    # ======================================================

    def _ajustar_tamanho(self):

        self.update_idletasks()

        largura = min(max(self.winfo_reqwidth(), 440), max(int(self.winfo_screenwidth() * 0.9), 440))
        altura = min(max(self.winfo_reqheight(), 440), max(int(self.winfo_screenheight() * 0.85), 440))

        self.geometry(f"{largura}x{altura}")
        self.minsize(440, 440)

    # ======================================================

    def montar_conteudo(self, nome_cliente):

        ctk.CTkLabel(
            self,
            text=f"Ajuste manual — {nome_cliente}",
            font=("Arial", 18, "bold")
        ).pack(padx=20, pady=(20, 5), anchor="w")

        ctk.CTkLabel(
            self,
            text="Use quando o cliente apresentar um cartão fidelidade físico, "
                 "ou pra corrigir um pedido que não entrou certo.",
            font=("Arial", 12),
            text_color="gray",
            wraplength=380,
            justify="left"
        ).pack(padx=20, anchor="w")

        ctk.CTkLabel(self, text="O que este ajuste altera?").pack(padx=20, anchor="w", pady=(15, 4))

        self.alvo = ctk.CTkSegmentedButton(self, values=["Pedidos", "Recompensas"])
        self.alvo.set("Pedidos")
        self.alvo.pack(padx=20, anchor="w")

        ctk.CTkLabel(
            self, text="Quantidade (negativo remove, ex: -1)"
        ).pack(padx=20, anchor="w", pady=(15, 4))

        self.quantidade = ctk.CTkEntry(self, width=120, placeholder_text="1")
        self.quantidade.pack(padx=20, anchor="w")

        ctk.CTkLabel(self, text="Justificativa (obrigatória)").pack(padx=20, anchor="w", pady=(15, 4))

        self.justificativa = ctk.CTkEntry(
            self, width=380,
            placeholder_text="Ex: cliente apresentou cartão fidelidade físico"
        )
        self.justificativa.pack(padx=20, anchor="w")

        ctk.CTkLabel(self, text="Quem está autorizando (obrigatório)").pack(padx=20, anchor="w", pady=(15, 4))

        self.usuario = ctk.CTkEntry(self, width=250)
        self.usuario.pack(padx=20, anchor="w")

        botoes = ctk.CTkFrame(self, fg_color="transparent")
        botoes.pack(pady=(20, 20))

        ctk.CTkButton(
            botoes, text="Salvar", width=120,
            fg_color="#2a7", hover_color="#186",
            command=self.salvar
        ).pack(side="left", padx=(0, 10))

        ctk.CTkButton(
            botoes, text="Cancelar", width=120,
            fg_color="#777", hover_color="#555",
            command=self.destroy
        ).pack(side="left")

    # ======================================================

    def salvar(self):

        alvo = (
            repositorio_fidelidade.ALVO_PEDIDOS if self.alvo.get() == "Pedidos"
            else repositorio_fidelidade.ALVO_RECOMPENSAS
        )

        try:
            repositorio_fidelidade.ajuste_manual(
                self.cliente_id, alvo, self.quantidade.get(),
                self.justificativa.get(), self.usuario.get(),
                banco=banco
            )
        except repositorio_fidelidade.FidelidadeInvalida as erro:
            banco.rollback()
            messagebox.showwarning("Fidelidade", str(erro))
            return

        banco.commit()

        self.destroy()
        messagebox.showinfo("Fidelidade", "Ajuste registrado com sucesso.")
        self.ao_salvar()
