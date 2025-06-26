[![PyPI](https://img.shields.io/pypi/v/wbjdbc)](https://pypi.org/project/wbjdbc/) [![PyPI - Downloads](https://img.shields.io/pypi/dm/wbjdbc)](https://pypi.org/project/wbjdbc/) [![Build Status](https://github.com/wanderbatistaf/wbjdbc/actions/workflows/publish-package.yml/badge.svg)](https://github.com/wanderbatistaf/wbjdbc/actions) ![License: MIT](https://img.shields.io/github/license/wanderbatistaf/wbjdbc) [![Último Commit](https://img.shields.io/github/last-commit/wanderbatistaf/wbjdbc)](https://github.com/wanderbatistaf/wbjdbc) [![GitHub issues](https://img.shields.io/github/issues/wanderbatistaf/wbjdbc)](https://github.com/wanderbatistaf/wbjdbc/issues) [![GitHub forks](https://img.shields.io/github/forks/wanderbatistaf/wbjdbc?style=social)](https://github.com/wanderbatistaf/wbjdbc) [![GitHub stars](https://img.shields.io/github/stars/wanderbatistaf/wbjdbc?style=social)](https://github.com/wanderbatistaf/wbjdbc) 
# wbjdbc (v1.2.0)

### 🌍 **Português** | 🇺🇸 **English**

---

## 📌 O que é o `wbjdbc`?

**wbjdbc** é uma biblioteca Python que simplifica a configuração e o uso do **JDBC** e da **JVM**, especialmente para conexões com bancos de dados **Informix** e **MongoDB**. A biblioteca gerencia drivers internamente, garantindo inicialização automática da JVM e configuração simplificada das conexões.

### 🚀 **Principais recursos**:
- **Inicialização automática da JVM** com detecção de `JAVA_HOME`.
- **Suporte para múltiplos drivers JDBC**:
  - **Informix JDBC Driver** (`jdbc-4.50.10.1.jar`)
  - **MongoDB BSON Driver** (`bson-3.8.0.jar`)
- **Gerenciamento interno de dependências**, incluindo suporte para **JPype1**.
- **Modo Debug** para facilitar troubleshooting.
- **Método `execute_query()`** retornando lista de dicionários.
- **Compatível com Python 3.8+**.

---

## 📥 Instalação
Para instalar a biblioteca via **PyPI**, execute:

```sh
pip install wbjdbc
```

---

## 🛠️ Uso

### ✅ **Inicializando a JVM**
A JVM pode ser inicializada automaticamente pelo `wbjdbc`, mas você também pode inicializá-la manualmente:

```python
from wbjdbc import start_jvm

start_jvm()
```

Isso garantirá que a JVM esteja disponível antes de realizar conexões via JDBC.

---

### 📡 **Conectando-se ao Informix**

Aqui está um exemplo de como usar o **wbjdbc** para se conectar a um banco de dados **Informix**:

```python
from wbjdbc import connect_to_db

# Parâmetros de conexão
conn = connect_to_db(
    db_type="informix-sqli",
    host="meu-servidor",
    database="minha_base",
    user="meu_usuario",
    password="minha_senha",
    port=1526,
    server="meu_informix_server"
)

# Criando cursor e executando uma consulta
cursor = conn.cursor()
cursor.execute("SELECT * FROM minha_tabela")
resultados = cursor.fetchall()

# Exibindo resultados
for linha in resultados:
    print(linha)

# Fechando conexão
cursor.close()
conn.close()
```
---
### 🧩 Métodos adicionais do cursor
O objeto retornado por conn.cursor() implementa métodos similares ao padrão DB-API:

> 🔎 .description
Retorna metadados das colunas da última consulta executada:

```python
cursor.execute("SELECT id, nome FROM produtos")
print(cursor.description)
#[('id',), ('nome',)]
```
> 🔁 .fetchone()
Lê uma linha por vez como tupla:
```python
linha = cursor.fetchone()
while linha:
    print(linha)
    linha = cursor.fetchone()
```
---

### ⚙️ **Consulta Simplificada com `execute_query()` (para uso com `wborm`)**

A nova versão do `wbjdbc` oferece um método auxiliar para retornar uma lista de dicionários com nomes de colunas — ideal para integração com `wborm`:

```python
from wbjdbc import connect_to_db

conn = connect_to_db(
    db_type="informix-sqli",
    host="meu-servidor",
    database="minha_base",
    user="meu_usuario",
    password="minha_senha",
    port=1526,
    server="meu_informix_server"
)

resultados = conn.execute_query("SELECT * FROM minha_tabela")

for row in resultados:
    print(row)  # {'id': 1, 'nome': 'Produto A', 'preco': 25.99}
```

> 🔁 O `execute_query()` retorna uma lista de dicionários com os nomes das colunas como chaves.

---

### 📋 **Exemplo de saída**:

```sh
(1, 'Produto A', 25.99)
(2, 'Produto B', 19.50)
(3, 'Produto C', 32.75)
```

Caso a tabela tenha colunas `id`, `nome` e `preco`, o resultado da query será uma lista de tuplas.

---

## 🛠️ **Configuração Avançada**

### 🔍 **Definir um caminho específico para o Java**
Caso o `JAVA_HOME` não esteja corretamente configurado, você pode definir um caminho específico para o Java:

```python
start_jvm(java_home="/caminho/para/o/java")
```

### 📦 **Adicionar JARs adicionais**
Se precisar de drivers JDBC extras, basta adicionar os arquivos `.jar` na inicialização:

```python
start_jvm(extra_jars=["/caminho/para/outro-driver.jar"])
```

---

## 🐛 **Ativando o modo Debug**
Para facilitar a identificação de problemas, o `wbjdbc` oferece um **modo Debug** que imprime informações úteis durante a execução.

### 🔎 **Ativando Debug na inicialização da JVM:**
```python
start_jvm(debug=1)
```

### 🔎 **Ativando Debug na conexão ao banco:**
```python
conn = connect_to_db(
    db_type="informix-sqli",
    host="meu-servidor",
    database="minha_base",
    user="meu_usuario",
    password="minha_senha",
    port=1526,
    server="meu_informix_server",
    debug=1
)
```

Com isso, logs detalhados sobre a configuração do ambiente, os JARs carregados e a conexão serão exibidos no console.

---

## 🤝 **Contribuição**
Se deseja contribuir com melhorias para o projeto, envie um **pull request** no [repositório oficial](https://github.com/wanderbatistaf/wbjdbc).

---

## 📜 **Licença**
Este projeto é licenciado sob a **Licença MIT**. Consulte o arquivo [`LICENSE`](https://github.com/wanderbatistaf/wbjdbc/blob/main/LICENSE) para mais informações.

---

# 📌 **wbjdbc (v1.2.0) - English Version**

## 📌 What is `wbjdbc`?

**wbjdbc** is a Python library that simplifies **JDBC** and **JVM** configuration, especially for **Informix** and **MongoDB** databases. The library manages drivers internally, ensuring automatic JVM initialization and easy connection setup.

### 🚀 **Main Features**:
- **Automatic JVM initialization** with `JAVA_HOME` detection.
- **Support for multiple JDBC drivers**:
  - **Informix JDBC Driver** (`jdbc-4.50.10.1.jar`)
  - **MongoDB BSON Driver** (`bson-3.8.0.jar`)
- **Internal dependency management**, including **JPype1** support.
- **New: `execute_query()` for dictionary-based results**
- **Debug Mode** to help with troubleshooting.
- **Compatible with Python 3.8+**.

---

## 📥 Installation
To install via **PyPI**, run:

```sh
pip install wbjdbc
```

---

## 🛠️ **Usage**

### ✅ **Starting the JVM**

```python
from wbjdbc import start_jvm

start_jvm()
```

### 📡 **Connecting to Informix**

```python
from wbjdbc import connect_to_db

conn = connect_to_db(
    db_type="informix-sqli",
    host="my-server",
    database="my_database",
    user="my_user",
    password="my_password",
    port=1526,
    server="my_informix_server"
)

cursor = conn.cursor()
cursor.execute("SELECT * FROM my_table")
results = cursor.fetchall()
for row in results:
    print(row)

cursor.close()
conn.close()
```

---

### 🧩 **Additional cursor methods**

The object returned by `conn.cursor()` implements methods similar to the Python DB-API standard:

> 🔎 `.description`
> Returns metadata about the columns of the last executed query:

```python
cursor.execute("SELECT id, name FROM products")
print(cursor.description)
# [('id',), ('name',)]
```

> 🔁 `.fetchone()`
> Fetches one row at a time as a tuple:

```python
row = cursor.fetchone()
while row:
    print(row)
    row = cursor.fetchone()
```

---

### ⚙️ **Simplified Query with `execute_query()`**

New in version `1.1.4`, you can run a query and receive the output as a list of dictionaries — perfect for tools like `wborm`:

```python
results = conn.execute_query("SELECT * FROM my_table")
for row in results:
    print(row)  # {'id': 1, 'name': 'Product A', 'price': 25.99}
```

> 🔁 The `execute_query()` method returns rows with named fields as keys.

---

### 📋 **Example Output**:

```sh
(1, 'Product A', 25.99)
(2, 'Product B', 19.50)
(3, 'Product C', 32.75)
```

---

## 🛠️ **Advanced Configuration**

### 🔍 **Set a specific Java path**

```python
start_jvm(java_home="/path/to/java")
```

### 📦 **Add custom JDBC JARs**

```python
start_jvm(extra_jars=["/path/to/driver.jar"])
```

---

## 🐛 **Debug Mode**

```python
start_jvm(debug=1)
```

Or during connection:

```python
connect_to_db(..., debug=1)
```

---

## 🤝 **Contribute**
Pull requests are welcome via the [official GitHub repository](https://github.com/wanderbatistaf/wbjdbc).

---

## 📜 **License**
This project is licensed under the **MIT License**. See the [`LICENSE`](https://github.com/wanderbatistaf/wbjdbc/blob/main/LICENSE) file for details.
## **Made by a Brazilian Developer 🇧🇷**

