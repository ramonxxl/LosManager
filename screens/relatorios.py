import customtkinter as ctk
from tkinter import ttk, messagebox
from datetime import datetime

from database.conexao import banco
from utils import config
from utils import busca
from utils import calendario
from utils import tema
from utils import responsivo


class Relatorios(ctk.CTkFrame):

    def __init__(self, master):
        super().__init__(master)

        self.pack(fill="both", expand=True, padx=20, pady=20)

        self.todos_pedidos = []

        self.criar_interface()
        self.carregar_pedidos()
        self.aplicar_filtro()

    # ======================================================

    def criar_interface(self):

        self.scroll = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.scroll.pack(fill="both", expand=True)

        titulo = ctk.CTkLabel(
            self.scroll,
            text="Relatórios e Histórico de Pedidos",
            font=("Arial", 28, "bold")
        )
        titulo.pack(pady=(5, 15))

        topo = ctk.CTkFrame(self.scroll)
        topo.pack(fill="x")

        ctk.CTkLabel(topo, text="Período").grid(row=0, column=0, padx=10, pady=15)

        self.periodo = ctk.CTkSegmentedButton(
            topo,
            values=["Hoje", "7 dias", "Este mês", "Tudo"],
            command=self.selecionar_periodo
        )
        self.periodo.set("Hoje")
        self.periodo.grid(row=0, column=1, padx=10)

        ctk.CTkLabel(
            topo, text="🔍 Buscar (cliente ou nº do pedido)"
        ).grid(row=0, column=2, padx=(30, 10))

        self.busca = ctk.CTkEntry(
            topo, width=280, placeholder_text="Ex: João  ou  7"
        )
        self.busca.grid(row=0, column=3, padx=10)
        self.busca.bind("<KeyRelease>", lambda evento: self.aplicar_filtro())

        # ---------------- Filtro por data exata ----------------
        # Linha própria (não cabe junto com o período em telas 1366px)
        # e dentro de um frame, pra as larguras daqui não mexerem nas
        # colunas do grid de cima. Quando há data escolhida, ela manda
        # no filtro; clicar num período volta a valer o período.

        linha_data = ctk.CTkFrame(topo, fg_color="transparent")
        linha_data.grid(row=1, column=0, columnspan=4, sticky="w", padx=10, pady=(0, 12))

        self.data_filtro = None

        ctk.CTkButton(
            linha_data,
            text="📅 Escolher data",
            width=150,
            command=self.abrir_calendario
        ).pack(side="left")

        self.lbl_data_filtro = ctk.CTkLabel(
            linha_data,
            text="Nenhuma data escolhida (usando o período acima)",
            font=("Arial", 13, "italic"),
            text_color="gray"
        )
        self.lbl_data_filtro.pack(side="left", padx=12)

        self.botao_limpar_data = ctk.CTkButton(
            linha_data,
            text="✖ Limpar data",
            width=120,
            fg_color="#777",
            hover_color="#555",
            command=self.limpar_data_filtro
        )
        # Só aparece quando há uma data escolhida (ver atualizar_rotulo_data)

        # ---------------- Cards de resumo ----------------

        self.cards_frame = ctk.CTkFrame(self.scroll, fg_color="transparent")
        self.cards_frame.pack(fill="x", pady=15)

        # Popula com valores zerados só pra existir de verdade (com sua
        # altura real) antes da tabela ser dimensionada logo abaixo —
        # os valores certos vêm de aplicar_filtro() ao final do __init__.
        self.atualizar_cards([])

        # ---------------- Taxa por motoboy no período ----------------
        # Mesmo filtro (período/data/busca) da tabela principal — dá pra
        # ver quanto cada motoboy tem a receber de taxa de entrega.

        bloco_motoboys = ctk.CTkFrame(self.scroll)
        bloco_motoboys.pack(fill="x", pady=(0, 15))

        ctk.CTkLabel(
            bloco_motoboys,
            text="Taxa de Entrega por Motoboy no período",
            font=("Arial", 14, "bold")
        ).pack(anchor="w", padx=15, pady=(10, 6))

        self.tabela_motoboys = ttk.Treeview(
            bloco_motoboys,
            columns=("motoboy", "entregas", "total"),
            show="headings",
            height=4
        )
        self.tabela_motoboys.heading("motoboy", text="Motoboy")
        self.tabela_motoboys.heading("entregas", text="Entregas")
        self.tabela_motoboys.heading("total", text="Taxa total")
        self.tabela_motoboys.column("motoboy", width=260, anchor="w")
        self.tabela_motoboys.column("entregas", width=100, anchor="center")
        self.tabela_motoboys.column("total", width=120, anchor="e")
        self.tabela_motoboys.pack(fill="x", padx=15, pady=(0, 15))

        # ---------------- Ações sobre o pedido selecionado ----------------
        # Criado (e empacotado) antes da tabela só para medir a altura
        # real que ele ocupa; a tabela é inserida visualmente ANTES
        # dele via pack(before=...) logo abaixo.

        acoes_pedido = ctk.CTkFrame(self.scroll, fg_color="transparent")
        acoes_pedido.pack(fill="x", pady=(0, 10))

        botoes_pedido = ctk.CTkFrame(acoes_pedido, fg_color="transparent")
        botoes_pedido.pack(fill="x")

        ctk.CTkButton(
            botoes_pedido,
            text="🔍 Ver Pedido",
            width=140,
            command=self.ver_pedido
        ).pack(side="left", padx=(0, 10))

        ctk.CTkButton(
            botoes_pedido,
            text="🚫 Cancelar Pedido Selecionado",
            fg_color=tema.COR_VERMELHO,
            hover_color="#B93601",
            width=240,
            command=self.cancelar_pedido
        ).pack(side="left")

        ctk.CTkButton(
            botoes_pedido,
            text="↩️ Reverter Cancelamento",
            fg_color="#777",
            hover_color="#555",
            width=200,
            command=self.reverter_cancelamento
        ).pack(side="left", padx=(10, 0))

        # Texto explicativo abaixo dos botões, e com `wraplength`: ao
        # lado deles e sem quebra, ele esticava a linha para ~1900px e
        # ficava cortado em telas 1366x768.
        ctk.CTkLabel(
            acoes_pedido,
            text="Cancelar devolve automaticamente ao estoque os produtos e "
                 "ingredientes usados no pedido. Reverter faz o inverso, caso "
                 "o cancelamento tenha sido por engano. Ambos pedem a senha "
                 "de administrador e o pedido continua no histórico.",
            font=("Arial", 12),
            text_color="gray",
            wraplength=900,
            justify="left"
        ).pack(anchor="w", pady=(8, 0))

        # ---------------- Zona de perigo: zerar relatórios ----------------

        zona_perigo = ctk.CTkFrame(self.scroll, border_width=1, border_color="#a33")
        zona_perigo.pack(fill="x", pady=(15, 15))

        ctk.CTkLabel(
            zona_perigo,
            text="⚠️ Zona de Perigo",
            font=("Arial", 14, "bold"),
            text_color="#a33"
        ).pack(anchor="w", padx=15, pady=(12, 2))

        ctk.CTkLabel(
            zona_perigo,
            text="Apaga pedidos de verdade do banco de dados. Pede a senha "
                 "cadastrada em Configurações e uma confirmação extra.",
            font=("Arial", 12),
            text_color="gray"
        ).pack(anchor="w", padx=15, pady=(0, 10))

        botoes_perigo = ctk.CTkFrame(zona_perigo, fg_color="transparent")
        botoes_perigo.pack(anchor="w", padx=15, pady=(0, 15))

        ctk.CTkButton(
            botoes_perigo,
            text="🗑 Zerar Pedidos de Hoje",
            fg_color="#c80",
            hover_color="#960",
            width=200,
            command=lambda: self.zerar_pedidos(apenas_hoje=True)
        ).pack(side="left", padx=(0, 10))

        ctk.CTkButton(
            botoes_perigo,
            text="🗑 Zerar TODO o Histórico",
            fg_color="#a33",
            hover_color="#822",
            width=200,
            command=lambda: self.zerar_pedidos(apenas_hoje=False)
        ).pack(side="left")

        # ---------------- Tabela ----------------
        # Vem por último na construção (pra já poder medir a altura de
        # tudo que ficou acima E abaixo dela), mas é inserida
        # visualmente antes de "acoes_pedido" via pack(before=...).

        linhas = responsivo.linhas_para_tabela(self, self.scroll, pady_tabela=10)

        self.tabela = ttk.Treeview(
            self.scroll,
            columns=("id", "numero", "data", "hora", "cliente", "total", "pagamento", "status"),
            show="headings",
            height=linhas
        )

        colunas = [
            ("numero", "Nº", 70, "center"),
            ("data", "Data", 90, "center"),
            ("hora", "Hora", 70, "center"),
            ("cliente", "Cliente", 260, "w"),
            ("total", "Total", 100, "e"),
            ("pagamento", "Pagamento", 110, "center"),
            ("status", "Status", 100, "center"),
        ]

        for chave, texto, largura, ancora in colunas:
            self.tabela.heading(chave, text=texto)
            self.tabela.column(chave, width=largura, anchor=ancora)

        # Coluna "id" fica fora de displaycolumns: guarda o id do pedido
        # sem mostrar na tela (é só pra saber o que cancelar depois).
        self.tabela["displaycolumns"] = [chave for chave, *_ in colunas]

        self.tabela.tag_configure("cancelado", foreground="gray")

        self.tabela.pack(fill="x", pady=10, before=acoes_pedido)

        responsivo.tornar_dinamica(self, self.scroll, lambda: self.tabela, pady_tabela=10)

    # ======================================================
    # ZERAR RELATÓRIOS (protegido por senha)
    # ======================================================

    def zerar_pedidos(self, apenas_hoje):

        senha_cadastrada = config.obter("senha_reset").strip()

        if not senha_cadastrada:
            messagebox.showwarning(
                "Segurança",
                "Você ainda não cadastrou uma senha de administrador.\n\n"
                "Vá em Configurações → Segurança e cadastre uma senha antes "
                "de usar esta função."
            )
            return

        janela = ctk.CTkInputDialog(
            text="Digite a senha de administrador:",
            title="Confirmar Senha"
        )
        senha_digitada = janela.get_input()

        if senha_digitada is None:
            return

        if senha_digitada != senha_cadastrada:
            messagebox.showerror("Segurança", "Senha incorreta.")
            return

        escopo = (
            "os pedidos de HOJE" if apenas_hoje
            else "TODO o histórico de pedidos (todos os dias)"
        )

        confirmar = messagebox.askyesno(
            "Confirmação final",
            f"Isso vai apagar {escopo} permanentemente do banco de dados.\n\n"
            "Essa ação NÃO pode ser desfeita. Deseja continuar?"
        )

        if not confirmar:
            return

        if apenas_hoje:

            hoje = datetime.now().strftime("%d/%m/%Y")

            pedidos_do_dia = banco.buscar(
                "SELECT id FROM pedidos WHERE data=?", (hoje,)
            )

            for (pedido_id,) in pedidos_do_dia:
                banco.executar(
                    "DELETE FROM itens_pedido WHERE pedido_id=?", (pedido_id,)
                )
                banco.executar(
                    "DELETE FROM movimentos_ingrediente WHERE pedido_id=?", (pedido_id,)
                )

            banco.executar("DELETE FROM pedidos WHERE data=?", (hoje,))

            mensagem = "Os pedidos de hoje foram zerados."

        else:

            banco.executar("DELETE FROM itens_pedido")
            banco.executar("DELETE FROM movimentos_ingrediente")
            banco.executar("DELETE FROM pedidos")

            mensagem = "Todo o histórico de pedidos foi zerado."

        messagebox.showinfo("Relatórios", mensagem)

        self.carregar_pedidos()
        self.aplicar_filtro()

    # ======================================================
    # VER PEDIDO (o que foi vendido naquele pedido)
    # ======================================================

    def ver_pedido(self):

        selecionado = self.tabela.selection()

        if not selecionado:
            messagebox.showwarning(
                "Relatórios",
                "Selecione um pedido na lista para ver os itens."
            )
            return

        pedido_id = self.tabela.item(selecionado[0], "values")[0]

        JanelaDetalhePedido(self, pedido_id)

    # ======================================================
    # CANCELAR PEDIDO (devolve estoque de produto + ingredientes)
    # ======================================================

    def cancelar_pedido(self):

        selecionado = self.tabela.selection()

        if not selecionado:
            messagebox.showwarning(
                "Relatórios",
                "Selecione um pedido na lista para cancelar."
            )
            return

        valores = self.tabela.item(selecionado[0], "values")
        pedido_id, numero, status_atual = valores[0], valores[1], valores[7]

        if status_atual == "Cancelado":
            messagebox.showinfo("Relatórios", f"O pedido Nº {numero} já está cancelado.")
            return

        senha_cadastrada = config.obter("senha_reset").strip()

        if not senha_cadastrada:
            messagebox.showwarning(
                "Segurança",
                "Você ainda não cadastrou uma senha de administrador.\n\n"
                "Vá em Configurações → Segurança e cadastre uma senha antes "
                "de cancelar pedidos."
            )
            return

        janela_senha = ctk.CTkInputDialog(
            text="Digite a senha de administrador para cancelar o pedido:",
            title="Confirmar Senha"
        )
        senha_digitada = janela_senha.get_input()

        if senha_digitada is None:
            return

        if senha_digitada != senha_cadastrada:
            messagebox.showerror("Segurança", "Senha incorreta.")
            return

        confirmar = messagebox.askyesno(
            "Cancelar Pedido",
            f"Cancelar o pedido Nº {numero}?\n\n"
            "O estoque de produtos e de ingredientes usados nesse pedido "
            "será devolvido automaticamente. O pedido continua no "
            "histórico, só marcado como \"Cancelado\" — essa ação não "
            "apaga nada."
        )

        if not confirmar:
            return

        try:
            self.devolver_estoque_pedido(pedido_id)

            banco.executar_sem_commit(
                "UPDATE pedidos SET status='Cancelado' WHERE id=?", (pedido_id,)
            )

        except Exception as erro:
            banco.rollback()
            messagebox.showerror(
                "Erro ao cancelar pedido",
                f"Não foi possível cancelar o pedido:\n\n{erro}"
            )
            return

        banco.commit()

        messagebox.showinfo(
            "Relatórios",
            f"Pedido Nº {numero} cancelado. Estoque devolvido."
        )

        self.carregar_pedidos()
        self.aplicar_filtro()

    # ======================================================
    # REVERTER CANCELAMENTO (desfaz um cancelamento feito por engano)
    # ======================================================

    def reverter_cancelamento(self):

        selecionado = self.tabela.selection()

        if not selecionado:
            messagebox.showwarning(
                "Relatórios",
                "Selecione um pedido na lista para reverter o cancelamento."
            )
            return

        valores = self.tabela.item(selecionado[0], "values")
        pedido_id, numero, status_atual = valores[0], valores[1], valores[7]

        if status_atual != "Cancelado":
            messagebox.showinfo("Relatórios", f"O pedido Nº {numero} não está cancelado.")
            return

        senha_cadastrada = config.obter("senha_reset").strip()

        if not senha_cadastrada:
            messagebox.showwarning(
                "Segurança",
                "Você ainda não cadastrou uma senha de administrador.\n\n"
                "Vá em Configurações → Segurança e cadastre uma senha antes "
                "de reverter cancelamentos."
            )
            return

        janela_senha = ctk.CTkInputDialog(
            text="Digite a senha de administrador para reverter o cancelamento:",
            title="Confirmar Senha"
        )
        senha_digitada = janela_senha.get_input()

        if senha_digitada is None:
            return

        if senha_digitada != senha_cadastrada:
            messagebox.showerror("Segurança", "Senha incorreta.")
            return

        confirmar = messagebox.askyesno(
            "Reverter Cancelamento",
            f"Reverter o cancelamento do pedido Nº {numero}?\n\n"
            "O pedido volta a valer como \"Finalizado\", contando de novo "
            "no faturamento, e o estoque de produtos e ingredientes usados "
            "nele será descontado outra vez."
        )

        if not confirmar:
            return

        try:
            self.reconsumir_estoque_pedido(pedido_id)

            banco.executar_sem_commit(
                "UPDATE pedidos SET status='Finalizado' WHERE id=?", (pedido_id,)
            )

        except Exception as erro:
            banco.rollback()
            messagebox.showerror(
                "Erro ao reverter cancelamento",
                f"Não foi possível reverter o cancelamento:\n\n{erro}"
            )
            return

        banco.commit()

        messagebox.showinfo(
            "Relatórios",
            f"Cancelamento do pedido Nº {numero} revertido. Estoque descontado novamente."
        )

        self.carregar_pedidos()
        self.aplicar_filtro()

    # ======================================================

    def reconsumir_estoque_pedido(self, pedido_id):
        """Desconta de novo o estoque de produto e ingredientes de um
        pedido que estava cancelado — o inverso exato de
        `devolver_estoque_pedido`, e o mesmo raciocínio de abatimento de
        `Pedidos.gravar_pedido()`. Roda dentro da transação manual de
        `reverter_cancelamento`."""

        agora = datetime.now()
        data_str = agora.strftime("%d/%m/%Y")
        hora_str = agora.strftime("%H:%M")

        itens = banco.buscar(
            "SELECT produto_id, quantidade FROM itens_pedido WHERE pedido_id=?",
            (pedido_id,)
        )

        for produto_id, quantidade in itens:

            banco.executar_sem_commit(
                "UPDATE produtos SET estoque = MAX(0, estoque - ?) WHERE id=?",
                (quantidade, produto_id)
            )

            receita = banco.buscar(
                "SELECT ingrediente_id, quantidade FROM receita_produto WHERE produto_id=?",
                (produto_id,)
            )

            for ingrediente_id, quantidade_unitaria in receita:

                quantidade_total = quantidade_unitaria * quantidade

                banco.executar_sem_commit(
                    "UPDATE ingredientes SET estoque_atual = MAX(0, estoque_atual - ?) WHERE id=?",
                    (quantidade_total, ingrediente_id)
                )

                banco.executar_sem_commit(
                    """
                    INSERT INTO movimentos_ingrediente
                        (ingrediente_id, tipo, quantidade, pedido_id, data, hora)
                    VALUES (?, 'saida', ?, ?, ?, ?)
                    """,
                    (ingrediente_id, quantidade_total, pedido_id, data_str, hora_str)
                )

    # ======================================================

    def devolver_estoque_pedido(self, pedido_id):
        """Devolve ao estoque cada produto vendido no pedido e, se o
        produto tiver receita, também cada ingrediente usado — o
        inverso exato do abatimento feito em `Pedidos.gravar_pedido()`.
        Roda dentro da transação manual de `cancelar_pedido`."""

        agora = datetime.now()
        data_str = agora.strftime("%d/%m/%Y")
        hora_str = agora.strftime("%H:%M")

        itens = banco.buscar(
            "SELECT produto_id, quantidade FROM itens_pedido WHERE pedido_id=?",
            (pedido_id,)
        )

        for produto_id, quantidade in itens:

            banco.executar_sem_commit(
                "UPDATE produtos SET estoque = estoque + ? WHERE id=?",
                (quantidade, produto_id)
            )

            receita = banco.buscar(
                "SELECT ingrediente_id, quantidade FROM receita_produto WHERE produto_id=?",
                (produto_id,)
            )

            for ingrediente_id, quantidade_unitaria in receita:

                quantidade_total = quantidade_unitaria * quantidade

                banco.executar_sem_commit(
                    "UPDATE ingredientes SET estoque_atual = estoque_atual + ? WHERE id=?",
                    (quantidade_total, ingrediente_id)
                )

                banco.executar_sem_commit(
                    """
                    INSERT INTO movimentos_ingrediente
                        (ingrediente_id, tipo, quantidade, pedido_id, data, hora)
                    VALUES (?, 'devolucao', ?, ?, ?, ?)
                    """,
                    (ingrediente_id, quantidade_total, pedido_id, data_str, hora_str)
                )

    # ======================================================

    def carregar_pedidos(self):

        self.todos_pedidos = banco.buscar(
            """
            SELECT p.id, p.numero, p.data, p.hora,
                   COALESCE(c.nome, 'Cliente Balcão'), p.total, p.pagamento, p.status,
                   p.subtotal, p.desconto, p.acrescimo, m.nome
            FROM pedidos p
            LEFT JOIN clientes c ON c.id = p.cliente_id
            LEFT JOIN motoboys m ON m.id = p.motoboy_id
            ORDER BY p.id DESC
            """
        )

    # ======================================================

    def selecionar_periodo(self, valor=None):
        """Clicar num período descarta a data exata — os dois filtros
        são alternativos, não somados."""

        if self.data_filtro is not None:
            self.data_filtro = None
            self.atualizar_rotulo_data()

        self.aplicar_filtro()

    # ======================================================

    def abrir_calendario(self):

        calendario.escolher_data(
            self,
            ao_escolher=self.definir_data_filtro,
            data_inicial=self.data_filtro
        )

    def definir_data_filtro(self, data_texto):

        self.data_filtro = data_texto
        self.atualizar_rotulo_data()
        self.aplicar_filtro()

    def limpar_data_filtro(self):

        self.data_filtro = None
        self.atualizar_rotulo_data()
        self.aplicar_filtro()

    def atualizar_rotulo_data(self):

        if self.data_filtro:
            self.lbl_data_filtro.configure(
                text=f"Mostrando apenas {self.data_filtro}",
                text_color=tema.COR_LARANJA,
                font=("Arial", 13, "bold")
            )
            self.botao_limpar_data.pack(side="left")
        else:
            self.lbl_data_filtro.configure(
                text="Nenhuma data escolhida (usando o período acima)",
                text_color="gray",
                font=("Arial", 13, "italic")
            )
            self.botao_limpar_data.pack_forget()

    # ======================================================

    def aplicar_filtro(self):

        agora = datetime.now()
        periodo = self.periodo.get()
        termo = self.busca.get().strip().lower()

        filtrados = []

        for pedido_id, numero, data, hora, cliente, total, pagamento, status, subtotal, desconto, acrescimo, motoboy in self.todos_pedidos:

            try:
                data_dt = datetime.strptime(data, "%d/%m/%Y")
            except (ValueError, TypeError):
                data_dt = None

            # Data exata escolhida no calendário manda no filtro; sem
            # ela, vale o período selecionado.
            if self.data_filtro:

                if data != self.data_filtro:
                    continue

            else:

                if periodo == "Hoje" and data_dt and data_dt.date() != agora.date():
                    continue

                if periodo == "7 dias" and data_dt and (agora - data_dt).days > 7:
                    continue

                if periodo == "Este mês" and data_dt and (
                    data_dt.month != agora.month or data_dt.year != agora.year
                ):
                    continue

            if termo:
                if not busca.contem(termo, cliente) and termo not in str(numero):
                    continue

            filtrados.append((
                pedido_id, numero, data, hora, cliente, total, pagamento, status,
                subtotal, desconto, acrescimo, motoboy
            ))

        for linha in self.tabela.get_children():
            self.tabela.delete(linha)

        for pedido_id, numero, data, hora, cliente, total, pagamento, status, subtotal, desconto, acrescimo, motoboy in filtrados:

            cancelado = status == "Cancelado"

            self.tabela.insert(
                "", "end",
                values=(
                    pedido_id, f"{numero:04d}", data, hora, cliente,
                    f"R$ {total:.2f}", pagamento, status or "Finalizado"
                ),
                tags=("cancelado",) if cancelado else ()
            )

        # Cards de resumo só contam pedidos não cancelados, senão o
        # faturamento ficaria inflado com vendas que foram desfeitas.
        validos = [p for p in filtrados if p[7] != "Cancelado"]

        self.atualizar_cards(validos)
        self.atualizar_motoboys(validos)

    # ======================================================

    def atualizar_cards(self, filtrados):

        for widget in self.cards_frame.winfo_children():
            widget.destroy()

        # Total pago pelo cliente (produtos + taxa) x venda de produtos x
        # taxa de motoboy, separados pelo mesmo motivo do Caixa: a taxa de
        # entrega só repassa pro motoboy, não é faturamento da pastelaria.
        # Respeita o período selecionado (Hoje / 7 dias / Este mês / Tudo),
        # então dá pra ver o total semanal e mensal de cada um.
        total_geral = sum(p[5] for p in filtrados)
        total_vendas = sum((p[8] or 0.0) - (p[9] or 0.0) for p in filtrados)
        total_motoboy = sum(p[10] or 0.0 for p in filtrados)
        quantidade = len(filtrados)
        ticket_medio = total_geral / quantidade if quantidade else 0.0

        self.card(self.cards_frame, "Pedidos no período", str(quantidade), 0)
        self.card(self.cards_frame, "Vendas no período", f"R$ {total_vendas:.2f}", 1)
        self.card(self.cards_frame, "Taxa Motoboy no período", f"R$ {total_motoboy:.2f}", 2)
        self.card(self.cards_frame, "Ticket Médio", f"R$ {ticket_medio:.2f}", 3)

    # ======================================================

    def atualizar_motoboys(self, filtrados):
        """Agrupa a taxa de entrega (acréscimo) por motoboy, dentro do
        mesmo filtro de período/data/busca já aplicado à tabela
        principal. Pedido com taxa mas sem motoboy escolhido entra
        como "Sem motoboy", pra não esconder taxa não atribuída;
        pedido sem taxa e sem motoboy (balcão, sem entrega) não entra
        na tabela — não tem nada pra separar ali."""

        for linha in self.tabela_motoboys.get_children():
            self.tabela_motoboys.delete(linha)

        totais = {}
        contagem = {}

        for pedido in filtrados:

            acrescimo = pedido[10] or 0.0
            motoboy = pedido[11]

            if not motoboy and acrescimo <= 0:
                continue

            nome = motoboy or "Sem motoboy"

            totais[nome] = totais.get(nome, 0.0) + acrescimo
            contagem[nome] = contagem.get(nome, 0) + 1

        for nome in sorted(totais):
            self.tabela_motoboys.insert(
                "", "end",
                values=(nome, contagem[nome], f"R$ {totais[nome]:.2f}")
            )

    # ======================================================

    def card(self, master, titulo, valor, coluna):

        c = ctk.CTkFrame(master)
        c.grid(row=0, column=coluna, padx=10, sticky="nsew")
        master.grid_columnconfigure(coluna, weight=1)

        ctk.CTkLabel(c, text=titulo, font=("Arial", 14)).pack(pady=(15, 5))
        ctk.CTkLabel(c, text=valor, font=("Arial", 22, "bold")).pack(pady=(0, 15))


# ==========================================================
# JANELA: DETALHE DO PEDIDO (o que foi vendido)
# ==========================================================


class JanelaDetalhePedido(ctk.CTkToplevel):

    def __init__(self, master, pedido_id):
        super().__init__(master.winfo_toplevel())

        self.pedido_id = pedido_id

        self.title("Detalhe do Pedido")
        self.transient(master.winfo_toplevel())

        self.montar_conteudo()

        # Tamanho aplicado só depois que o Tk roda os `after` internos
        # do CustomTkinter — direto no __init__ a janela abre minúscula.
        self.after(60, self._ajustar_tamanho)

        self.grab_set()

    # ======================================================

    def _ajustar_tamanho(self):

        self.update_idletasks()

        largura = min(max(self.winfo_reqwidth(), 620), max(int(self.winfo_screenwidth() * 0.9), 620))
        altura = min(max(self.winfo_reqheight(), 460), max(int(self.winfo_screenheight() * 0.85), 460))

        self.geometry(f"{largura}x{altura}")
        self.minsize(620, 460)

    # ======================================================

    def montar_conteudo(self):

        pedido = banco.buscar_um(
            """
            SELECT p.numero, p.data, p.hora, COALESCE(c.nome, 'Cliente Balcão'),
                   p.subtotal, p.desconto, p.acrescimo, p.total,
                   p.pagamento, p.status
            FROM pedidos p
            LEFT JOIN clientes c ON c.id = p.cliente_id
            WHERE p.id = ?
            """,
            (self.pedido_id,)
        )

        if pedido is None:
            ctk.CTkLabel(
                self,
                text="Pedido não encontrado.",
                font=("Arial", 15)
            ).pack(padx=30, pady=30)
            return

        (numero, data, hora, cliente, subtotal, desconto,
         acrescimo, total, pagamento, status) = pedido

        scroll = ctk.CTkScrollableFrame(self, fg_color="transparent")
        scroll.pack(fill="both", expand=True, padx=15, pady=15)

        # ---------------- Cabeçalho ----------------

        ctk.CTkLabel(
            scroll,
            text=f"Pedido Nº {int(numero):04d}",
            font=("Arial", 22, "bold")
        ).pack(anchor="w")

        if status == "Cancelado":
            ctk.CTkLabel(
                scroll,
                text="🚫 PEDIDO CANCELADO",
                font=("Arial", 14, "bold"),
                text_color=tema.COR_VERMELHO
            ).pack(anchor="w", pady=(4, 0))

        ctk.CTkLabel(
            scroll,
            text=f"{data} às {hora}  •  Cliente: {cliente}  •  Pagamento: {pagamento}",
            font=("Arial", 13),
            text_color="gray"
        ).pack(anchor="w", pady=(4, 12))

        # ---------------- Itens ----------------

        itens = banco.buscar(
            """
            SELECT COALESCE(pr.nome, 'Produto removido'), i.quantidade,
                   i.valor_unitario, i.subtotal, i.observacao
            FROM itens_pedido i
            LEFT JOIN produtos pr ON pr.id = i.produto_id
            WHERE i.pedido_id = ?
            ORDER BY i.id
            """,
            (self.pedido_id,)
        )

        tabela = ttk.Treeview(
            scroll,
            columns=("produto", "observacao", "qtd", "valor", "subtotal"),
            show="headings",
            height=max(len(itens), 3)
        )

        for chave, texto, largura, ancora in [
            ("produto", "Produto", 240, "w"),
            ("observacao", "Observação", 190, "w"),
            ("qtd", "Qtd", 60, "center"),
            ("valor", "Valor", 90, "e"),
            ("subtotal", "Subtotal", 90, "e"),
        ]:
            tabela.heading(chave, text=texto)
            tabela.column(chave, width=largura, anchor=ancora)

        for nome, qtd, valor_unitario, item_subtotal, observacao in itens:
            tabela.insert(
                "", "end",
                values=(
                    nome,
                    observacao or "",
                    qtd,
                    f"R$ {valor_unitario:.2f}",
                    f"R$ {item_subtotal:.2f}"
                )
            )

        tabela.pack(fill="x", pady=(0, 12))

        if not itens:
            ctk.CTkLabel(
                scroll,
                text="Este pedido não tem itens registrados.",
                text_color="gray"
            ).pack(anchor="w", pady=(0, 12))

        # ---------------- Totais ----------------

        totais = ctk.CTkFrame(scroll)
        totais.pack(fill="x")

        def linha_total(rotulo, valor, negrito=False):
            fonte = ("Arial", 15, "bold") if negrito else ("Arial", 13)
            linha = ctk.CTkFrame(totais, fg_color="transparent")
            linha.pack(fill="x", padx=15, pady=3)
            ctk.CTkLabel(linha, text=rotulo, font=fonte).pack(side="left")
            ctk.CTkLabel(linha, text=valor, font=fonte).pack(side="right")

        ctk.CTkLabel(totais, text="").pack(pady=2)
        linha_total("Vendas (produtos)", f"R$ {(subtotal or 0.0) - (desconto or 0.0):.2f}")

        if acrescimo:
            linha_total("Taxa motoboy", f"R$ {acrescimo:.2f}")

        linha_total("TOTAL", f"R$ {total:.2f}", negrito=True)
        ctk.CTkLabel(totais, text="").pack(pady=2)

        ctk.CTkButton(
            scroll,
            text="Fechar",
            width=120,
            command=self.destroy
        ).pack(anchor="e", pady=(12, 0))
