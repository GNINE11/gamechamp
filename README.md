# Plataforma para Organizar Campeonato de Games
## Proposta Completa

---

## 1. Funcionalidades por Categoria

### Autenticação e Contas

- Cadastro de jogadores com nome de usuário, e-mail e senha
- Login/logout para jogadores e administradores
- Área administrativa Django (`/admin`) com acesso restrito a staff
- Perfil do jogador com avatar e bio

---

### Gerenciamento de Campeonatos — Admin

- Criar, editar e excluir campeonatos com todas as configurações de formato
- Definir formato geral: eliminação simples, eliminação dupla, pontos corridos ou grupos + playoffs
- Configurar formato das partidas por fase: Bo1, Bo3 ou Bo5 (podendo ser diferente na final)
- Definir número de grupos, times por grupo e quantos avançam de cada grupo
- Configurar critérios de desempate em ordem de prioridade
- Ativar ou desativar disputa de 3º lugar
- Definir método de chaveamento: aleatório, manual ou por ranking
- Abrir e fechar inscrições
- Aprovar ou rejeitar inscrições de equipes
- Gerar chaveamento automaticamente ao fechar inscrições
- Registrar placar de cada game/mapa dentro de uma partida
- Encerrar campeonato e registrar campeão

---

### Gerenciamento de Equipes — Jogadores

- Criar equipe (criador torna-se capitão automaticamente)
- Editar nome e logo da equipe
- Convidar jogadores por nome de usuário
- Aceitar ou recusar convites recebidos
- Capitão pode remover membros e cancelar convites pendentes
- Capitão pode transferir a capitania para outro membro

---

### Participação em Campeonatos — Capitão

- Inscrever a equipe em campeonatos com inscrições abertas
- Cancelar inscrição enquanto ainda pendente
- Acompanhar status da inscrição: pendente, aprovada ou rejeitada

---

### Chaveamento e Partidas

- Visualização do bracket/chave do torneio por fase
- Tabela de classificação por grupo com pontos, vitórias, saldo e posição
- Lista de partidas com times, data, horário e formato (Bo1/Bo3/Bo5)
- Resultado de cada game/mapa registrado individualmente
- Vencedor da partida calculado automaticamente pela soma dos games
- Avanço automático do vencedor para a próxima fase
- Critérios de desempate aplicados automaticamente na classificação dos grupos

---

### Área Pública — Sem Login

- Listar campeonatos ativos e encerrados
- Visualizar bracket, grupos e resultados
- Ver equipes participantes de cada campeonato

---

## 2. Entidades do Banco de Dados

---

### User — Estendido via AbstractUser

| Campo | Tipo | Descrição |
|---|---|---|
| `id` | PK | Identificador único |
| `username` | string | Nome de usuário único |
| `email` | string | E-mail único |
| `password` | string | Senha (hash) |
| `is_staff` | boolean | Define acesso administrativo |
| `avatar` | image | Foto de perfil (opcional) |
| `bio` | text | Descrição curta (opcional) |
| `created_at` | datetime | Data de cadastro |

---

### Team — Equipe

| Campo | Tipo | Descrição |
|---|---|---|
| `id` | PK | Identificador único |
| `name` | string | Nome da equipe |
| `logo` | image | Logo (opcional) |
| `captain` | FK → User | Capitão atual |
| `created_at` | datetime | Data de criação |

---

### TeamMembership — Membros da Equipe

| Campo | Tipo | Descrição |
|---|---|---|
| `id` | PK | Identificador único |
| `team` | FK → Team | Equipe |
| `player` | FK → User | Jogador membro |
| `joined_at` | datetime | Data de entrada |

---

### Invite — Convite

| Campo | Tipo | Descrição |
|---|---|---|
| `id` | PK | Identificador único |
| `team` | FK → Team | Equipe que convidou |
| `invited_player` | FK → User | Jogador convidado |
| `status` | enum | `pending`, `accepted`, `declined`, `cancelled` |
| `created_at` | datetime | Data do convite |
| `responded_at` | datetime | Data da resposta |

---

### Championship — Campeonato

| Campo | Tipo | Descrição |
|---|---|---|
| `id` | PK | Identificador único |
| `name` | string | Nome do campeonato |
| `game` | string | Jogo |
| `status` | enum | `draft`, `open`, `in_progress`, `finished` |
| `max_teams` | integer | Máximo de equipes |
| `start_date` | date | Data de início |
| `created_by` | FK → User | Admin responsável |
| `stage_format` | enum | `single_elimination`, `double_elimination`, `round_robin`, `groups_then_playoffs` |
| `group_count` | integer | Nº de grupos (se aplicável) |
| `teams_per_group` | integer | Times por grupo (se aplicável) |
| `teams_advancing_per_group` | integer | Quantos avançam de cada grupo |
| `group_match_format` | enum | `bo1`, `bo3`, `bo5` — formato na fase de grupos |
| `playoff_format` | enum | `single_elimination`, `double_elimination` |
| `playoff_match_format` | enum | `bo1`, `bo3`, `bo5` — formato nos playoffs |
| `final_match_format` | enum | `bo1`, `bo3`, `bo5` — pode ser diferente |
| `third_place_match` | boolean | Se haverá disputa de 3º lugar |
| `seeding_method` | enum | `random`, `manual`, `by_ranking` |
| `created_at` | datetime | Data de criação |

---

### TiebreakerRule — Critério de Desempate

| Campo | Tipo | Descrição |
|---|---|---|
| `id` | PK | Identificador único |
| `championship` | FK → Championship | Campeonato |
| `priority` | integer | Ordem de aplicação (1 = primeiro) |
| `criterion` | enum | `points`, `wins`, `head_to_head`, `round_diff`, `rounds_won`, `win_rate` |

---

### Registration — Inscrição

| Campo | Tipo | Descrição |
|---|---|---|
| `id` | PK | Identificador único |
| `championship` | FK → Championship | Campeonato |
| `team` | FK → Team | Equipe inscrita |
| `status` | enum | `pending`, `approved`, `rejected` |
| `registered_at` | datetime | Data da inscrição |
| `reviewed_at` | datetime | Data da revisão pelo admin |

---

### Group — Grupo

| Campo | Tipo | Descrição |
|---|---|---|
| `id` | PK | Identificador único |
| `championship` | FK → Championship | Campeonato |
| `name` | string | Ex: "Grupo A", "Grupo B" |

---

### GroupStanding — Classificação no Grupo

| Campo | Tipo | Descrição |
|---|---|---|
| `id` | PK | Identificador único |
| `group` | FK → Group | Grupo |
| `team` | FK → Team | Equipe |
| `wins` | integer | Vitórias |
| `losses` | integer | Derrotas |
| `draws` | integer | Empates |
| `points` | integer | Pontos acumulados |
| `rounds_won` | integer | Rounds/mapas ganhos |
| `rounds_lost` | integer | Rounds/mapas perdidos |
| `round_diff` | integer | Saldo (calculado) |
| `position` | integer | Posição no grupo |

---

### Match — Partida

| Campo | Tipo | Descrição |
|---|---|---|
| `id` | PK | Identificador único |
| `championship` | FK → Championship | Campeonato |
| `format` | enum | `bo1`, `bo3`, `bo5` |
| `phase` | enum | `group`, `playoff`, `grand_final` |
| `group` | FK → Group (nullable) | Grupo (se fase de grupos) |
| `playoff_round` | enum | `quarter`, `semi`, `final`, `third_place` (nullable) |
| `round_number` | integer | Número da rodada dentro da fase |
| `team_a` | FK → Team (nullable) | Equipe A |
| `team_b` | FK → Team (nullable) | Equipe B |
| `winner` | FK → Team (nullable) | Vencedor (preenchido ao final) |
| `status` | enum | `scheduled`, `ongoing`, `finished` |
| `scheduled_at` | datetime | Data e hora agendada |

---

### GameResult — Resultado de Cada Game/Mapa

| Campo | Tipo | Descrição |
|---|---|---|
| `id` | PK | Identificador único |
| `match` | FK → Match | Partida |
| `game_number` | integer | Número do game (1, 2, 3...) |
| `score_a` | integer | Placar da equipe A neste game |
| `score_b` | integer | Placar da equipe B neste game |
| `winner` | FK → Team | Vencedor deste game |
| `map` | string (opcional) | Mapa/stage jogado |

---

## 3. Relacionamentos entre Entidades

```
User ──< TeamMembership >── Team
            (N:N via TeamMembership)

User ────── captain ────── Team
            (1:N — um usuário pode ser capitão de uma equipe)

Team ──< Invite >── User
            (N:N via Invite — capitão convida jogadores)

User ──< Championship
            (1:N via created_by — admin cria campeonatos)

Team ──< Registration >── Championship
            (N:N via Registration — times se inscrevem)

Championship ──< TiebreakerRule
            (1:N — critérios de desempate ordenados)

Championship ──< Group ──< GroupStanding >── Team
            (campeonato → grupos → classificação por time)

Championship ──< Match ──< GameResult
            (campeonato → partidas → games individuais)

Match ────── team_a / team_b / winner ────── Team
            (cada partida referencia até três times)

Match ────── group ────── Group (nullable)
            (partidas de grupo referenciam seu grupo)
```

### Tabela Resumo

| Entidades | Cardinalidade | Descrição |
|---|---|---|
| `User` ↔ `Team` | N:N via `TeamMembership` | Jogadores pertencem a equipes |
| `User` → `Team` | 1:N via `captain` | Um usuário pode ser capitão |
| `User` ↔ `Team` | N:N via `Invite` | Capitão convida jogadores |
| `User` → `Championship` | 1:N via `created_by` | Admin cria campeonatos |
| `Team` ↔ `Championship` | N:N via `Registration` | Times se inscrevem |
| `Championship` → `TiebreakerRule` | 1:N | Critérios ordenados por prioridade |
| `Championship` → `Group` | 1:N | Campeonato tem grupos |
| `Group` → `GroupStanding` | 1:N | Classificação por grupo |
| `Team` → `GroupStanding` | 1:N | Time aparece na classificação |
| `Championship` → `Match` | 1:N | Campeonato possui partidas |
| `Group` → `Match` | 1:N | Grupo possui partidas (nullable) |
| `Match` → `Team` | N:1 (×3) | `team_a`, `team_b`, `winner` |
| `Match` → `GameResult` | 1:N | Bo3/Bo5 tem múltiplos games |
| `GameResult` → `Team` | N:1 | Vencedor de cada game |

---

## 4. Observações de Implementação

**Extensão do User** — use `AbstractUser` e adicione `avatar` e `bio` diretamente, sem criar um `Profile` separado. Mais simples para o escopo do trabalho.

**Status como TextChoices** — defina todos os campos de status como `models.TextChoices` do Django. Fica legível no código e seguro no banco.

**Vencedor da partida** — o `winner` em `Match` deve ser calculado via método do model com base nos `GameResult` filhos, nunca preenchido manualmente pelo admin no caso de Bo3/Bo5.

**Chaveamento** — ao fechar as inscrições, dispare um método ou signal que leia as equipes aprovadas e gere os objetos `Match` da primeira fase automaticamente, respeitando o `seeding_method` configurado.

**Critérios de desempate** — implemente um método no `Group` ou no `Championship` que ordene os `GroupStanding` respeitando a sequência de `TiebreakerRule` pelo campo `priority`.

**Permissões** — use `@login_required` para áreas de jogadores e `@staff_member_required` (ou `user.is_staff`) para ações administrativas customizadas fora do `/admin`.

**Formatos de partida por fase** — ao gerar uma partida, herde o formato correto do campeonato: `group_match_format` para partidas de grupo, `final_match_format` para a grande final, e `playoff_match_format` para as demais fases de playoffs.

---

## 5. Estrutura de Pastas

```
gamechamp/
├── manage.py
├── requirements.txt
├── .env
├── .gitignore
├── README.md
│
├── config/                          # configurações do projeto Django
│   ├── __init__.py
│   ├── asgi.py
│   ├── settings.py
│   ├── urls.py
│   └── wsgi.py
│
├── apps/
│   ├── accounts/                    # User (AbstractUser estendido)
│   │   ├── migrations/
│   │   ├── admin.py
│   │   ├── forms.py
│   │   ├── models.py
│   │   ├── urls.py
│   │   └── views.py
│   │
│   ├── teams/                       # Team, TeamMembership, Invite
│   │   ├── migrations/
│   │   ├── admin.py
│   │   ├── forms.py
│   │   ├── models.py
│   │   ├── urls.py
│   │   └── views.py
│   │
│   ├── championships/               # Championship, TiebreakerRule, Registration
│   │   ├── migrations/
│   │   ├── admin.py
│   │   ├── forms.py
│   │   ├── models.py
│   │   ├── urls.py
│   │   ├── views.py
│   │   └── bracket.py               # lógica de geração do chaveamento
│   │
│   └── matches/                     # Group, GroupStanding, Match, GameResult
│       ├── migrations/
│       ├── admin.py
│       ├── forms.py
│       ├── models.py
│       ├── urls.py
│       ├── views.py
│       └── standings.py             # lógica de classificação e desempate
│
├── templates/                       # templates 
│   ├── base.html
│   ├── navbar.html
│   └── home.html
│
├── static/
│   ├── css/
│   ├── js/
│   └── img/
│
└── media/                           # uploads dos usuários
    ├── avatars/
    └── team_logos/
```

---

### Por que essa divisão em 4 apps?

A regra de ouro é: cada app deve ser responsável por um domínio de negócio coeso. Se você deletar um app, o sistema ainda deve fazer sentido sem ele.

**`accounts`** — tudo que é sobre identidade. O model `User` estendido fica aqui. Se amanhã você trocar para autenticação social (Google, Discord), você mexe só aqui.

**`teams`** — tudo que é sobre organização de jogadores. `Team`, `TeamMembership` e `Invite` são inseparáveis: um time só existe quando tem membros, e membros entram por convite. Esse trio vive junto.

**`championships`** — tudo que é sobre a competição em si: `Championship`, `TiebreakerRule` e `Registration`. A inscrição (`Registration`) fica aqui, e não em `teams`, porque ela é uma decisão do campeonato — o admin aprova ou rejeita — não uma decisão do time.

**`matches`** — tudo que acontece dentro de um campeonato já aberto: `Group`, `GroupStanding`, `Match` e `GameResult`. Essa app depende de `championships` e `teams`, mas é isolada porque tem sua própria lógica complexa de classificação, chaveamento por fase e contagem de games no Bo3/Bo5.

---

### Os dois arquivos extras que fazem diferença

**`championships/bracket.py`** — concentra a lógica de geração do chaveamento. Quando o admin fecha as inscrições, esse módulo lê as equipes aprovadas e cria os objetos `Match` da primeira fase, respeitando o `seeding_method` configurado. Manter isso fora do `views.py` e do `models.py` deixa o código testável e fácil de alterar.

**`matches/standings.py`** — concentra o algoritmo de classificação dos grupos. Recebe uma lista de `GroupStanding` e os `TiebreakerRule` do campeonato e retorna a tabela ordenada pela sequência de critérios. Separar essa lógica evita engordar o model com métodos que não são responsabilidade dele.