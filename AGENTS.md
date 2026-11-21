# Claude Toc

Regras gerais de trabalho vêm do `CLAUDE.md` global do usuário.

## Produto e stack
- Plugin do Claude Code que avisa no celular (via [ntfy](https://ntfy.sh)) quando o Claude termina, pergunta, pede permissão ou para por erro. Escopo e decisões: `docs/SPEC.md` (pt) e `docs/SPEC.en.md` (en).
- Stack: Python 3.9+ só com biblioteca padrão (`scripts/toc.py`), lançador `scripts/run.sh` (sh), hooks em `hooks/hooks.json`, comandos `/toc:*` em `skills/`, manifesto em `.claude-plugin/`.
- Sem dependências para instalar. Sem `PRODUCT.md`: a especificação faz esse papel.

## Comandos canônicos
- Instalar: não se aplica: sem dependências
- Desenvolver: não se aplica: plugin sem servidor; teste com `/toc:test` no Claude Code
- Lint e formatar: não há configurado
- Tipos: não se aplica: Python sem checagem estática
- Testes: `python -m unittest discover -s tests -v` (use `python3` onde `python` não existir)
- Validar o plugin: `claude plugin validate .`
- Build: não se aplica
- Verificação completa: testes + `claude plugin validate .` — rode antes de declarar uma tarefa concluída. O CI (`.github/workflows/tests.yml`) roda os testes em Linux e Windows, Python 3.9 e 3.13, e o launcher: `sh scripts/run.sh status --data-dir <dir>` deve imprimir "Claude Toc v".

## Mapa de documentação
- Escopo e decisões: `docs/SPEC.md` · `docs/SPEC.en.md`
- Uso e instalação: `README.md` · `README.pt-br.md`
- Versões: `CHANGELOG.md`

## Convenções do projeto
- Repositório público: nada pessoal (caminhos da máquina, nomes, tópicos ou tokens reais) em código, docs, testes ou commits.
- Todo handler de hook termina com código 0: código 2 num hook `Stop` faria o Claude continuar trabalhando.
- Só biblioteca padrão; funciona em Linux, macOS e Windows (Git Bash) e em Python 3.9.
- Texto enviado ao ntfy passa pelo filtro de segredos; não envie texto novo sem passar por ele.
- Código, testes, skills e `CHANGELOG.md` em inglês, como já está no repositório; `README` e spec existem em duas línguas (pt e en) e devem mudar juntos.
- Mudança de comportamento atualiza README, spec (pt e en) e `CHANGELOG.md` (seção `Unreleased`) na mesma mudança.
