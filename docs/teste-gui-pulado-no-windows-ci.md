# Teste de responsividade da tabela pula no CI do Windows

## Status: RESOLVIDO (2026-08-13)

O teste passava no Linux mas pulava no Windows (tanto CI quanto desktop
real com 1920x1080) porque lia o `height` da tabela **antes do debounce
do `tornar_dinamica`** terminar. No Linux as fontes menores faziam o
cálculo inicial (`linhas_para_tabela` em `Produtos.__init__`) já retornar
um valor acima do piso, mascarando o problema. No Windows a fonte "Arial"
real consome mais espaço vertical, então o cálculo inicial retornava o
piso (4 linhas), e só o recálculo pós-`<Configure>` (que passa pelo
debounce de `ATRASO_DEBOUNCE_MS`) corrigia pro valor real (19 linhas numa
tela de 1050px).

**O fix**: adicionar `time.sleep(ESPERA_DEBOUNCE_SEGUNDOS)` + `root.update()`
após construir a tela e antes de ler `linhas_janela_grande`, para que o
debounce complete e o `height` reflita o recálculo real. Com essa mudança o
teste passa tanto no Windows desktop (1920x1080, confirmado) quanto no
Linux.

**No CI (`windows-latest`)**: ainda pode pular, dado que a tela do runner é
fixa em ~768px e mesmo com o debounce a tabela pode continuar no piso — mas
isso é uma limitação real da resolução daquele runner, não um bug no teste.
A cobertura de verdade acontece no Linux CI (Xvfb com tela configurável) e
agora também em qualquer máquina Windows real.

## Contexto original (para referência)

O texto abaixo é a investigação original que levou à descoberta do bug.

## Onde isso vive no código

- `testes/test_tela_produtos_responsividade.py` — o teste em si. Tenta duas
  margens de tela (`MARGENS_TELA_PX = [30, 200]`) antes de desistir e pular,
  com um diagnóstico detalhado na mensagem de skip.
- `testes/gui_ambiente.py` — detecta o ambiente gráfico disponível
  (Windows / Linux com monitor / Xvfb) e, no caso do Xvfb, sobe ele com uma
  tela virtual de 1366x1400 (mais alta que o 1366x768 da loja, de propósito,
  pra esse teste ter espaço de sobra ali).
- `utils/responsivo.py` — a lógica real sendo testada:
  `MINIMO_LINHAS_PADRAO = 4`, `ALTURA_LINHA_TABELA = 32`,
  `ALTURA_CABECALHO_TABELA = 29`, `MARGEM_SEGURANCA = 8`.
- `.github/workflows/build-release.yml` — não tem mais nada relacionado a
  isso hoje (a tentativa de contornar foi revertida — ver histórico do git
  abaixo). O passo "Rodar a suíte de testes" só chama `python -m testes`.

## Cronologia do que já foi tentado

Tudo abaixo foi validado rodando de verdade na Action (não é suposição) —
os commits estão no histórico do `main`, nesta ordem:

1. **`ad76aeb`** — Primeira run real do gate de testes no CI revelou um
   `UnicodeEncodeError`: o console do `windows-latest` usa cp1252 por
   padrão e não sabe codificar `✓`/`✗`/`○` do relatório de testes
   (`testes/relatorio.py`). Corrigido forçando UTF-8 na saída.

2. **`5d39011`** — Com o encoding corrigido, o teste de responsividade em
   si falhou (não pulou — falhou mesmo) com alturas fixas (768/500/900,
   que funcionavam em todo lugar testado localmente):

   ```
   AssertionError: 4 not less than 4 : A tabela deveria ter MENOS linhas
   depois que a janela diminuiu de altura (tinha 4, ficou 4).
   ```

   Ou seja: mesmo a 768px de altura (a maior das três), a tabela já
   estava no piso mínimo de 4 linhas — a diferença entre 768/500/900
   simplesmente não existia no Windows.

   **Descoberta nº 1**: a fonte "Arial" de verdade (Windows) renderiza
   visivelmente mais alta que a fonte substituta usada no Linux/Xvfb, e a
   tela de Produtos (título + filtro + formulário + dica, todos antes da
   tabela) consome espaço suficiente a mais no Windows pra já bater no
   piso mínimo mesmo numa janela de 768px.

   Tentativa de correção: em vez de alturas fixas, usar
   `winfo_screenheight()` e pedir uma janela BEM maior que a tela
   (2400px, tela real de 1080px) pra garantir folga. Isso reproduziu um
   **segundo problema, localmente** (não no CI): um window manager real
   (testado num Linux desktop de verdade, não Xvfb) trata um `geometry()`
   maior que a tela como pedido de "maximizar", e depois de "maximizado"
   passa a ignorar `geometry()` menores — a janela ficou grudada em
   998px (a tela menos a decoração) e nunca mais encolheu, mesmo pedindo
   explicitamente 350px depois.

3. **`45b94de`** — Corrigido usando margens moderadas em vez de valores
   extremos: `altura_grande = winfo_screenheight() - margem`, tentando
   `margem=30` primeiro (mais folga em telas pequenas) e caindo pra
   `margem=200` só se a primeira não conseguir redimensionar o
   suficiente ou não escapar do piso (esse fallback existe por causa do
   bug do "maximizar" do item 2). Passou localmente (Linux com monitor e
   Xvfb), mas na Action:

   ```
   pulado: Este ambiente gráfico não deu pra testar com nenhuma das
   margens tentadas ([30, 200]px): margem=30px -> grande=738px/4linhas,
   pequena=300px/4linhas; margem=200px -> grande=568px/4linhas,
   pequena=300px/4linhas
   ```

   **Descoberta nº 2**: a tela do runner `windows-latest` tem **~768px de
   altura fixos** (738 = 768 − 30). Mesmo pedindo quase a tela inteira
   (738px), a tabela continua no piso de 4 linhas — a "Descoberta nº 1"
   é forte o bastante pra que nem o teto real da tela do runner seja
   suficiente.

4. **`41984b8`** — Aceito e documentado como skip esperado nesse ponto
   (antes da tentativa de contornar via resolução, abaixo).

5. **`2a9e023` → `ccca3b5`** — Tentativa de aumentar a resolução real da
   VM do Windows via PowerShell antes dos testes, usando P/Invoke
   (`user32.dll`) pra chamar a API legada de configuração de display do
   Win32. Nesta ordem:

   1. **Resolução customizada direta** (`ChangeDisplaySettings` pedindo
      1366x2000 sem antes enumerar nada):
      ```
      Resultado da troca de resolução (0 = sucesso): -2
      ```
      `-2` = `DISP_CHANGE_BADMODE` — resolução recusada.

   2. **Enumerar os modos suportados** (`EnumDisplaySettings` a partir do
      modo 0, pra descobrir quais resoluções o driver realmente aceita e
      pedir uma dessas em vez de uma arbitrária):
      ```
      Modos de vídeo suportados pela VM: 0
      ```
      Nenhum modo enumerado — a primeira chamada (`modeNum=0`) já falhou.

   3. **Uma lista de resoluções padrão comuns** (1920x1200, 1600x1200,
      1920x1080, ... até 1280x960), tentadas uma a uma via
      `ChangeDisplaySettings` direto (sem depender da enumeração, que já
      tinha se mostrado quebrada). Antes de cada tentativa, o script
      também chamava `EnumDisplaySettings(NULL, ENUM_CURRENT_SETTINGS,
      ...)` só pra ter um `DEVMODE` válido de base:
      ```
      EnumDisplaySettings(ENUM_CURRENT_SETTINGS) falhou -- desistindo.
      Nenhuma resolução candidata foi aceita -- seguindo com a resolução
      padrão da VM.
      ```
      **`ENUM_CURRENT_SETTINGS` é a consulta mais básica que existe**
      (\"me diga a configuração atual\") — funciona em qualquer sessão
      Windows com uma sessão gráfica normal, incluindo a maioria das VMs.
      Ela falhar também é o dado mais importante desta investigação.

   No meio do caminho (commit `b79e59b`) também apareceu e foi corrigido
   um erro real de compilação C# (`CS0051`, inconsistência de
   acessibilidade entre o struct `DEVMODE` e os métodos que o usam) — não
   tem relação com a causa raiz, só um bug introduzido e corrigido no
   processo.

   A tentativa foi revertida em `ccca3b5` — o passo não tinha mais
   nenhuma hipótese razoável sobrando pra tentar sem acesso interativo a
   uma máquina Windows de verdade.

## Dados/evidências coletados (resumo)

- Tela do runner `windows-latest`: **~768px de altura** (confirmado, não
  suposição).
- Mesmo pedindo ~738px (quase a tela inteira), a tabela de Produtos nunca
  passa de **4 linhas** (o piso mínimo — `MINIMO_LINHAS_PADRAO` em
  `utils/responsivo.py`). Isso implica que o conteúdo acima da tabela
  (título + filtro + formulário + dica) consome **mais de ~549px** de
  altura ali (`738 − 189`, onde 189 é o mínimo de espaço livre pra sair
  do piso com a fórmula atual) — bem mais do que consome no Linux/Xvfb.
- `ChangeDisplaySettings` recusa uma resolução arbitrária
  (`-2`/`DISP_CHANGE_BADMODE`).
- `EnumDisplaySettings` não enumera **nenhum** modo (nem o modo 0).
- `EnumDisplaySettings` com `ENUM_CURRENT_SETTINGS` (`-1`) — a consulta
  mais básica possível — **também falha**.
- Apesar de tudo isso, o Tk/CustomTkinter cria janelas reais normalmente
  nesse runner (toda a suíte de GUI roda lá, só esse teste específico
  pula) — a sessão gráfica em si funciona, só a API legada de
  configuração de display do Win32 parece não responder.

## Minhas suspeitas sobre a causa raiz

Sem acesso interativo a uma máquina Windows real, não dá pra confirmar
qual dessas é a explicação certa — só descartar algumas com mais ou
menos confiança:

1. **Mais provável**: o adaptador de vídeo virtual da VM do
   `windows-latest` (GitHub-hosted, provavelmente Azure) não implementa
   essa API legada (`EnumDisplaySettings`/`ChangeDisplaySettings`) de
   verdade — é comum adaptadores sintéticos modernos (Hyper-V synthetic
   display, driver de renderização por software tipo WARP, ou o
   "Microsoft Basic Display Adapter" numa VM sem GPU passthrough) não
   exporem uma tabela de modos VESA-style tradicional, já que não existe
   hardware físico com EDID por trás. Isso explicaria por que até
   `ENUM_CURRENT_SETTINGS` falha — não tem "modo atual" no sentido que
   essa API antiga espera.

2. **Menos provável, mas não descartada**: um problema de marshaling no
   meu P/Invoke (`testes`/workflow não guardam mais o script, só o
   histórico do git — ver commit `18d5960` pelo código exato usado). O
   layout do struct `DEVMODE` foi conferido campo a campo contra a
   definição pública do Win32 e parece correto (a soma dos tamanhos do
   "union" de posição/orientação bate com a variante que eu declarei),
   mas eu **nunca cheguei a capturar o código de erro real do Windows**
   (`[System.Runtime.InteropServices.Marshal]::GetLastWin32Error()`) —
   só o valor de retorno das próprias funções. Esse é o próximo passo
   mais óbvio de diagnóstico (ver abaixo).

3. **Também não descartada**: mismatch de `CharSet` (ANSI vs Unicode) —
   o P/Invoke não especificava `CharSet` explicitamente, então usa o
   padrão do runtime (`CharSet.Ansi` historicamente, mas vale confirmar
   no .NET usado pelo `pwsh` do runner), enquanto `user32.dll` resolve
   pra `EnumDisplaySettingsA` ou `EnumDisplaySettingsW` dependendo disso
   — um mismatch faria o struct `DEVMODE` ficar com o tamanho errado do
   ponto de vista do Windows, e a API rejeitar silenciosamente.

## Sugestões pra quem for investigar numa máquina Windows real

1. **Primeiro passo, mais valioso**: rodar o mesmo P/Invoke
   interativamente (não dentro de `continue-on-error: true`) e, logo
   depois de cada chamada que falhar, capturar
   `[System.Runtime.InteropServices.Marshal]::GetLastWin32Error()`. Isso
   nunca foi feito — só o valor de retorno das funções (`0`/`-2`) foi
   observado, não o código de erro real do Windows por trás.

2. Rodar `Get-CimInstance -ClassName Win32_VideoController | Select
   Name, VideoModeDescription, CurrentHorizontalResolution,
   CurrentVerticalResolution, AdapterCompatibility` pra identificar de
   verdade qual adaptador de vídeo está em uso — isso confirma ou refuta
   a suspeita nº 1 acima.

3. Tentar explicitamente `[DllImport("user32.dll", CharSet =
   CharSet.Ansi)]` (e o struct com `CharSet = CharSet.Ansi` também) pra
   descartar a suspeita nº 3 — é uma mudança pequena e rápida de testar.

4. Se a API legada realmente não for suportada por esse adaptador, uma
   ferramenta de nível mais alto (ex: algum módulo PowerShell de
   community tipo `DisplayConfig`, ou o utilitário `nircmd.exe`) pode
   ter mais sorte — mas isso também merece ser pesado contra o
   custo/risco de trazer uma dependência de terceiros só pra CI (o
   `nircmd.exe`, por exemplo, é um binário de terceiros que precisaria
   ser baixado a cada run).

5. **Vale reconsiderar se esse caminho compensa de verdade**: a
   cobertura desse comportamento específico (tabela responsiva ao
   redimensionar) já existe e roda de verdade no Linux (monitor real ou
   Xvfb, onde controlamos a resolução livremente). Se o Windows CI
   continuar resistente, uma alternativa mais barata seria aceitar
   definitivamente o skip ali e, se quiser reforçar a cobertura da
   fórmula em si (não do redimensionamento real de janela), escrever um
   teste separado e puramente numérico contra `utils.responsivo.
   linhas_para_tabela()` (sem instanciar nenhuma janela), que não
   depende de resolução de tela nenhuma.

## Como reproduzir localmente (pra comparar com o Windows)

```
python -m testes                              # display real, se houver
env -u DISPLAY python -m testes                # força o fallback pro Xvfb
python -m unittest testes.test_tela_produtos_responsividade -v
```

O `testes/gui_ambiente.py` decide sozinho qual ambiente usar — ver esse
módulo e a seção "Testable cadastros" / "GUI tests" do `CLAUDE.md` pra
mais contexto sobre como os testes de GUI deste projeto são estruturados.
