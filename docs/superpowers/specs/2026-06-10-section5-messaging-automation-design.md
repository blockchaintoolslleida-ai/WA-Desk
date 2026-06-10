# Secció 5 — Configuració de Missatgeria (Automatitzacions)

**Data:** 2026-06-10
**Estat:** Especificació aprovada
**Àmbit:** Admin Panel — Nova secció "Automatitzacions"

---

## 1. Resum

Nova secció al panell d'administració (`/admin`) que permet als tenants configurar regles d'auto-resposta i assignació automàtica d'agents. Les regles s'organitzen en **5 categories fixes** que s'avaluen en ordre seqüencial. La primera categoria que fa match dispara la seva acció i atura el pipeline.

---

## 2. Arquitectura: Motor per Categories

### 2.1 Pipeline d'avaluació

Quan arriba un missatge entrant (webhook WhatsApp → inserció a DB):

```
📥 Missatge entrant
    ↓
[1. Salutació]      → ¿Primer contacte? → Auto-resposta de benvinguda
    ↓ (no match)
[2. Horaris]         → ¿Hora actual dins d'alguna franja del dia? → Resposta "en horari" o "fora d'horari"
    ↓ (no match)
[3. Paraules clau]   → ¿El text conté alguna paraula clau? → Resposta FAQ
    ↓ (no match)
[4. Assignació]      → ¿Auto-assignació activada? → Assignar agent per round-robin
    ↓ (no match)
[5. Fallback]        → Regla catch-all (sempre dispara si existeix)
    ↓
📤 Acció executada (o res si cap categoria té regles actives)
```

**Regla d'or:** La primera categoria que fa match **atura el pipeline**. Si una regla de Salutació dispara, no s'avaluen Horaris ni Paraules clau.

### 2.2 Fitxers afectats

| Capa | Fitxer | Acció |
|---|---|---|
| **DB** | `supabase_automation_rules.sql` | Nou — migració per crear taules |
| **Backend** | `backend/routers/automation.py` | Nou — router amb CRUD de regles, horari, assignació |
| **Backend** | `backend/services/automation_engine.py` | Nou — motor d'avaluació de regles |
| **Backend** | `backend/routers/webhook.py` | Modificar — cridar el motor després d'inserir missatge |
| **Backend** | `backend/server.py` | Modificar — registrar el nou router |
| **Frontend** | `frontend/src/pages/admin/AutomationSection.js` | Nou — component principal |
| **Frontend** | `frontend/src/pages/AdminPage.js` | Modificar — afegir nav item + import |
| **Frontend** | `frontend/src/lib/api.js` | Modificar — afegir `automationApi` |
| **Frontend** | `frontend/src/lib/i18n.js` | Modificar — afegir claus `admin.automations.*` (CA/ES/EN) |

---

## 3. Model de Dades

### 3.1 Taula: `automation_rules`

```sql
CREATE TABLE automation_rules (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  category TEXT NOT NULL CHECK (category IN ('greeting', 'schedule', 'keywords', 'fallback')),
  name TEXT NOT NULL,
  is_active BOOLEAN DEFAULT true,
  priority INTEGER NOT NULL DEFAULT 1,
  
  -- Trigger (JSONB, específic per categoria)
  trigger_config JSONB NOT NULL DEFAULT '{}',
  
  -- Action
  response_text TEXT,
  
  -- Limits
  delay_seconds INTEGER DEFAULT 0,
  daily_limit INTEGER,  -- NULL = il·limitat
  
  created_at TIMESTAMPTZ DEFAULT now(),
  updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_automation_rules_tenant ON automation_rules(tenant_id, category, priority);
```

### 3.2 Estructura de `trigger_config` per categoria

| Categoria | trigger_config |
|---|---|
| **greeting** | `{}` — sense opcions, sempre és "primer contacte" |
| **schedule** | `{"type": "outside_hours"}` o `{"type": "inside_hours"}` |
| **keywords** | `{"keywords": ["preu", "pressupost", "precio"], "match_mode": "any"}` |
| **fallback** | `{}` — sense opcions, sempre dispara (catch-all) |

*Nota:* `match_mode` sempre és `"any"` (conté almenys una paraula). Case-insensitive. Si en el futur es vol `"all"`, s'afegeix.

### 3.3 Taula: `business_hours`

```sql
CREATE TABLE business_hours (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  timezone TEXT NOT NULL DEFAULT 'Europe/Madrid',
  
  -- Cada dia té 0+ franges horàries
  schedule JSONB NOT NULL DEFAULT '{}',
  -- Format: { "mon": [["09:00","13:00"],["16:00","19:00"]], "tue": [...], ... }
  
  created_at TIMESTAMPTZ DEFAULT now(),
  updated_at TIMESTAMPTZ DEFAULT now(),
  
  UNIQUE(tenant_id)
);
```

### 3.4 Taula: `assignment_config`

```sql
CREATE TABLE assignment_config (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  is_enabled BOOLEAN DEFAULT false,
  timeout_minutes INTEGER DEFAULT 5,
  strategy TEXT NOT NULL DEFAULT 'round_robin',  -- 'round_robin' | 'least_conversations'
  agent_pool UUID[] DEFAULT '{}',  -- array de profile.id dels agents participants
  created_at TIMESTAMPTZ DEFAULT now(),
  updated_at TIMESTAMPTZ DEFAULT now(),
  
  UNIQUE(tenant_id)
);
```

### 3.5 Taula: `automation_logs`

```sql
CREATE TABLE automation_logs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  rule_id UUID REFERENCES automation_rules(id) ON DELETE SET NULL,
  conversation_id UUID,
  message_id UUID,
  category TEXT,
  triggered_at TIMESTAMPTZ DEFAULT now(),
  response_preview TEXT  -- primers 100 chars de la resposta enviada
);

CREATE INDEX idx_automation_logs_tenant_date ON automation_logs(tenant_id, triggered_at);
CREATE INDEX idx_automation_logs_rule ON automation_logs(rule_id, triggered_at);
```

Aquesta taula serveix per:
- Fer complir el `daily_limit` de cada regla (contar quants logs té la regla avui)
- Auditoria bàsica de quines regles s'han disparat

---

## 4. API Endpoints

### 4.1 Automation Rules CRUD

**Base:** `/api/admin/automation/rules`

| Mètode | Path | Descripció |
|---|---|---|
| `GET` | `/` | Llistar totes les regles del tenant, ordenades per categoria i prioritat |
| `POST` | `/` | Crear nova regla |
| `PUT` | `/{rule_id}` | Actualitzar regla existent |
| `DELETE` | `/{rule_id}` | Eliminar regla |
| `PATCH` | `/{rule_id}/toggle` | Activar/desactivar regla |
| `PUT` | `/reorder` | Reordenar prioritats dins d'una categoria (rep array de `{id, priority}`) |

### 4.2 Business Hours

**Base:** `/api/admin/automation/business-hours`

| Mètode | Path | Descripció |
|---|---|---|
| `GET` | `/` | Obtenir horari laboral del tenant |
| `PUT` | `/` | Guardar/actualitzar horari laboral |

### 4.3 Assignment Config

**Base:** `/api/admin/automation/assignment`

| Mètode | Path | Descripció |
|---|---|---|
| `GET` | `/` | Obtenir configuració d'assignació |
| `PUT` | `/` | Guardar/actualitzar configuració |

### 4.4 Logs (opcional, per debug)

| Mètode | Path | Descripció |
|---|---|---|
| `GET` | `/api/admin/automation/logs?limit=50` | Últims logs d'auto-resposta del tenant |

### 4.5 Payloads

**POST/PUT `/rules`**:
```json
{
  "category": "keywords",
  "name": "FAQ Preus",
  "is_active": true,
  "priority": 1,
  "trigger_config": {
    "keywords": ["preu", "pressupost", "precio"],
    "match_mode": "any"
  },
  "response_text": "Hola! Els nostres preus varien segons el producte. Vols que un agent et faci un pressupost personalitzat?",
  "delay_seconds": 0,
  "daily_limit": null
}
```

**PUT `/business-hours`**:
```json
{
  "timezone": "Europe/Madrid",
  "schedule": {
    "mon": [["09:00", "13:00"], ["16:00", "19:00"]],
    "tue": [["09:00", "13:00"], ["16:00", "19:00"]],
    "wed": [["09:00", "13:00"], ["16:00", "19:00"]],
    "thu": [["09:00", "13:00"], ["16:00", "19:00"]],
    "fri": [["09:00", "15:00"]],
    "sat": [],
    "sun": []
  }
}
```

**PUT `/assignment`**:
```json
{
  "is_enabled": true,
  "timeout_minutes": 5,
  "strategy": "round_robin",
  "agent_pool": ["uuid-agent-1", "uuid-agent-2", "uuid-agent-3"]
}
```

---

## 5. Motor d'Avaluació (`services/automation_engine.py`)

### 5.1 Funció principal

```python
async def evaluate_and_execute(tenant_id: str, conversation_id: str, message: dict) -> Optional[dict]:
    """
    Avalua les regles d'auto-resposta per a un missatge entrant.
    Retorna dict amb el resultat o None si cap regla dispara.
    """
```

### 5.2 Pseudocodi

```
1. Obtenir totes les regles actives del tenant, ordenades per category_order, priority
2. Per cada categoria (en ordre 1→5):
   a. Obtenir regles actives d'aquesta categoria (ordenades per prioritat)
   b. Per cada regla:
      - Comprovar daily_limit (si n'hi ha): contar automation_logs d'avui
      - Si s'ha excedit el límit, saltar
      - Avaluar trigger:
        - greeting: comprovar si és el primer missatge del contacte
        - schedule: comprovar si l'hora actual és dins/fora de business_hours
        - keywords: comprovar si el text conté alguna keyword
        - fallback: sempre true (catch-all)
      - Si match:
        - Si delay_seconds > 0: programar enviament diferit (background task)
        - Si delay_seconds == 0: enviar immediatament
        - Registrar a automation_logs
        - Retornar resultat
   c. Si cap regla d'aquesta categoria dispara, passar a la següent
3. Si cap categoria dispara, retornar None
```

### 5.3 Lògica "Fora d'horari"

```python
def is_inside_business_hours(schedule: dict, timezone_str: str) -> bool:
    """
    Retorna True si l'hora actual cau dins d'alguna franja del dia actual.
    - Si el dia no té franges → fora d'horari
    - Si l'hora actual està entre l'inici i el final de qualsevol franja → dins
    - Altrament → fora
    """
```

### 5.4 Assignació automàtica

Quan la categoria 4 (Assignació) està activa:
1. Comprovar `assignment_config.is_enabled`
2. Si la conversa NO té agent assignat després de `timeout_minutes` → assignar
3. Seleccionar agent de `agent_pool` segons l'estratègia (`round_robin` o `least_conversations`)
4. Actualitzar `conversations.assigned_agent_id`
5. Per round-robin: usar un comptador atòmic o consultar l'últim assignat

---

## 6. Integració amb Webhook

Al fitxer `backend/routers/webhook.py`, després d'inserir el missatge entrant a la DB:

```python
from services.automation_engine import evaluate_and_execute

# Després d'inserir el missatge...
if message_direction == 'incoming':
    try:
        result = await evaluate_and_execute(tenant_id, conversation_id, message_data)
        if result:
            logger.info(f"Automation fired: {result['category']} → {result['rule_name']}")
    except Exception as e:
        logger.error(f"Automation engine error: {e}")
```

---

## 7. Frontend — Components

### 7.1 `AutomationSection.js`

Component principal amb 3 pestanyes internes:
- **Pestanya 1:** `RulesTab` — Les 5 categories amb les seves regles
- **Pestanya 2:** `BusinessHoursTab` — Configuració horària setmanal
- **Pestanya 3:** `AssignmentTab` — Configuració d'assignació automàtica

### 7.2 Pestanyes internes

```
AutomationSection
├── Pestanya "Regles d'auto-resposta"
│   ├── CategoryCard (×5, un per categoria: greeting, schedule, keywords, assignment, fallback)
│   │   ├── Capçalera amb icona, nom, botó "+ Afegir regla"
│   │   └── Llista de RuleRow (ordenades per prioritat)
│   │       ├── Prioritat (nº)
│   │       ├── Nom de la regla
│   │       ├── Resum del trigger
│   │       ├── Toggle on/off
│   │       ├── Botó editar ✏️
│   │       └── Botó eliminar 🗑️
│   └── Modal "RuleEditor" (crear/editar regla)
│       ├── Nom
│       ├── Toggle actiu
│       ├── Prioritat (selector de posició)
│       ├── Trigger (varia segons categoria)
│       │   ├── greeting: sense opcions
│       │   ├── schedule: selector "Fora d'horari" / "En horari laboral"
│       │   ├── keywords: llista de xips + input per afegir
│       │   └── fallback: sense opcions
│       ├── Text de resposta (textarea amb marcadores)
│       ├── Delay (segons)
│       ├── Límit diari (opcional)
│       └── Botons Guardar / Cancel·lar
│
├── Pestanya "Horari laboral"
│   ├── Selector de zona horària
│   ├── Graella de 7 dies (Dl-Dg)
│   │   └── Per cada dia:
│   │       ├── Toggle dia actiu/tancat
│   │       ├── Llista de franges (inici—fi) editables
│   │       └── Botó "+ Afegir franja"
│   └── Botó Guardar
│
└── Pestanya "Assignació automàtica"
    ├── Toggle mestre (ON/OFF)
    ├── Timeout (minuts)
    ├── Estratègia (round-robin / menys converses)
    ├── Pool d'agents (checkboxes)
    └── Botó Guardar
```

### 7.3 `AdminPage.js` — Canvis

Afegir al `NAV_ITEMS`:
```js
{ id: 'automation', icon: Lightning, key: 'admin.nav.automation' },
```

Afegir al render:
```jsx
{section === 'automation' && <AutomationSection t={t} locale={locale} />}
```

### 7.4 `api.js` — Nou `automationApi`

```js
export const automationApi = {
  // Rules
  getRules: () => api.get('/admin/automation/rules'),
  createRule: (data) => api.post('/admin/automation/rules', data),
  updateRule: (id, data) => api.put(`/admin/automation/rules/${id}`, data),
  deleteRule: (id) => api.delete(`/admin/automation/rules/${id}`),
  toggleRule: (id) => api.patch(`/admin/automation/rules/${id}/toggle`),
  reorderRules: (data) => api.put('/admin/automation/rules/reorder', data),
  // Business Hours
  getBusinessHours: () => api.get('/admin/automation/business-hours'),
  updateBusinessHours: (data) => api.put('/admin/automation/business-hours', data),
  // Assignment
  getAssignment: () => api.get('/admin/automation/assignment'),
  updateAssignment: (data) => api.put('/admin/automation/assignment', data),
  // Logs
  getLogs: (limit = 50) => api.get(`/admin/automation/logs?limit=${limit}`),
};
```

---

## 8. i18n — Claus de traducció

Totes les claus sota el prefix `admin.automations.*`:

```js
// CA (català)
'admin.nav.automation': 'Automatitzacions',
'admin.automation.title': 'Automatitzacions',
'admin.automation.tab_rules': 'Regles d\'auto-resposta',
'admin.automation.tab_hours': 'Horari laboral',
'admin.automation.tab_assignment': 'Assignació automàtica',

// Categories
'admin.automation.cat_greeting': 'Salutació',
'admin.automation.cat_greeting_desc': 'Primer contacte',
'admin.automation.cat_schedule': 'Horaris',
'admin.automation.cat_schedule_desc': 'Fora d\'horari / En horari',
'admin.automation.cat_keywords': 'Paraules clau',
'admin.automation.cat_keywords_desc': 'Respostes per keyword',
'admin.automation.cat_assignment': 'Assignació',
'admin.automation.cat_assignment_desc': 'Auto-assignació d\'agents',
'admin.automation.cat_fallback': 'Fallback',
'admin.automation.cat_fallback_desc': 'Resposta per defecte',

// Rule editor
'admin.automation.rule_name': 'Nom de la regla',
'admin.automation.rule_active': 'Activa',
'admin.automation.rule_priority': 'Prioritat',
'admin.automation.rule_trigger': 'Disparador',
'admin.automation.rule_response': 'Missatge de resposta',
'admin.automation.rule_delay': 'Delay (segons)',
'admin.automation.rule_daily_limit': 'Límit diari',
'admin.automation.rule_unlimited': 'Il·limitat',
'admin.automation.add_rule': 'Afegir regla',
'admin.automation.edit_rule': 'Editar regla',
'admin.automation.save_rule': 'Guardar regla',
'admin.automation.cancel': 'Cancel·lar',
'admin.automation.add_keyword': 'Afegir',
'admin.automation.keyword_placeholder': 'Nova paraula clau...',
'admin.automation.markers_hint': 'Marcadors disponibles:',

// Schedule
'admin.automation.timezone': 'Zona horària',
'admin.automation.day_mon': 'Dilluns',
'admin.automation.day_tue': 'Dimarts',
'admin.automation.day_wed': 'Dimecres',
'admin.automation.day_thu': 'Dijous',
'admin.automation.day_fri': 'Divendres',
'admin.automation.day_sat': 'Dissabte',
'admin.automation.day_sun': 'Diumenge',
'admin.automation.closed': 'Tancat',
'admin.automation.add_slot': 'Afegir franja',
'admin.automation.save_hours': 'Guardar horari',
'admin.automation.morning': 'matí',
'admin.automation.afternoon': 'tarda',

// Assignment
'admin.automation.assignment_enabled': 'Assignació automàtica',
'admin.automation.assignment_desc': 'Quan s\'activa, els nous missatges s\'assignen automàticament',
'admin.automation.assignment_timeout': 'Timeout d\'assignació (minuts)',
'admin.automation.assignment_timeout_hint': 'Si cap agent assigna la conversa en aquest temps, s\'assigna automàticament',
'admin.automation.assignment_strategy': 'Estratègia',
'admin.automation.strategy_round_robin': 'Round-robin (per torns)',
'admin.automation.strategy_least': 'Menys converses obertes',
'admin.automation.assignment_agents': 'Agents participants',
'admin.automation.assignment_disabled_warn': 'L\'assignació automàtica està desactivada. Totes les converses requereixen assignació manual.',
'admin.automation.save_assignment': 'Guardar configuració',
```

Les traduccions ES i EN segueixen el mateix patró, afegint els blocs corresponents a `translations.es` i `translations.en`.

---

## 9. Pla d'Implementació (ordre)

1. **Migració SQL** — Crear les 4 taules noves (automation_rules, business_hours, assignment_config, automation_logs)
2. **Backend: Automation Engine** — `services/automation_engine.py` amb la funció `evaluate_and_execute`
3. **Backend: Automation Router** — `routers/automation.py` amb tots els endpoints CRUD
4. **Backend: Integració webhook** — Cridar el motor des de `routers/webhook.py` després d'inserir missatges entrants
5. **Backend: Server** — Registrar el nou router
6. **Frontend: API client** — Afegir `automationApi` a `api.js`
7. **Frontend: i18n** — Afegir les claus CA/ES/EN a `i18n.js`
8. **Frontend: AutomationSection** — Component principal amb 3 pestanyes + RuleEditor modal
9. **Frontend: AdminPage** — Afegir nav item i renderitzar la secció
10. **Tests** — Tests d'integració per al motor de regles i els endpoints

---

## 10. Límits i consideracions

- **Fallback**: Només 1 regla permesa a la categoria fallback. Intentar crear-ne més retorna error 400.
- **Fallback**: Només 1 regla permesa a la categoria fallback. Intentar crear-ne més retorna error 400.
- **Daily limit**: Es compta sobre `automation_logs` filtrant per `rule_id` i `triggered_at` del dia actual en la zona horària del tenant (definida a `business_hours.timezone`). Si s'excedeix, la regla es salta silenciosament i es logueja.
- **Primer contacte**: Un contacte es considera "primer contacte" si no té cap conversa prèvia al sistema (0 files a `conversations` amb el seu `contact_id`). No aplica a converses noves d'un contacte existent.
- **Delay**: L'enviament diferit usa `asyncio.create_task` amb `asyncio.sleep`. No persisteix entre reinicis del servidor (és acceptable per al MVP; en el futur es pot migrar a Celery/Redis).
- **Marcadores**: `{{agent_name}}`, `{{business_name}}`, `{{contact_name}}` es substitueixen en el moment d'enviar. Si no hi ha valor disponible (ex: conversa sense agent assignat), s'usa "el nostre equip" / "nuestro equipo" / "our team" segons l'idioma del tenant.
- **Round-robin**: Es guarda un comptador per tenant a `assignment_config` (o es dedueix de l'últim assignat a `conversations`).
- **Paraules clau**: Coincidència case-insensitive amb `contains` (no regex ni paraula completa). El missatge ha de contenir almenys una de les paraules. Ex: "preu" fa match amb "Quin preu té?" i amb "PREU si us plau".
