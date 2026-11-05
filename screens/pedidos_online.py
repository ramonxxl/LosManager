"""
=================================================================
PEDIDOS DO CARDÁPIO ONLINE — janela aberta pela tela de Pedidos
=================================================================
Lista os pedidos feitos no cardápio online (hoje/ontem e os em
andamento), mostra o detalhe do selecionado e, em "Lançar no
carrinho", monta o rascunho (repositorios/pedidos_online.py) e
entrega para a tela de Pedidos, que segue o fluxo normal de
finalizar (motoboy, cupom, estoque, caixa e fidelidade).

Situação do pedido: os mesmos botões do painel do cardápio
(Aceitar, Saiu para entrega / Pronto para retirar, Entregue). O
toque grava no cardápio — vale no painel, aqui e no "Meus pedidos"
do cliente — e oferece a mensagem pronta no WhatsApp do cliente.
Mudou no painel? A lista daqui acompanha a cada consulta (20 s).

A consulta ao site roda numa thread separada (internet lenta não
pode travar o caixa) — ver cardapio_online.buscar_em_segundo_plano.
=================================================================
"""

import webbrowser
from datetime import datetime

import customtkinter as ctk
from tkinter import ttk, messagebox

from database.conexao import banco
from utils import cardapio_online
from repositorios import pedidos_online as repositorio_pedidos_online

STATUS = {
    "novo": "Novo", "preparo": "Em preparo", "pronto": "Pronto p/ retirar",
    "entrega": "Saiu p/ entrega", "concluido": "Concluído", "cancelado": "Cancelado",
}
PAGAMENTO = {"pix": "PIX", "dinheiro": "Dinheiro", "credito": "Crédito", "debito": "Débito", "vr": "Vale-refeição"}


def _hora(iso):
    try:
        return datetime.fromisoformat(iso.replace("Z", "+00:00")).astimezone().strftime("%d/%m %H:%M")
    except Exception:
        return ""


def _reais(centavos):
    return f"R$ {(centavos or 0) / 100:.2f}".replace(".", ",")


class JanelaPedidosOnline(ctk.CTkToplevel):

    def __init__(self, master, ao_lancar):
        super().__init__(master.winfo_toplevel())

        self.ao_lancar = ao_lancar
        self.pedidos = []
        self._mudando = False   # esperando o cardápio confirmar uma mudança de situação

        self.title("Pedidos do cardápio online")
        self.transient(master.winfo_toplevel())

        self.montar_conteudo()

        # Mesmo motivo das outras janelas: tamanho só depois dos after()
        # internos do CustomTkinter, senão abre minúscula.
        self.after(60, self._ajustar_tamanho)

        self.grab_set()

        self.mostrar(cardapio_online.ultimo_resultado()["pedidos"])
        self.atualizar()

        # a consulta automática do main.py (a cada 20 s) também atualiza esta lista
        cardapio_online.registrar_ouvinte(self._ao_publicar)

    def _ao_publicar(self):
        if self.winfo_exists() and not self._mudando:
            self.mostrar(cardapio_online.ultimo_resultado()["pedidos"])

    def destroy(self):
        cardapio_online.remover_ouvinte(self._ao_publicar)
        super().destroy()

    # ======================================================

    def _ajustar_tamanho(self):

        self.update_idletasks()

        largura = min(max(self.winfo_reqwidth(), 900), max(int(self.winfo_screenwidth() * 0.92), 600))
        altura = min(max(self.winfo_reqheight(), 560), max(int(self.winfo_screenheight() * 0.86), 420))

        self.geometry(f"{largura}x{altura}")
        self.minsize(600, 420)

    # ======================================================

    def montar_conteudo(self):

        topo = ctk.CTkFrame(self, fg_color="transparent")
        topo.pack(fill="x", padx=16, pady=(14, 4))

        ctk.CTkLabel(
            topo,
            text="🌐 Pedidos do cardápio online",
            font=("Arial", 18, "bold")
        ).pack(side="left")

        ctk.CTkButton(topo, text="🔄 Atualizar", width=110, command=self.atualizar).pack(side="right")

        self.lbl_status = ctk.CTkLabel(self, text="", font=("Arial", 12), text_color="gray")
        self.lbl_status.pack(anchor="w", padx=16)

        corpo = ctk.CTkFrame(self, fg_color="transparent")
        corpo.pack(fill="both", expand=True, padx=16, pady=8)

        self.tabela = ttk.Treeview(
            corpo,
            columns=("numero", "hora", "cliente", "tipo", "total", "situacao"),
            show="headings",
            height=12
        )
        for coluna, titulo, largura, ancora in (
            ("numero", "#", 50, "center"), ("hora", "Hora", 90, "center"), ("cliente", "Cliente", 170, "w"),
            ("tipo", "Entrega", 80, "center"), ("total", "Total", 85, "e"), ("situacao", "Situação", 200, "w"),
        ):
            self.tabela.heading(coluna, text=titulo)
            self.tabela.column(coluna, width=largura, anchor=ancora)

        self.tabela.tag_configure("pendente", background="#FFE3B8")
        self.tabela.tag_configure("lancado", foreground="gray")
        self.tabela.bind("<<TreeviewSelect>>", self.mostrar_detalhe)
        self.tabela.bind("<Double-1>", lambda e: self.lancar())
        self.tabela.pack(side="left", fill="both", expand=True)

        lado = ctk.CTkFrame(corpo, fg_color="transparent")
        lado.pack(side="left", fill="both", padx=(10, 0))

        self.detalhe = ctk.CTkTextbox(lado, width=330, font=("Consolas", 12), wrap="word")
        self.detalhe.pack(fill="both", expand=True)
        self.detalhe.configure(state="disabled")

        # botões de situação + WhatsApp do pedido selecionado (desenhar_acoes)
        self.acoes = ctk.CTkFrame(lado, fg_color="transparent")
        self.acoes.pack(fill="x", pady=(8, 0))

        rodape = ctk.CTkFrame(self, fg_color="transparent")
        rodape.pack(fill="x", padx=16, pady=(0, 14))

        ctk.CTkLabel(
            rodape,
            text="Em laranja: ainda não lançados. Dois cliques ou o botão ao lado põem o pedido no carrinho.",
            font=("Arial", 11),
            text_color="gray",
            wraplength=520,
            justify="left"
        ).pack(side="left")

        ctk.CTkButton(rodape, text="Fechar", width=90, fg_color="gray40", command=self.destroy).pack(side="right")

        self.btn_lancar = ctk.CTkButton(
            rodape,
            text="🛒 Lançar no carrinho",
            width=180,
            font=("Arial", 14, "bold"),
            command=self.lancar
        )
        self.btn_lancar.pack(side="right", padx=8)

    # ======================================================

    def atualizar(self):

        self.lbl_status.configure(text="Consultando o cardápio online...")

        cardapio_online.buscar_em_segundo_plano(self, self._ao_receber)

    def _ao_receber(self, pedidos, erro):

        if not self.winfo_exists():
            return

        cardapio_online.publicar(pedidos, erro)

        if erro:
            self.lbl_status.configure(text=f"⚠ {erro}", text_color="#c2371f")
            return

        self.lbl_status.configure(text=f"Atualizado às {datetime.now():%H:%M:%S}", text_color="gray")
        self.mostrar(pedidos)

    # ======================================================

    def mostrar(self, pedidos):

        selecionado = self.tabela.selection()
        self.pedidos = pedidos or []

        lancados = dict(banco.buscar(
            "SELECT pedido_online_id, numero FROM pedidos WHERE pedido_online_id IS NOT NULL AND status != 'Cancelado'"
        ))

        for linha in self.tabela.get_children():
            self.tabela.delete(linha)

        # pendentes primeiro, depois os mais recentes
        ordenados = sorted(
            self.pedidos,
            key=lambda p: (bool(p.get("importadoEm") or p["id"] in lancados or p.get("status") not in cardapio_online.STATUS_EM_ABERTO), -p["id"])
        )

        for p in ordenados:

            numero_local = lancados.get(p["id"])

            etapa = STATUS.get(p.get("status"), p.get("status"))

            if numero_local:
                situacao, tag = f"✓ Nº {numero_local:04d} · {etapa}", "lancado"
            elif p.get("importadoEm"):
                situacao, tag = f"✓ Nº {p.get('importadoNumero') or '?'} · {etapa}", "lancado"
            elif p.get("status") in cardapio_online.STATUS_EM_ABERTO:
                # ainda não lançado no caixa; se a situação já andou (mudada aqui ou no painel), mostra qual
                situacao = "⏳ Aguardando" if p.get("status") == "novo" else f"⏳ Não lançado · {etapa}"
                tag = "pendente"
            else:
                situacao, tag = STATUS.get(p.get("status"), p.get("status")), "lancado"

            self.tabela.insert(
                "", "end", iid=str(p["id"]), tags=(tag,),
                values=(
                    p["id"], _hora(p.get("criadoEm", "")), (p.get("cliente") or {}).get("nome", ""),
                    "Entrega" if (p.get("entrega") or {}).get("tipo") == "entrega" else "Retirada",
                    _reais(p.get("total")), situacao,
                )
            )

        if selecionado and self.tabela.exists(selecionado[0]):
            self.tabela.selection_set(selecionado[0])
        elif self.tabela.get_children():
            self.tabela.selection_set(self.tabela.get_children()[0])

        if not self.pedidos:
            self._escrever_detalhe("Nenhum pedido do cardápio online hoje.")
            self.desenhar_acoes(None)

    # ======================================================

    def _pedido_selecionado(self):

        selecionado = self.tabela.selection()

        if not selecionado:
            return None

        return next((p for p in self.pedidos if str(p["id"]) == selecionado[0]), None)

    def _escrever_detalhe(self, texto):

        self.detalhe.configure(state="normal")
        self.detalhe.delete("1.0", "end")
        self.detalhe.insert("1.0", texto)
        self.detalhe.configure(state="disabled")

    def mostrar_detalhe(self, evento=None):

        p = self._pedido_selecionado()

        if not p:
            return

        linhas = [f"PEDIDO ONLINE #{p['id']}  —  {STATUS.get(p.get('status'), '')}", ""]

        for item in p.get("itens") or []:
            linhas.append(f"{item['qtd']}x {item['nome']}  {_reais(item.get('total'))}")
            for e in item.get("escolhas") or []:
                linhas.append(f"   + {str(e['n']) + 'x ' if e.get('n', 1) > 1 else ''}{e['nome']}")
            if item.get("obs"):
                linhas.append(f"   Obs: {item['obs']}")

        linhas += ["", f"Subtotal: {_reais(p.get('subtotal'))}"]

        entrega = p.get("entrega") or {}

        if entrega.get("tipo") == "entrega":
            taxa = "a combinar" if entrega.get("combinar") else _reais(p.get("taxa"))
            linhas += [
                f"Entrega: {taxa}",
                f"TOTAL: {_reais(p.get('total'))}",
                "",
                f"{entrega.get('rua', '')}, {entrega.get('numero', '')}" + (f" - {entrega['complemento']}" if entrega.get("complemento") else ""),
                f"{entrega.get('bairro', '')}" + (f" - {entrega['cidade']}" if entrega.get("cidade") else ""),
            ]
            if entrega.get("referencia"):
                linhas.append(f"Ref.: {entrega['referencia']}")
        else:
            linhas += [f"TOTAL: {_reais(p.get('total'))}", "", "RETIRADA NO LOCAL"]

        pagamento = p.get("pagamento") or {}
        linha_pag = f"Pagamento: {PAGAMENTO.get(pagamento.get('forma'), pagamento.get('forma'))}"
        if pagamento.get("forma") == "dinheiro":
            linha_pag += f" (troco p/ {_reais(pagamento['troco'])})" if pagamento.get("troco") else " (sem troco)"

        cliente = p.get("cliente") or {}

        linhas += [
            "", linha_pag,
            f"Cliente: {cliente.get('nome', '')}",
            f"WhatsApp: {repositorio_pedidos_online.formatar_telefone(cliente.get('whatsapp'))}",
        ]

        if p.get("obs"):
            linhas += ["", f"Obs.: {p['obs']}"]

        self._escrever_detalhe("\n".join(linhas))
        self.desenhar_acoes(p)

    # ======================================================
    # SITUAÇÃO DO PEDIDO (igual ao painel do cardápio)
    # ======================================================

    def desenhar_acoes(self, p):

        for filho in self.acoes.winfo_children():
            filho.destroy()

        if not p:
            return

        for status, rotulo in cardapio_online.proximos_status(p):
            ctk.CTkButton(
                self.acoes, text=rotulo, height=34, font=("Arial", 13, "bold"),
                fg_color="#E8590C" if status in ("entrega", "pronto") else None,
                hover_color="#C94A07" if status in ("entrega", "pronto") else None,
                state="disabled" if self._mudando else "normal",
                command=lambda s=status: self.mudar_status(p, s)
            ).pack(fill="x", pady=(0, 6))

        link = cardapio_online.link_whatsapp((p.get("cliente") or {}).get("whatsapp"), p.get("mensagem"))

        if link:
            ctk.CTkButton(
                self.acoes, text="📲 Mandar mensagem ao cliente", height=32,
                fg_color="#25A55F", hover_color="#1E8A4F",
                command=lambda: webbrowser.open(link)
            ).pack(fill="x")

    def mudar_status(self, p, status):

        self._mudando = True
        self.desenhar_acoes(p)
        self.lbl_status.configure(text="Avisando o cardápio online...", text_color="gray")

        cardapio_online.mudar_status_em_segundo_plano(
            self, p["id"], status, lambda pedido, erro: self._status_mudou(p["id"], pedido, erro)
        )

    def _status_mudou(self, pedido_id, pedido, erro):

        self._mudando = False

        if erro:
            self.lbl_status.configure(text=f"⚠ {erro}", text_color="#c2371f")
            self.mostrar_detalhe()
            messagebox.showwarning("Pedidos online", f"A situação não mudou.\n\n{erro}", parent=self)
            return

        # troca o pedido na lista desta janela e no estado compartilhado (faixa da tela de Pedidos)
        self.pedidos = [pedido if p["id"] == pedido_id else p for p in self.pedidos]
        cardapio_online.publicar(self.pedidos)
        self.lbl_status.configure(
            text=f"#{pedido_id}: {STATUS.get(pedido.get('status'), pedido.get('status'))} — atualizado no cardápio às {datetime.now():%H:%M}",
            text_color="#2a7"
        )

        # saiu para entrega / pronto: já oferece o aviso ao cliente, como o painel
        if pedido.get("status") in ("entrega", "pronto"):
            link = cardapio_online.link_whatsapp((pedido.get("cliente") or {}).get("whatsapp"), pedido.get("mensagem"))
            if link and messagebox.askyesno(
                "Avisar o cliente?",
                f"Mensagem para {(pedido.get('cliente') or {}).get('nome', '')}:\n\n{pedido.get('mensagem')}\n\nAbrir no WhatsApp?",
                parent=self
            ):
                webbrowser.open(link)

    # ======================================================

    def lancar(self):

        p = self._pedido_selecionado()

        if not p:
            messagebox.showwarning("Pedidos online", "Selecione um pedido na lista.", parent=self)
            return

        if p.get("status") == "cancelado":
            messagebox.showwarning("Pedidos online", "Esse pedido foi cancelado no cardápio online.", parent=self)
            return

        numero_local = repositorio_pedidos_online.ja_lancado(p["id"])

        if (numero_local or p.get("importadoEm")) and not messagebox.askyesno(
            "Pedido já lançado",
            f"O pedido online #{p['id']} já foi lançado"
            + (f" como Nº {numero_local:04d}" if numero_local else "")
            + ".\n\nLançar de novo mesmo assim?",
            parent=self
        ):
            return

        try:
            estado, avisos = repositorio_pedidos_online.montar_rascunho(p)
        except repositorio_pedidos_online.PedidoOnlineInvalido as erro:
            messagebox.showwarning("Pedidos online", str(erro), parent=self)
            return

        # A tela de Pedidos pergunta se pode descartar um carrinho em
        # andamento; se a resposta for não, a janela continua aberta.
        self.grab_release()

        if self.ao_lancar(estado, avisos):
            self.destroy()
        else:
            self.grab_set()
