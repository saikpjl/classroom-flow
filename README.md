# classroom-flow

Entregas e alertas de prazo do Google Classroom, pelo terminal (macOS + zsh).

```
classroom_flow/
├── config.py     caminhos, escopos OAuth, variáveis (NTFY_TOPIC…)
├── errors.py     exceções + tradução de erros HTTP
├── auth.py       OAuth2, cache/renovação do token
├── classroom.py  cursos, atividades, submissões, busca tolerante a acentos
├── drive.py      upload ao Drive
├── submit.py     entrega via API + modo manual assistido
├── notify.py     push no celular (ntfy)
├── alerts.py     janelas de prazo, deduplicação
└── cli.py        comando `cflow`
```

## ⚠️ Limitação da API (leia antes)

`studentSubmissions.modifyAttachments` e `turnIn` só aceitam chamadas do **mesmo projeto do
Google Cloud que criou a atividade**. Em atividades criadas por professores o Google devolve
`403 ProjectPermissionDenied`. Por isso `cflow entregar`:

1. localiza turma/atividade e confere se já foi entregue;
2. se a atividade for "do seu projeto" → sobe ao Drive, anexa e dá `turnIn` pela API;
3. caso contrário (o normal) → **modo manual assistido**: abre o Finder com o arquivo
   selecionado e a atividade no navegador, para você arrastar e clicar em *Entregar*.

## 1. Google Cloud

1. https://console.cloud.google.com → **novo projeto** (ex.: `classroom-flow`).
2. **APIs e serviços → Biblioteca**: ative **Google Classroom API** e **Google Drive API**.
3. **Tela de consentimento OAuth** (Google Auth Platform): tipo **Externo**, preencha nome e e-mail.
4. **Acesso a dados / Escopos**: adicione os 4 escopos de `config.py`.
5. **Público / Usuários de teste**: adicione o seu e-mail do Classroom.
   - Em modo *Testing* o refresh token expira em **7 dias** (o `cflow login` refaz). Para evitar,
     publique o app ("Em produção"); ele aparecerá como "não verificado", o que é ok para uso pessoal.
6. **Credenciais → Criar credenciais → ID do cliente OAuth → App para computador**.
   Baixe o JSON e salve em `~/.config/classroom-flow/credentials.json`.
7. Contas de escola/faculdade (Workspace) podem ter apps de terceiros bloqueados pelo
   administrador (`admin_policy_enforced`). Nesse caso só o admin libera.

## 2. Instalação

```zsh
cd classroom-flow
python3 -m venv .venv && source .venv/bin/activate
pip install -e .

mkdir -p ~/.config/classroom-flow
mv ~/Downloads/client_secret_*.json ~/.config/classroom-flow/credentials.json

cflow login
```

Para usar `cflow` sem ativar o venv, adicione ao `~/.zshrc`:

```zsh
alias cflow="$HOME/classroom-flow/.venv/bin/cflow"
```

## 3. Uso

```zsh
cflow prazos                                   # pendências dos próximos 14 dias
cflow entregar "relatório 2" ~/Docs/rel2.pdf   # busca por parte do título
cflow entregar "lista" lista.pdf --curso calculo --dry-run
```

## 4. Alertas no celular (ntfy)

1. Instale o app **ntfy** (iOS/Android) e assine um tópico com nome longo e aleatório,
   por exemplo `classroom-7f3k9x2m-prazos` (tópicos do ntfy.sh são públicos para quem sabe o nome).
2. Crie `~/.config/classroom-flow/env`:
   ```
   NTFY_TOPIC=classroom-7f3k9x2m-prazos
   ```
3. `cflow testar-notificacao` → deve chegar no celular.
4. `cflow monitorar --dry-run` mostra o que seria enviado.
5. Agende a cada 30 min: `zsh launchd/install.sh`.

Avisos padrão: 72h, 24h, 6h, 1h antes e uma vez após o prazo (se não entregue).
Ajuste com `--limites 120,48,12,2` no plist. Atividades entregues não geram alertas.
Se o token expirar, você recebe um push pedindo `cflow login` (no máximo 1x por dia).
