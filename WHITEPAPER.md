# Cell — Whitepaper

> *"Vesmír je zákon. Země je život."*

---

## 1. Vize

Cell je self-improving AI agent — systém schopný autonomního fungování, rozšiřování vlastních schopností a dlouhodobé paměti. Na rozdíl od statických agentů (jako Hermes Agent nebo OpenClaw) si Cell může přepisovat vlastní zdrojový kód, vytvářet nové funkce a plánovat vlastní úlohy — vše v rámci pevně daných hranic, které zajišťuje neměnné jádro systému.

Základní analogie: **Vesmír a Země.**

- **Vesmír (Core)** — neměnné zákony, fyzika systému. Nezáleží na tom, co se děje uvnitř. Nelze ho přepsat.
- **Země (Brain)** — živá civilizace. Roste, mění se, může sama sebe zničit, ale také sama sebe přestavět.

---

## 2. Architektura

```
┌─────────────────────────────────────────────────┐
│                     CORE                        │
│                                                 │
│  ┌──────────┐  ┌──────────┐  ┌───────────────┐ │
│  │  Chat    │  │ Scheduler│  │Process Manager│ │
│  │  Module  │  │          │  │  (try-except) │ │
│  └────┬─────┘  └────┬─────┘  └───────┬───────┘ │
│       │              │                │         │
│  ┌────▼──────────────▼────────────────▼───────┐ │
│  │              Context Store                 │ │
│  │         (permanentní, blockchain-like)     │ │
│  └────────────────────┬───────────────────────┘ │
│                       │                         │
│  ┌────────────────────▼───────────────────────┐ │
│  │                  Proxy                     │ │
│  │       (LLM API komunikace, klíče)          │ │
│  └────────────────────┬───────────────────────┘ │
└───────────────────────┼─────────────────────────┘
                        │
┌───────────────────────▼─────────────────────────┐
│                    BRAIN                        │
│                                                 │
│  ┌─────────────────────────────────────────┐   │
│  │            Hlavní smyčka                │   │
│  │  vstup → LLM → function calling → výstup│   │
│  └─────────────────────────────────────────┘   │
│                                                 │
│  ┌─────────────────┐  ┌──────────────────────┐ │
│  │ Standardní      │  │   self_improve()     │ │
│  │ funkce (lokální)│  │  → přes Core         │ │
│  └─────────────────┘  └──────────────────────┘ │
│                                                 │
│  /brain/                                        │
│    brain.py         ← hlavní logika             │
│    functions/       ← self-generované funkce    │
│    assets/          ← libovolné zdroje          │
│    backup/          ← zálohy předchozích verzí  │
└─────────────────────────────────────────────────┘
```

---

## 3. Komponenty

### 3.1 Core

Core je **BIOS systému** — neměnná vrstva, kterou brain nemůže za žádných okolností přepsat. Obsahuje několik modulů:

#### Chat Module
Uživatel komunikuje výhradně přes Core. Zprávy se přidávají do kontextu a při každém volání se celý kontext předává Brainu jako vstup.

#### Scheduler
Brain může přes Core registrovat časované úlohy. Core v daný čas nebo interval spustí Brain s předem definovaným vstupem a systémovou zprávou, která označuje, že jde o plánovanou úlohu (nikoli přímý uživatelský požadavek).

```
Příklad systémové zprávy pro scheduled task:
"[SCHEDULED TASK] Toto je automaticky spuštěná úloha: <popis úlohy>"
```

#### Process Manager
Core spouští Brain v ochranném try-except bloku:

1. Brain se spustí.
2. Pokud proběhne bez chyby → výstup se zpracuje normálně.
3. Pokud Brain spadne (syntaktická chyba, výjimka, špatně vygenerovaný kód):
   - Core provede **rollback** na poslední funkční zálohu z `brain/backup/`.
   - Chyba (traceback, logy) se zapíše do kontextu jako systémová zpráva.
   - Při příštím běhu LLM ví, co se pokazilo, a může to opravit.

#### Context Store
Kontext je **permanentní a append-only** — historické kroky nelze přepsat (blockchain-like princip). Každá verze kontextu musí být konzistentní s předchozí. Kontext obsahuje:
- historii konverzace s uživatelem,
- systémové zprávy (errory, scheduled task notifikace),
- výstupy z function callingu.

> *Poznámka: Limit tokenů se bude řešit kompresí kontextu v pozdější fázi vývoje.*

#### Proxy
Veškerá komunikace s DeepSeek API probíhá výhradně přes Proxy modul v Core. Brain nikdy nevidí API klíč — volá pouze `proxy.get(...)`, `proxy.post(...)` apod. Proxy přeloží volání na skutečný HTTP request.

---

### 3.2 Brain

Brain je **živá část systému** — složka kódu, kterou lze za běhu přepisovat. Brain je napojen na LLM (DeepSeek) přes Proxy a řídí se vlastní logikou, kterou si sám navrhuje.

#### Hlavní smyčka

```
vstup (z Core)
  → zpracování v brain.py
    → volání LLM (přes Proxy)
      → function calling
        → výstup
→ zpět do Core (uložení do kontextu, verifikace)
```

#### Function Calling

Brain může volat funkce dvěma způsoby:

| Typ funkce | Kde se vykoná | Příklad |
|---|---|---|
| Standardní | Přímo v Brain | `get_weather()`, `search_web()` |
| `self_improve()` | Přes Core | Přepis zdrojového kódu Brain |

Standardní funkce si Brain generuje sám pomocí `self_improve()` a ukládá do `brain/functions/`.

#### self_improve()

Klíčová funkce celého systému. Když LLM rozhodne, že chce novou schopnost nebo opravit chybu:

1. Zavolá `self_improve()` s popisem změny / novým kódem.
2. Volání se **přesměruje do Core** (Brain ji nemůže vykonat sám).
3. Core provede změnu v `brain/` složce.
4. Před změnou uloží aktuální stav do `brain/backup/`.
5. Pokud nová verze selže → automatický rollback (viz Process Manager).

Možné varianty `self_improve()`:
- Vytvoření nové funkce
- Úprava existující funkce
- Přepis celého `brain.py`

---

## 4. Bezpečnostní model

| Pravidlo | Důvod |
|---|---|
| Brain nemůže přepsat Core | Core je zákon — jeho porušení by bylo konec systému |
| API klíče jsou pouze v Core (Proxy) | Brain nesmí mít přístup k přihlašovacím údajům |
| `self_improve()` prochází Core | Core může v budoucnu přidat validaci, schválení, sandbox |
| Kontext je append-only | Zabraňuje manipulaci s historií (podvody, reinterpretace) |
| Backup před každou změnou | Garantuje funkční stav i po chybě |

> *Rozšířená bezpečnostní vrstva (sandboxing, izolace procesů, whitelisting systémových volání) bude řešena v pozdější fázi.*

---

## 5. Technický stack

| Komponenta | Technologie |
|---|---|
| Jazyk | Python |
| LLM | DeepSeek API |
| Komunikace s LLM | Proxy modul (Core) |
| Persistence kontextu | Soubor / databáze (TBD) |
| Plánování úloh | Scheduler v Core |

---

## 6. Struktura projektu

```
cell-2/
├── core/
│   ├── core.py              ← hlavní orchestrátor
│   ├── chat.py              ← chat modul
│   ├── scheduler.py         ← správa časovaných úloh
│   ├── process_manager.py   ← spouštění brain, try-except, rollback
│   ├── proxy.py             ← komunikace s DeepSeek API
│   └── context_store.py     ← správa permanentního kontextu
│
├── brain/
│   ├── brain.py             ← hlavní logika agenta
│   ├── functions/           ← self-generované funkce
│   ├── assets/              ← libovolné zdroje
│   └── backup/              ← zálohy předchozích verzí
│
├── WHITEPAPER.md
└── CLAUDE.md
```

---

## 7. Životní cyklus jednoho běhu

```
1. Trigger (uživatel / scheduler / error recovery)
2. Core sestaví vstup: kontext + systémové zprávy + nový vstup
3. Process Manager spustí Brain (try-except)
4. Brain zavolá LLM přes Proxy
5. LLM rozhodne o akci:
   a. Odpověď uživateli → výstup do Core
   b. Volání standardní funkce → lokálně v Brain → výstup do Core
   c. Volání self_improve() → Core provede změnu → Brain pokračuje
6. Core verifikuje výstup, uloží do kontextu
7. Výstup se zobrazí uživateli (nebo se uloží jako výsledek scheduled tasku)
```

---

## 8. Budoucí rozvoj

- **Komprese kontextu** — automatické shrnutí starší historie pro řešení token limitu
- **Rozšířená bezpečnostní vrstva** — sandbox pro brain, whitelist systémových volání
- **Multi-brain** — více specializovaných Brain modulů koordinovaných Core
- **Schvalovací mechanismus** — volitelné potvrzení uživatele před `self_improve()`
- **Monitoring dashboard** — přehled stavu, verzí, scheduled tasků

---

*Cell — systém, který roste.*
