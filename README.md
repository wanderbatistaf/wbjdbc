[![PyPI](https://img.shields.io/pypi/v/wbjdbc)](https://pypi.org/project/wbjdbc/) [![PyPI - Downloads](https://img.shields.io/pypi/dm/wbjdbc)](https://pypi.org/project/wbjdbc/) [![Build Status](https://github.com/wanderbatistaf/wbjdbc/actions/workflows/publish-package.yml/badge.svg)](https://github.com/wanderbatistaf/wbjdbc/actions) ![License: MIT](https://img.shields.io/github/license/wanderbatistaf/wbjdbc) [![Último Commit](https://img.shields.io/github/last-commit/wanderbatistaf/wbjdbc)](https://github.com/wanderbatistaf/wbjdbc) [![GitHub issues](https://img.shields.io/github/issues/wanderbatistaf/wbjdbc)](https://github.com/wanderbatistaf/wbjdbc/issues) [![GitHub forks](https://img.shields.io/github/forks/wanderbatistaf/wbjdbc?style=social)](https://github.com/wanderbatistaf/wbjdbc) [![GitHub stars](https://img.shields.io/github/stars/wanderbatistaf/wbjdbc?style=social)](https://github.com/wanderbatistaf/wbjdbc) 
# 🧩 wbjdbc v2.3 — JDBC para Python (com suporte a Informix, Pooling, Async e Cache)

wbjdbc é uma biblioteca JDBC moderna e otimizada para Python, agora com recursos de **pool de conexões**, **execução assíncrona**, **operações em lote**, **cache de metadados** e **mapeamento de tipos**.  
Totalmente compatível com versões anteriores (v1.x) e pronta para produção.

---

## 🚀 Principais Recursos

- 🗄️ **Multi-Banco** — Informix, MySQL e PostgreSQL com os drivers JDBC já embutidos.
- 🔄 **Pool de Conexões** — Gerencia múltiplas conexões com reaproveitamento automático.  
- ⚡ **Execução em Lote** — Até 10x mais rápido em inserções/atualizações massivas.  
- 🧵 **Execução Assíncrona** — Suporte a dezenas de queries simultâneas.  
- 🧠 **Cache de Metadados** — Reduz 95–99% das consultas de schema repetidas.  
- 🧩 **Mapeamento Automático de Tipos** — Conversão bidirecional entre JDBC e Python.  
- 🧮 **Métricas e Logging Estruturado** — Estatísticas detalhadas de desempenho.  
- ⚙️ **Configuração via `.env` ou Variáveis de Ambiente**  
- ✅ **Compatível 100% com versões anteriores**

---

## 🧰 Instalação

```bash
pip install wbjdbc
```

Também precisa de uma JVM no `PATH`/`JAVA_HOME` — o wbjdbc conversa com
Informix/MySQL/Postgres via driver JDBC de verdade, não é REST API disfarçada. Sem
JVM, sem conexão - mas pelo menos ele avisa em vez de te deixar adivinhando.

---

## 💡 Uso Básico

```python
from wbjdbc import connect_optimized

conn = connect_optimized(
    db_type="informix-sqli",
    host="server",
    database="db",
    user="user",
    password="pass",
    server="informix"
)

cursor = conn.cursor()
cursor.execute("SELECT * FROM clientes LIMIT 10")
rows = cursor.fetchdh()          # lista de dicts (coluna -> valor)
print(rows)

# Ou, direto no objeto de conexão:
rows = conn.execute_query("SELECT * FROM clientes LIMIT 10")

# Se preferir pandas:
cursor.execute("SELECT * FROM clientes LIMIT 10")
df = cursor.fetchdf()
```

> `connect_optimized()` é a API única recomendada — usa internamente `_DirectCursor`
> (JPype direto, sem o lock global do jaydebeapi), pool com pre-warm/statement cache e
> cache de schema. `connect_to_db()` e `OptimizedJDBCConnection` continuam a funcionar
> (agora delegando para o mesmo núcleo), mas emitem `DeprecationWarning`.

---

## ⚙️ Execução em Lote

```python
data = [(1, "Alice"), (2, "Bob")]
conn.execute_batch("INSERT INTO clientes VALUES (?, ?)", data)
```

---

## 🧵 Execução Assíncrona

`execute_async` executa uma query síncrona numa thread separada (bom para disparar queries em paralelo).
Para usar `async`/`await` verdadeiramente, sem bloquear o event loop em ponto nenhum (nem no `execute`, nem no `fetchall`), usa `async_db_conn`:

```python
future = conn.execute_async("SELECT COUNT(*) FROM clientes")
print(future.result())

# ou, de verdade assíncrono:
from wbjdbc.aio import async_db_conn

async def main():
    async with async_db_conn(db_type="informix-sqli", host="server", database="db",
                              user="user", password="pass", server="informix") as conn:
        cursor = conn.cursor()
        await cursor.execute("SELECT * FROM clientes LIMIT 10")
        rows = await cursor.fetchdh()
        print(rows)
```

---

## 🔁 Retry e Reconexão

Uma falha transitória na criação da conexão (base de dados a reiniciar, falha momentânea de rede) é repetida automaticamente com backoff, antes de desistir.
Nunca reexecuta uma query já enviada — só a etapa de conectar.

```python
conn = connect_optimized(
    db_type="informix-sqli", host="server", database="db", user="user",
    password="pass", server="informix",
    max_retries=3,      # default: WBJDBC_MAX_RETRIES (3)
    retry_delay=1.0,    # default: WBJDBC_RETRY_DELAY (1.0s, backoff linear)
)
```

---

## 🔒 SSL/TLS

```python
conn = connect_optimized(
    db_type="postgresql", host="server", database="db", user="user", password="pass",
    ssl_enabled=True,   # default: WBJDBC_SSL_ENABLED
    ssl_verify=True,    # default: WBJDBC_SSL_VERIFY
)
```

Para o Informix, o driver aceita `;SECURITY=SSL` no URL — os nomes de propriedade podem variar consoante a versão do driver/configuração do servidor, 
convém verificar a documentação do driver em uso antes de confiar nisto em produção.

---

## ⚠️ Exceções (DB-API 2.0)

Erros de query e de ligação são traduzidos para a hierarquia padrão do DB-API 2.0, com
`.sqlstate`/`.sqlcode` disponíveis para tratamento programático:

```python
from wbjdbc import IntegrityError, OperationalError

try:
    cursor.execute("INSERT INTO clientes (id) VALUES (?)", (1,))
except IntegrityError as e:
    print(f"violação de constraint: {e.sqlstate}")
except OperationalError:
    print("conexão perdida")
```

Hierarquia: `Error` → `InterfaceError` / `DatabaseError` → `DataError`,
`OperationalError`, `IntegrityError`, `InternalError`, `ProgrammingError`,
`NotSupportedError`.

---

## 📈 Métricas e Logging

- Tempo médio, p50, p95 e p99 de queries  
- Estatísticas de pool, cache e conexões  
- Exportação em JSON ou Prometheus (`get_metrics_collector().export_metrics(...)`,
  ativado via `WBJDBC_METRICS_PROMETHEUS=true`), ou diretamente o texto de exposição via
  `get_metrics_collector().export_prometheus()` numa rota sua:

```python
@app.route("/metrics")
def metrics():
    return get_metrics_collector().export_prometheus(), 200, \
        {"Content-Type": "text/plain; version=0.0.4"}
```

---

## 🔧 Configuração (.env)

```
DB_TYPE=informix-sqli
DB_HOST=server
DB_DATABASE=db
DB_USER=user
DB_PASSWORD=pass
POOL_MIN=10
POOL_MAX=20
CACHE_TTL=600
WBJDBC_MAX_RETRIES=3
WBJDBC_RETRY_DELAY=1.0
WBJDBC_SSL_ENABLED=false
WBJDBC_METRICS_PROMETHEUS=false
```

---

## 🧾 Changelog

Ver [CHANGELOG.md](CHANGELOG.md) para o histórico completo e detalhado.

**v2.0.0**
- Novo pool de conexões (thread-safe)
- Execução assíncrona e em lote
- Cache de metadados com invalidação
- Métricas detalhadas e logs estruturados
- Total compatibilidade com v1.x

---

## 🧑‍💻 Licença
MIT © 2025 Wander Freitas Batista

---

# 🇺🇸 wbjdbc v2.3 — JDBC for Python (Informix, Pooling, Async, Caching)

**wbjdbc** is a modern, optimized JDBC library for Python featuring **connection pooling**, **async queries**, **batch execution**, **metadata caching**, and **type mapping**.  
Fully production-ready and **100% backward compatible** with v1.x.

---

## 🚀 Main Features

- 🗄️ **Multi-Database** — Informix, MySQL and PostgreSQL, with JDBC drivers bundled in.
- 🔄 **Connection Pooling** — Efficient, thread-safe connection reuse  
- ⚡ **Batch Execution** — 5–10x faster inserts/updates  
- 🧵 **Async Query Execution** — 50–100 concurrent queries supported  
- 🧠 **Metadata Caching** — Up to 99% fewer repeated schema queries  
- 🧩 **Type Mapping** — Automatic JDBC ↔ Python conversions  
- 🧮 **Metrics & Structured Logging**  
- ⚙️ **Environment-based Configuration (.env)**  
- ✅ **100% Backward Compatible**

---

## 🧰 Installation

```bash
pip install wbjdbc
```

You'll also need a JVM on `PATH`/`JAVA_HOME` — wbjdbc talks to Informix/MySQL/Postgres
through real JDBC drivers, not a REST API in disguise. No JVM, no connection - but at
least it'll say so instead of leaving you to guess.

---

## 💡 Basic Usage

```python
from wbjdbc import connect_optimized

conn = connect_optimized(
    db_type="informix-sqli",
    host="server",
    database="db",
    user="user",
    password="pass",
    server="informix"
)

cursor = conn.cursor()
cursor.execute("SELECT * FROM customers LIMIT 10")
rows = cursor.fetchdh()          # list of dicts (column -> value)
print(rows)

# Or directly on the connection object:
rows = conn.execute_query("SELECT * FROM customers LIMIT 10")

# If you prefer pandas:
cursor.execute("SELECT * FROM customers LIMIT 10")
df = cursor.fetchdf()
```

> `connect_optimized()` is the single recommended API — it uses `_DirectCursor`
> internally (JPype-direct, bypassing jaydebeapi's global lock), a pool with
> pre-warming/statement caching, and schema caching. `connect_to_db()` and
> `OptimizedJDBCConnection` still work (now delegating to the same core), but raise a
> `DeprecationWarning`.

---

## ⚙️ Batch Execution

```python
data = [(1, "Alice"), (2, "Bob")]
conn.execute_batch("INSERT INTO customers VALUES (?, ?)", data)
```

---

## 🧵 Async Execution

`execute_async` runs a sync query on a worker thread (fine for firing off parallel
queries). For real `async`/`await` with nothing blocking the event loop - not
`execute`, not `fetchall` - use `async_db_conn`:

```python
future = conn.execute_async("SELECT COUNT(*) FROM customers")
print(future.result())

# or, truly async:
from wbjdbc.aio import async_db_conn

async def main():
    async with async_db_conn(db_type="informix-sqli", host="server", database="db",
                              user="user", password="pass", server="informix") as conn:
        cursor = conn.cursor()
        await cursor.execute("SELECT * FROM customers LIMIT 10")
        rows = await cursor.fetchdh()
        print(rows)
```

---

## 🔁 Retry & Reconnect

A transient failure establishing the connection (database restarting, brief network
blip) is retried automatically with backoff before giving up. It only ever retries
the connect step - never a query already sent to the server.

```python
conn = connect_optimized(
    db_type="informix-sqli", host="server", database="db", user="user",
    password="pass", server="informix",
    max_retries=3,      # default: WBJDBC_MAX_RETRIES (3)
    retry_delay=1.0,    # default: WBJDBC_RETRY_DELAY (1.0s, linear backoff)
)
```

---

## 🔒 SSL/TLS

```python
conn = connect_optimized(
    db_type="postgresql", host="server", database="db", user="user", password="pass",
    ssl_enabled=True,   # default: WBJDBC_SSL_ENABLED
    ssl_verify=True,    # default: WBJDBC_SSL_VERIFY
)
```

For Informix, the driver accepts `;SECURITY=SSL` on the URL - property names can vary
by driver version/server configuration, so check the docs for the driver version
you're running before relying on this in production.

---

## ⚠️ Exceptions (DB-API 2.0)

Query and connection errors are translated into the standard DB-API 2.0 hierarchy,
with `.sqlstate`/`.sqlcode` available for programmatic handling:

```python
from wbjdbc import IntegrityError, OperationalError

try:
    cursor.execute("INSERT INTO customers (id) VALUES (?)", (1,))
except IntegrityError as e:
    print(f"constraint violation: {e.sqlstate}")
except OperationalError:
    print("connection lost")
```

Hierarchy: `Error` → `InterfaceError` / `DatabaseError` → `DataError`,
`OperationalError`, `IntegrityError`, `InternalError`, `ProgrammingError`,
`NotSupportedError`.

---

## 📊 Metrics & Logging

- Query latency (avg, p50, p95, p99)  
- Pool and cache statistics  
- JSON or Prometheus export (`get_metrics_collector().export_metrics(...)`, toggled
  via `WBJDBC_METRICS_PROMETHEUS=true`), or the raw exposition text straight from
  `get_metrics_collector().export_prometheus()` in your own route:

```python
@app.route("/metrics")
def metrics():
    return get_metrics_collector().export_prometheus(), 200, \
        {"Content-Type": "text/plain; version=0.0.4"}
```

---

## 🔧 Configuration Example (.env)

```
DB_TYPE=informix-sqli
DB_HOST=server
DB_DATABASE=db
DB_USER=user
DB_PASSWORD=pass
POOL_MIN=10
POOL_MAX=20
CACHE_TTL=600
WBJDBC_MAX_RETRIES=3
WBJDBC_RETRY_DELAY=1.0
WBJDBC_SSL_ENABLED=false
WBJDBC_METRICS_PROMETHEUS=false
```

---

## 🧾 Changelog

See [CHANGELOG.md](CHANGELOG.md) for the full, detailed history.

**v2.0.0**
- Thread-safe connection pool  
- Async & batch execution  
- Metadata cache with invalidation  
- Detailed metrics and structured logs  
- Full backward compatibility with v1.x  

---

## 🧑‍💻 License
MIT © 2025 Wander Freitas Batista 

Made by a Brazilian Developer 🇧🇷
