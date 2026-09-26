[![PyPI](https://img.shields.io/pypi/v/wbjdbc)](https://pypi.org/project/wbjdbc/) [![PyPI - Downloads](https://img.shields.io/pypi/dm/wbjdbc)](https://pypi.org/project/wbjdbc/) [![Build Status](https://github.com/wanderbatistaf/wbjdbc/actions/workflows/publish-package.yml/badge.svg)](https://github.com/wanderbatistaf/wbjdbc/actions) ![License: MIT](https://img.shields.io/github/license/wanderbatistaf/wbjdbc) [![Último Commit](https://img.shields.io/github/last-commit/wanderbatistaf/wbjdbc)](https://github.com/wanderbatistaf/wbjdbc) [![GitHub issues](https://img.shields.io/github/issues/wanderbatistaf/wbjdbc)](https://github.com/wanderbatistaf/wbjdbc/issues) [![GitHub forks](https://img.shields.io/github/forks/wanderbatistaf/wbjdbc?style=social)](https://github.com/wanderbatistaf/wbjdbc) [![GitHub stars](https://img.shields.io/github/stars/wanderbatistaf/wbjdbc?style=social)](https://github.com/wanderbatistaf/wbjdbc) 
# 🧩 wbjdbc v2.0 — JDBC para Python (com suporte a Informix, Pooling, Async e Cache)

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
> cache de schema. `connect_to_db()` e `OptimizedJDBCConnection` continuam funcionando
> (agora delegando para o mesmo núcleo), mas emitem `DeprecationWarning`.

---

## ⚙️ Execução em Lote

```python
data = [(1, "Alice"), (2, "Bob")]
conn.execute_batch("INSERT INTO clientes VALUES (?, ?)", data)
```

---

## 🧵 Execução Assíncrona

```python
future = conn.execute_async("SELECT COUNT(*) FROM clientes")
print(future.result())
```

---

## 📈 Métricas e Logging

- Tempo médio, p50, p95 e p99 de queries  
- Estatísticas de pool, cache e conexões  
- Exportação em JSON (`get_metrics_collector().export_metrics(...)`) — hoje é
  JSON puro; um endpoint Prometheus nativo ainda está no roadmap.

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
```

---

## 🧾 Changelog

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

# 🇺🇸 wbjdbc v2.0 — JDBC for Python (Informix, Pooling, Async, Caching)

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

```python
future = conn.execute_async("SELECT COUNT(*) FROM customers")
print(future.result())
```

---

## 📊 Metrics & Logging

- Query latency (avg, p50, p95, p99)  
- Pool and cache statistics  
- JSON export (`get_metrics_collector().export_metrics(...)`) — a native Prometheus
  endpoint is on the roadmap, not implemented yet.  

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
```

---

## 🧾 Changelog

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
