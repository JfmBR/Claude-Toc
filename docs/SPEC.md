# Claude Toc — Especificação v1.0.0

> **Status:** implementada e validada no Claude Code 2.1.325
> **Idioma:** português · [English](SPEC.en.md)

---

## 1. Visão geral

**Claude Toc** é um plugin para o Claude Code. Ele manda uma notificação para o seu celular quando o Claude:

- termina uma tarefa;
- faz uma pergunta e fica esperando você;
- pede permissão para rodar algo;
- para por causa de um erro.

**Analogia:** é a campainha do micro-ondas. Você não precisa ficar olhando o prato girar. Quando acaba, ele apita.

### 1.1 Problema

Você manda uma tarefa para o Claude Code e espera. Sem aviso, você fica olhando a tela ou volta tarde demais. Se o Claude parou para pedir permissão ou por erro, ele fica parado até você voltar.

### 1.2 Objetivo

- Avisar no celular, em segundos, quando o Claude precisa de você.
- Mostrar no aviso: projeto, computador, duração e um resumo.
- Funcionar no Windows e no Linux.
- Instalar com um comando, sem `pip install`.

### 1.3 Fora do escopo (v1)

- Responder ao Claude pelo celular.
- Notificar quando **você** interrompe o Claude (Esc).
- Notificar subagentes (`SubagentStop`).
- Abrir o GitHub ao tocar na notificação.
- Fila ou resumo dos avisos do horário silencioso.
- Pausa com duração (ex.: `off 2h`).
- Avisos em execuções sem interface (`claude -p`).

---

## 2. Decisões tomadas

| Item | Decisão |
|---|---|
| Nome de exibição | **Claude Toc** |
| Nome interno | `toc` (comandos `/toc:*`). Nomes que começam com `claude-` são reservados à Anthropic |
| Repositório | [JfmBR/Claude-Toc](https://github.com/JfmBR/Claude-Toc) |
| Canal | [ntfy](https://ntfy.sh) (app grátis, sem conta) |
| Tópico | Um só para todos os computadores |
| Linguagem | Python 3.9+, só biblioteca padrão |
| Lançador | `scripts/run.sh` acha o Python sozinho (`python3`, `python`, `py`) |
| Distribuição | Plugin do Claude Code, com marketplace no próprio repositório |
| Gatilhos | Concluído, pergunta, permissão, erro |
| Interrupção (Esc) | Não notifica |
| Tempo mínimo | Padrão: sempre notifica (0 s). Configurável |
| Conteúdo | Projeto, computador, duração, resumo |
| Resumo | **Final** da última resposta do Claude |
| Computador | Hostname, com apelido opcional |
| Idioma do aviso | Configurável: português (padrão) ou inglês |
| Prioridade | ✅ normal. ❓ 🔐 ❌ alta |
| Extras | Emoji por tipo, horário silencioso, comandos de controle |
| Horário silencioso | Padrão: 23:00 às 07:00. Descarta tudo |
| Pausa (`off`) | Até religar (`on`). Vale por computador |
| Licença | MIT |
| Versão | SemVer + `CHANGELOG.md` |
| CI | GitHub Actions: Windows e Linux, Python 3.9 e 3.13, mais `claude plugin validate` |
| Demo no README | Print das notificações no celular |
| Documentação | Português e inglês |

---

## 3. Como funciona

### 3.1 Fluxo

```
Você envia o prompt
   └─► UserPromptSubmit  → salva a hora de início da sessão
                           (marca o turno se o prompt for /toc:...)

Claude trabalha...
   ├─► Abre pergunta de múltipla escolha → PreToolUse (AskUserQuestion) → ❓
   ├─► Pediu permissão (~6 s sem digitar) → Notification (permission_prompt) → 🔐
   ├─► Servidor MCP pede dados          → Notification (elicitation_dialog) → ❓
   ├─► Erro de API                       → StopFailure → ❌
   └─► Terminou                          → Stop
                                            ├─ turno de /toc:...  → nada
                                            ├─ termina com "?"    → ❓
                                            └─ senão              → ✅

Você aperta Esc → o Claude Code não dispara Stop → nada
```

### 3.2 Hooks usados

| Evento | Matcher | Modo | Função |
|---|---|---|---|
| `UserPromptSubmit` | — | síncrono, 5 s | Grava a hora de início |
| `Stop` | — | `async` | Envia ✅ ou ❓ |
| `StopFailure` | — (todos os erros) | `async` | Envia ❌ |
| `Notification` | `permission_prompt\|elicitation_dialog` | `async` | Envia 🔐 ou ❓ |
| `PreToolUse` | `AskUserQuestion` | `async` | Envia ❓ com o texto da pergunta |

**Por que não usar `idle_prompt`:** ele dispara ~60 s depois de um `Stop`. Ia gerar aviso duplicado.

**Por que `async`:** o envio nunca atrasa o Claude. Um hook assíncrono não consegue bloquear nada, então não há risco de travar a sessão.

### 3.3 Regras de decisão (ordem de checagem)

A primeira regra que bloquear encerra o fluxo.

1. **Plugin pausado** (`/toc:off`) → não envia.
2. **Horário silencioso** → não envia. Vale para **todos** os tipos.
3. **Comando do próprio plugin** (só no `Stop`) → se o prompt do turno começou com `/toc:`, não envia.
4. **Tempo mínimo** (só ✅ e ❓ vindos do `Stop`) → se a duração for menor que o mínimo, ou desconhecida, não envia.
5. **Envia** a notificação.

> 🔐 e ❌ ignoram o tempo mínimo. Eles travam o Claude, então sempre valem o aviso.
> Interrupção (Esc) não precisa de regra: o Claude Code não dispara `Stop` quando você interrompe.

### 3.4 Detecção de pergunta (heurística)

- Pega `last_assistant_message` do evento `Stop`.
- Remove markdown e espaços do fim.
- Se o último caractere for `?` (ou `？`) → tipo ❓.
- **Limitação:** o Claude às vezes termina com "Quer que eu faça X?" só por educação. Nesse caso o aviso vem como ❓. Isso é aceitável.

---

## 4. Conteúdo da notificação

### 4.1 Formato (corpo JSON enviado ao ntfy)

| Campo | Conteúdo | Exemplo |
|---|---|---|
| `topic` | Opção `ntfy_topic` | `toc-joao-8f3k2m9q` |
| `title` | Tipo + projeto | `Terminou · padaria-app` |
| `message` | Linha 1: duração e computador. Linha 2: detalhe | `4 min 32 s · NOTEBOOK`<br>`…e os testes passaram. Quer que eu faça o deploy?` |
| `tags` | Shortcode do emoji. O ntfy mostra o emoji antes do título | `["white_check_mark"]` |
| `priority` | Por tipo | `3` |

O emoji vai em `tags`, não no título. Se fosse nos dois, o app mostraria o emoji duas vezes.

### 4.2 Tipos

| Tipo | Emoji (tag) | Título (pt) | Título (en) | Prioridade | Linha 2 |
|---|---|---|---|---|---|
| Concluído | ✅ `white_check_mark` | `Terminou` | `Finished` | 3 | Resumo |
| Pergunta | ❓ `question` | `Pergunta` | `Question` | 4 | Resumo, ou texto da pergunta |
| Permissão | 🔐 `closed_lock_with_key` | `Precisa de permissão` | `Needs permission` | 4 | Campo `message` do evento |
| Erro | ❌ `x` | `Parou com erro` | `Stopped with error` | 4 | Tipo do erro, traduzido |
| Teste | 🔔 `bell` | `Teste` | `Test` | 3 | Frase fixa |

### 4.3 De onde vem cada dado

| Dado | Fonte |
|---|---|
| Projeto | Pasta raiz do git a partir de `cwd` (procura `.git` subindo as pastas). Sem git, nome da pasta `cwd` |
| Computador | Opção `device_name`. Se vazia, `socket.gethostname()` |
| Duração | Hora do evento menos a hora salva no `UserPromptSubmit` da mesma `session_id` |
| Resumo | **Final** de `last_assistant_message`: sem markdown, espaços colapsados, últimos `summary_length` caracteres, começando numa palavra inteira, com `…` no início se foi cortado |
| Pergunta (`AskUserQuestion`) | `tool_input.questions[0].question` |
| Tipo do erro | Campo `error` do `StopFailure` (`rate_limit`, `overloaded`, `server_error`…), traduzido. Valor novo vira "Erro desconhecido" |

### 4.4 Formato da duração

| Duração | Exibição |
|---|---|
| < 60 s | `42 s` |
| < 1 h | `4 min 32 s` |
| ≥ 1 h | `1 h 05 min` |
| Desconhecida | só o computador na linha 1 |

A duração fica desconhecida se o plugin foi instalado no meio da sessão.

---

## 5. Configuração

### 5.1 Opções do plugin (`userConfig`)

O Claude Code pergunta estes valores ao ativar o plugin. Também dá para mudar com `/config` ou `claude plugin configure toc@toc`.

| Chave | Tipo | Padrão | Descrição |
|---|---|---|---|
| `ntfy_topic` | string | — (obrigatório) | Nome do tópico. Use algo aleatório |
| `ntfy_server` | string | `https://ntfy.sh` | Servidor ntfy |
| `python_command` | string | vazio (automático) | Só se o Python 3.9+ tiver outro nome |
| `device_name` | string | vazio (hostname) | Apelido do computador |
| `language` | string | `pt` | `pt` ou `en` |
| `min_duration_seconds` | number | `0` | Tempo mínimo para ✅ e ❓ |
| `quiet_start` | string `HH:MM` | `23:00` | Início do horário silencioso |
| `quiet_end` | string `HH:MM` | `07:00` | Fim do horário silencioso |
| `include_summary` | boolean | `true` | Desligue para não mandar o texto do Claude ao ntfy |
| `summary_length` | number | `150` | Tamanho máximo do resumo (20 a 1000) |

Regras:
- `quiet_start` igual a `quiet_end` → horário silencioso desligado.
- O horário silencioso pode cruzar a meia-noite (23:00 → 07:00).
- O horário usa o relógio local do computador.
- Valor inválido → usa o padrão e grava um aviso no log.

### 5.2 Como o script recebe as opções

| Origem | Quando | Prioridade |
|---|---|---|
| Variáveis `CLAUDE_PLUGIN_OPTION_<CHAVE>` | Hooks (o Claude Code exporta) | 1ª |
| Argumentos `--set chave=valor` | Uso manual | 2ª |
| `config.json` no diretório de dados | Comandos `/toc:*` | 3ª |
| Padrões do script | Opção não definida | última |

Cada hook grava as opções que recebeu em `config.json`. Os comandos `/toc:*` rodam pela ferramenta Bash, que não recebe essas variáveis, então eles leem esse arquivo. Digitar `/toc:test` já dispara o `UserPromptSubmit`, que atualiza o arquivo antes do comando rodar.

**Por que o script tem seus próprios padrões:** o Claude Code não substitui `${user_config.CHAVE}` quando a opção ficou no padrão. Por isso nenhum hook depende dessa substituição.

### 5.3 Estado interno

Fica em `${CLAUDE_PLUGIN_DATA}` (`~/.claude/plugins/data/toc-toc/`), que sobrevive a atualizações do plugin:

```
toc-toc/
├── state.json          # { "enabled": true }
├── config.json         # cópia das opções, para os comandos /toc:*
├── starts/
│   └── <session_id>    # { "time": ..., "skip": false }
└── claude-toc.log      # erros, rotacionado em 100 KB
```

- Um arquivo por sessão em `starts/` evita conflito entre sessões paralelas.
- Arquivos com mais de 24 h são apagados a cada novo prompt.
- `enabled` vale por computador.

---

## 6. Comandos de controle

São *skills* do plugin com `disable-model-invocation: true`: só você chama, o Claude não chama sozinho.

| Comando | Ação |
|---|---|
| `/toc:test` | Envia uma notificação de teste agora. Ignora horário silencioso e pausa |
| `/toc:off` | Pausa os avisos neste computador até você rodar `on` |
| `/toc:on` | Retoma os avisos |
| `/toc:status` | Mostra: estado, tópico (parcial), servidor, computador, idioma, tempo mínimo, horário silencioso e resumo |

Cada comando pede ao Claude para rodar `sh "${CLAUDE_PLUGIN_ROOT}/scripts/run.sh" <comando> --data-dir "${CLAUDE_PLUGIN_DATA}"` e mostrar a saída. O turno de um comando `/toc:` não gera aviso.

---

## 7. Avisos ao usuário

### 7.1 Horário silencioso ⚠️

> **Durante o horário silencioso, nenhum aviso é enviado. Isso inclui perguntas, pedidos de permissão e erros.**
> Se o Claude pedir algo nesse horário, ele fica parado esperando, e você **não** será avisado. A mensagem é descartada, não fica na fila.

Este aviso aparece no README e na saída de `/toc:status` quando o horário silencioso está ativo.

### 7.2 Privacidade 🔒

- O servidor público `ntfy.sh` não pede senha. **Quem souber o nome do tópico lê seus avisos.**
- Use um tópico longo e aleatório. Exemplo: `toc-joao-8f3k2m9q`.
- O resumo envia parte da resposta do Claude ao servidor. Pode conter nome de arquivo, trecho de código ou dado do projeto.
- Para mais privacidade: desligue `include_summary`, ou use um servidor ntfy próprio em `ntfy_server`.

### 7.3 Push nativo

Se você também ligar o push do Remote Control no `/config` do Claude Code, vai receber **dois** avisos. Use só um dos dois.

---

## 8. Requisitos técnicos

### 8.1 Lançador `run.sh`

- Shell POSIX. Roda no Linux, macOS e no Git Bash do Windows.
- Tenta, em ordem: `python_command` (se definido), `python3`, `python`, `py`.
- Só aceita um Python que responda a `sys.version_info >= (3, 9)`. Isso pula o atalho da Microsoft Store, que existe mas não funciona.
- Lê o JSON do hook uma vez e repassa ao Python.
- Sempre sai com código 0.

### 8.2 Script `toc.py`

- **Subcomandos de hook** (JSON pelo stdin): `start`, `stop`, `failure`, `notify`, `ask`.
- **Subcomandos de controle:** `test`, `on`, `off`, `status`. Aceitam `--data-dir` e `--set chave=valor`.
- **Envio:** `urllib.request`, `POST` com JSON no corpo para a raiz do servidor. JSON evita problemas de acento em cabeçalhos HTTP.
- **Timeout de rede:** 5 s.
- **Textos:** dicionário `pt`/`en` dentro do script.
- **Hooks nunca escrevem no stdout.** A saída de um `UserPromptSubmit` entraria no contexto do Claude.
- **Hooks sempre saem com código 0.**

> ⚠️ **Nunca sair com código 2 no `Stop`.** Pela doc oficial, exit 2 no `Stop` faz o Claude continuar trabalhando. Todo erro é capturado, gravado no log e termina com `exit 0`.

### 8.3 Configuração dos hooks

Forma *shell* (`command` sem `args`), porque o `sh` precisa de um shell no Windows:

```json
{
  "type": "command",
  "command": "sh \"${CLAUDE_PLUGIN_ROOT}/scripts/run.sh\" stop",
  "async": true
}
```

O arquivo completo está em `hooks/hooks.json`.

### 8.4 Estrutura do repositório

```
Claude-Toc/
├── .claude-plugin/
│   ├── plugin.json         # nome "toc", displayName "Claude Toc", userConfig
│   └── marketplace.json    # marketplace "toc" com o plugin na raiz ("./")
├── .github/workflows/
│   └── tests.yml           # testes + launcher + claude plugin validate
├── hooks/
│   └── hooks.json
├── skills/
│   ├── test/SKILL.md
│   ├── on/SKILL.md
│   ├── off/SKILL.md
│   └── status/SKILL.md
├── scripts/
│   ├── run.sh              # acha o Python
│   └── toc.py              # toda a lógica
├── tests/
│   └── test_toc.py         # unittest, sem dependências
├── docs/
│   ├── SPEC.md
│   ├── SPEC.en.md
│   └── images/             # prints das notificações
├── README.md               # inglês
├── README.pt-br.md
├── CHANGELOG.md
├── .gitignore
└── LICENSE                 # MIT
```

### 8.5 Instalação

Em um passo, no terminal (Claude Code 2.1.275+):

```bash
claude plugin install toc --marketplace JfmBR/Claude-Toc --config ntfy_topic=SEU-TOPICO
```

Ou dentro do Claude Code:

```
/plugin marketplace add JfmBR/Claude-Toc
/plugin install toc@toc
```

O repositório precisa ser **público** para outras pessoas instalarem.

### 8.6 Compatibilidade

| Sistema | Requisito |
|---|---|
| Linux | Python 3.9+ |
| Windows | Python 3.9+ e Git for Windows (fornece o `sh`) |
| macOS | Python 3.9+ (não é foco, mas deve funcionar) |

A versão mínima subiu de 3.8 para 3.9: o Python 3.8 está sem suporte desde outubro de 2024, e o 3.9 foi testado aqui.

### 8.7 Versionamento

- SemVer: `MAJOR.MINOR.PATCH`. Primeira versão: `1.0.0`.
- Versão em `plugin.json` igual à tag do git (`v1.0.0`). Mudar a versão é o que faz os usuários receberem a atualização.
- `CHANGELOG.md` no formato *Keep a Changelog*.

---

## 9. Validação feita

Os 6 pontos em aberto da versão anterior da spec foram resolvidos assim:

| # | Ponto | Resultado |
|---|---|---|
| 1 | Caixa de perguntas (`AskUserQuestion`) | Não gera `Notification`. Solução: hook `PreToolUse` com matcher `AskUserQuestion`, que envia o texto da pergunta |
| 2 | `${user_config.*}` no `command` | **Falha** quando a opção fica no padrão: o hook não roda. Solução: lançador `run.sh` e opções lidas por variável de ambiente |
| 3 | Nome dos comandos | Prefixados pelo nome do plugin: `/toc:test`. O nome `claude-toc` é reservado e foi trocado por `toc` |
| 4 | `async` recebe o JSON completo | Sim, pela doc oficial. Mas em `claude -p` o Claude Code cancela hooks assíncronos ao sair |
| 5 | `Stop` ao apertar Esc | Não dispara, pela doc oficial. A regra de interrupção não precisa de código |
| 6 | Campos do `StopFailure` | `error` (tipo), `error_details` e `last_assistant_message` |

### 9.1 Teste de ponta a ponta

Rodado no Claude Code 2.1.325 real, com o plugin instalado pelo marketplace local e um servidor ntfy falso:

- Prompt em subpasta de um repo git → chegou `Pergunta · meu-projeto`, `4 s · SANDBOX`, com o final da resposta.
- `/toc:status`, `/toc:test`, `/toc:off`, `/toc:on` → saída correta. Só o `test` gerou aviso.
- `/toc:off` → o `Stop` seguinte não enviou nada.

---

## 10. Plano de testes

### 10.1 Testes automáticos (`unittest`, 32 casos)

| Área | Casos |
|---|---|
| Horário silencioso | Dentro, fora, cruzando meia-noite, início = fim |
| Duração | 42 s, 4 min 32 s, 1 h 05 min, sem início |
| Detecção de pergunta | Termina com `?`, com `?` + markdown, sem `?`, texto vazio |
| Resumo | Corte no final, início em palavra inteira, `…`, remoção de markdown |
| Nome do projeto | Subpasta de repo git, pasta sem git |
| Configuração | Padrões, valores inválidos, prioridade das origens, idioma |
| Decisão | Pausa e silêncio bloqueiam tudo; tempo mínimo; 🔐 e ❌ ignoram o mínimo; `AskUserQuestion`; resumo desligado |
| Ponta a ponta | Turno completo com servidor falso; hook nunca falha (rede fora, JSON inválido); `off`/`on`/`test`/`status`; comandos `/toc:` não avisam; aviso de silêncio no `status`; limpeza de arquivos antigos |

### 10.2 CI (GitHub Actions)

- `python -m unittest` em `ubuntu-latest` e `windows-latest`, com Python 3.9 e 3.13.
- Teste do `run.sh` pelo Git Bash (no Windows, confirma que ele acha o Python).
- `claude plugin validate .` com a versão atual do Claude Code.

### 10.3 Testes manuais (no seu computador)

- [ ] Windows: tarefa curta → recebe ✅ com duração.
- [ ] Linux: tarefa curta → recebe ✅ com duração.
- [ ] Pedido de permissão parado ~6 s → recebe 🔐.
- [ ] Pergunta de múltipla escolha → recebe ❓ com o texto.
- [ ] `language: en` → textos em inglês.
- [ ] Horário silencioso ativo → nada chega, `/toc:status` mostra o aviso.
- [ ] Notebook e PC no mesmo tópico → cada aviso mostra o computador certo.

---

## 11. Ideias futuras (v2+)

- Tocar na notificação abre o repositório no GitHub (campo `click` do ntfy).
- Pausa com duração (`/toc:off 2h`).
- Token de acesso para servidores ntfy com senha.
- Fila do horário silencioso com resumo às 07:00.
- Telegram e Discord como canais alternativos.
- Suporte a Windows sem Git Bash (lançador em PowerShell).
- Ícone do plugin (`.claude-plugin/icon.png`).

---

## 12. Referências

- [Hooks reference — Claude Code](https://code.claude.com/docs/en/hooks)
- [Plugin manifest reference — Claude Code](https://code.claude.com/docs/en/plugins/manifest-reference)
- [Marketplace reference — Claude Code](https://code.claude.com/docs/en/plugins/marketplace-reference)
- [ntfy — documentação](https://docs.ntfy.sh)
