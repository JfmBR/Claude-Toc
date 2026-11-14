# Claude Toc 🔔

[![tests](https://github.com/JfmBR/Claude-Toc/actions/workflows/tests.yml/badge.svg)](https://github.com/JfmBR/Claude-Toc/actions/workflows/tests.yml)
[![Licença: MIT](https://img.shields.io/badge/licen%C3%A7a-MIT-blue.svg)](LICENSE)

[English](README.md) · **Português**

Plugin para o Claude Code que manda uma notificação para o seu celular quando o Claude:

- ✅ termina uma tarefa;
- ❓ faz uma pergunta;
- 🔐 pede permissão para rodar algo;
- ❌ para por causa de um erro (limite de uso, servidor fora do ar…).

É a campainha do micro-ondas: você não precisa ficar olhando o prato girar. Quando acaba, ele apita.

Os avisos passam pelo [ntfy](https://ntfy.sh), um app de push grátis e sem cadastro. Cada aviso mostra o projeto, o computador, quanto tempo o Claude trabalhou e o final da última resposta.

<!-- Print: adicione docs/images/notifications.png e descomente a linha abaixo.
![Notificações do Claude Toc no celular](docs/images/notifications.png)
-->

## Instalação

**1. Celular.** Instale o app **ntfy** ([Android](https://play.google.com/store/apps/details?id=io.heckel.ntfy) · [iOS](https://apps.apple.com/app/ntfy/id1625396347)) e assine um tópico com nome longo e aleatório, como `toc-seunome-8f3k2m9q`.

**2. Claude Code.** No terminal:

```bash
claude plugin install toc --marketplace JfmBR/Claude-Toc --config ntfy_topic=toc-seunome-8f3k2m9q
```

Ou dentro do Claude Code:

```
/plugin marketplace add JfmBR/Claude-Toc
/plugin install toc@toc
```

O Claude Code pergunta as opções do plugin. Só `ntfy_topic` é obrigatória.

**3. Teste.** Rode `/toc:test` no Claude Code. O celular deve tocar.

Use o **mesmo tópico** em todos os seus computadores. O aviso mostra de qual computador veio.

## Como é cada aviso

| Tipo | Quando | Prioridade | Segunda linha |
|---|---|---|---|
| ✅ Terminou | O Claude termina a resposta | normal | Final da resposta |
| ❓ Pergunta | A resposta termina com `?`, ou o Claude abre uma pergunta de múltipla escolha | alta | A pergunta |
| 🔐 Precisa de permissão | Um pedido de permissão espera ~6 s sem você digitar | alta | O que o Claude quer rodar |
| ❌ Parou com erro | O turno termina com erro da API | alta | O tipo do erro |

Exemplo:

```
✅ Terminou · padaria-app
4 min 32 s · NOTEBOOK
…os 18 testes passaram. Quer que eu abra o pull request?
```

## Comandos

| Comando | O que faz |
|---|---|
| `/toc:test` | Envia um aviso de teste agora. Ignora pausa e horário silencioso |
| `/toc:off` | Pausa os avisos neste computador até `/toc:on` |
| `/toc:on` | Retoma os avisos |
| `/toc:status` | Mostra as configurações e se o horário silencioso está ativo agora |

Esses comandos nunca geram aviso.

## Opções

Altere com `/config` no Claude Code, ou com `claude plugin configure toc@toc`.

| Opção | Padrão | O que faz |
|---|---|---|
| `ntfy_topic` | — (obrigatória) | Tópico que o celular assina |
| `ntfy_server` | `https://ntfy.sh` | Seu próprio servidor ntfy, se tiver |
| `device_name` | hostname | Apelido do computador, como `Notebook` ou `PC` |
| `language` | `pt` | Idioma do aviso: `pt` ou `en` |
| `min_duration_seconds` | `0` | Pula ✅ e ❓ em turnos mais curtos que isso. 🔐 e ❌ sempre saem |
| `quiet_start` / `quiet_end` | `23:00` / `07:00` | Horário silencioso, no horário local. Valores iguais = desligado |
| `include_summary` | `true` | Envia o final da resposta do Claude |
| `summary_length` | `150` | Tamanho máximo do resumo, em caracteres |
| `python_command` | automático | Comando do Python 3.9+. Deixe vazio: ele tenta `python3`, `python` e `py` |

### ⚠️ Horário silencioso

Durante o horário silencioso **nenhum aviso é enviado, nem perguntas nem pedidos de permissão.** Se o Claude pedir algo nesse horário, ele fica esperando e você **não** é avisado. A mensagem é descartada, não fica na fila. O `/toc:status` mostra esse aviso enquanto o horário silencioso está ativo.

### 🔒 Privacidade

- O servidor público `ntfy.sh` não tem senha. **Quem souber o seu tópico lê seus avisos.** Use um tópico longo e aleatório.
- O resumo envia parte da resposta do Claude ao servidor do ntfy. Pode conter nome de arquivo, código ou dado do projeto.
- Para mais privacidade, coloque `include_summary` em `false`, ou aponte `ntfy_server` para um servidor ntfy próprio.

## Requisitos

- Claude Code com suporte a plugins.
- Python 3.9 ou mais novo. Nada para instalar com `pip`.
- `sh`: já vem no Linux e no macOS. No Windows, vem com o [Git for Windows](https://git-scm.com/downloads/win) (Git Bash), que o Claude Code já usa.

## Limitações

- **A detecção de pergunta é uma heurística.** Uma resposta que termina com um "Quer que eu faça X?" educado chega como ❓, não ✅.
- **Sem aviso quando você aperta Esc.** O Claude Code não dispara o evento `Stop` numa interrupção. Isso é proposital: você está no computador.
- **Execuções sem interface (`claude -p`) não avisam.** Os hooks de aviso rodam em segundo plano, e o Claude Code cancela esses hooks quando um `-p` termina.
- **Push nativo.** Se você também ligar o push do Remote Control no `/config` do Claude Code, recebe dois avisos. Use só um dos dois.

## Problemas

1. Rode `/toc:status` e confira tópico e servidor.
2. Rode `/toc:test`. Se falhar, o erro aparece na tela.
3. Veja o log: `~/.claude/plugins/data/toc-toc/claude-toc.log`.
4. Confira se o celular assina exatamente o mesmo tópico.

## Como funciona

O plugin registra [hooks do Claude Code](https://code.claude.com/docs/en/hooks) que chamam `scripts/toc.py`:

| Hook | Uso |
|---|---|
| `UserPromptSubmit` | Guarda a hora de início do turno, para mostrar a duração |
| `Stop` | ✅ ou ❓ |
| `StopFailure` | ❌ |
| `Notification` (`permission_prompt`, `elicitation_dialog`) | 🔐 ou ❓ |
| `PreToolUse` (`AskUserQuestion`) | ❓ |

O script usa só a biblioteca padrão do Python e nunca trava o Claude: todo hook termina com código 0. O projeto completo está em [docs/SPEC.md](docs/SPEC.md).

## Desenvolvimento

```bash
python -m unittest discover -s tests -v
claude plugin validate .
```

O CI roda os testes no Linux e no Windows, com Python 3.9 e 3.13. Veja as versões no [CHANGELOG.md](CHANGELOG.md).

## Licença

[MIT](LICENSE) © João Francisco
