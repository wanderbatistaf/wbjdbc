[![PyPI](https://img.shields.io/pypi/v/wbjdbc)](https://pypi.org/project/wbjdbc/) [![PyPI - Downloads](https://img.shields.io/pypi/dm/wbjdbc)](https://pypi.org/project/wbjdbc/) [![Build Status](https://github.com/wanderbatistaf/wbjdbc/actions/workflows/publish-package.yml/badge.svg)](https://github.com/wanderbatistaf/wbjdbc/actions) ![License: MIT](https://img.shields.io/github/license/wanderbatistaf/wbjdbc) [![Último Commit](https://img.shields.io/github/last-commit/wanderbatistaf/wbjdbc)](https://github.com/wanderbatistaf/wbjdbc) [![GitHub issues](https://img.shields.io/github/issues/wanderbatistaf/wbjdbc)](https://github.com/wanderbatistaf/wbjdbc/issues) [![GitHub forks](https://img.shields.io/github/forks/wanderbatistaf/wbjdbc?style=social)](https://github.com/wanderbatistaf/wbjdbc) [![GitHub stars](https://img.shields.io/github/stars/wanderbatistaf/wbjdbc?style=social)](https://github.com/wanderbatistaf/wbjdbc) 
# wbjdbc (v1.2.1)

### 🌍 Português | 🇺🇸 English

---

## 📌 O que é o wbjdbc?

wbjdbc é uma biblioteca Python que simplifica a configuração e o uso do JDBC e da JVM, especialmente para conexões com bancos de dados Informix e MongoDB. A biblioteca gerencia drivers internamente, garantindo inicialização automática da JVM e configuração simplificada das conexões.

### 🚀 Principais recursos:
- Inicialização automática da JVM com detecção de JAVA_HOME.
- Suporte para múltiplos drivers JDBC:
  - Informix JDBC Driver (jdbc-4.50.10.1.jar)
  - MongoDB BSON Driver (bson-3.8.0.jar)
- Gerenciamento interno de dependências, incluindo suporte para JPype1.
- Modo Debug para facilitar troubleshooting.
- Método execute_query() retornando lista de dicionários.
- Compatível com Python 3.8+.

---

## 📥 Instalação
Para instalar a biblioteca via PyPI, execute:

```sh
pip install wbjdbc
```

---

## 🛠️ Uso

### ✅ Inicializando a JVM
A JVM pode ser inicializada automaticamente pelo wbjdbc, mas você também pode inicializá-la manualmente:

```python
from wbjdbc import start_jvm

start_jvm()
```

Isso garantirá que a JVM esteja disponível antes de realizar conexões via JDBC.

---

### 📡 Conectando-se ao Informix

Aqui está um exemplo de como usar o wbjdbc para se conectar a um banco de dados Informix:

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
# [('id',), ('nome',)]
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

### ⚙️ Consulta Simplificada com execute_query() (para uso com wborm)

A nova versão do wbjdbc oferece um método auxiliar para retornar uma lista de dicionários com nomes de colunas — ideal para integração com wborm:

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

> 🔁 O execute_query() retorna uma lista de dicionários com os nomes das colunas como chaves.

---

### 📋 Exemplo de saída:

```sh
(1, 'Produto A', 25.99)
(2, 'Produto B', 19.50)
(3, 'Produto C', 32.75)
```

Caso a tabela tenha colunas id, nome e preco, o resultado da query será uma lista de tuplas.

---

## 🛠️ Configuração Avançada

### 🔍 Definir um caminho específico para o Java
Caso o JAVA_HOME não esteja corretamente configurado, você pode definir um caminho específico para o Java:

```python
start_jvm(java_home="/caminho/para/o/java")
```

### 📦 Adicionar JARs adicionais
Se precisar de drivers JDBC extras, basta adicionar os arquivos .jar na inicialização:

```python
start_jvm(extra_jars=["/caminho/para/outro-driver.jar"])
```

---

## 🍎 macOS: configurar JAVA_HOME e validar a JVM

Use o utilitário nativo do macOS para apontar o JAVA_HOME e validar a lib da JVM.

```sh
# Detectar e exportar o JAVA_HOME para a sessão atual
export JAVA_HOME=$(/usr/libexec/java_home)

# Tornar permanente no zsh
echo 'export JAVA_HOME=$(/usr/libexec/java_home)' >> ~/.zshrc
source ~/.zshrc

# Verificar a biblioteca da JVM (JDK completo deve conter este arquivo)
ls -l "$JAVA_HOME/lib/server/libjvm.dylib"

# Conferir a versão do Java
"$JAVA_HOME/bin/java" -version
```

Se o arquivo libjvm.dylib não existir, instale um JDK completo (ex.: Temurin/Adoptium) e aponte o JAVA_HOME para .../Contents/Home. A partir da versão 1.2.1, o wbjdbc detecta automaticamente a biblioteca correta no macOS (.dylib).

Problemas comuns no macOS
- Erro: “JVM not found: .../lib/server/libjvm.so” → no macOS a extensão é .dylib. Atualize para 1.2.1+ e verifique o JAVA_HOME.
- “No valid Java installation found.” → defina o JAVA_HOME como acima e valide com "$JAVA_HOME/bin/java -version".

---

## 🐛 Ativando o modo Debug
Para facilitar a identificação de problemas, o wbjdbc oferece um modo Debug que imprime informações úteis durante a execução.

### 🔎 Ativando Debug na inicialização da JVM:
```python
start_jvm(debug=1)
```

### 🔎 Ativando Debug na conexão ao banco:
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

## 🤝 Contribuição
Se deseja contribuir com melhorias para o projeto, envie um pull request no repositório oficial:
https://github.com/wanderbatistaf/wbjdbc

---

## 📜 Licença
Este projeto é licenciado sob a Licença MIT. Consulte o arquivo LICENSE para mais informações:
https://github.com/wanderbatistaf/wbjdbc/blob/main/LICENSE

---

# wbjdbc (v1.2.1) - English Version

## 📌 What is wbjdbc?

wbjdbc is a Python library that simplifies JDBC and JVM configuration, especially for Informix and MongoDB databases. The library manages drivers internally, ensuring automatic JVM initialization and easy connection setup.

### 🚀 Main Features:
- Automatic JVM initialization with JAVA_HOME detection.
- Support for multiple JDBC drivers:
  - Informix JDBC Driver (jdbc-4.50.10.1.jar)
  - MongoDB BSON Driver (bson-3.8.0.jar)
- Internal dependency management, including JPype1 support.
- Debug Mode to help with troubleshooting.
- execute_query() returns dictionary-based rows.
- Compatible with Python 3.8+.

---

## 📥 Installation
To install via PyPI, run:

```sh
pip install wbjdbc
```

---

## 🛠️ Usage

### ✅ Starting the JVM
The JVM can be initialized automatically by wbjdbc, but you can also initialize it manually:

```python
from wbjdbc import start_jvm

start_jvm()
```

This ensures the JVM is available before making JDBC connections.

---

### 📡 Connecting to Informix

Here’s an example of how to use wbjdbc to connect to an Informix database:

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
### 🧩 Additional cursor methods
The object returned by conn.cursor() implements methods similar to the Python DB-API standard:

> 🔎 .description  
Returns metadata about the columns of the last executed query:

```python
cursor.execute("SELECT id, name FROM products")
print(cursor.description)
# [('id',), ('name',)]
```

> 🔁 .fetchone()  
Reads one row at a time as a tuple:
```python
row = cursor.fetchone()
while row:
    print(row)
    row = cursor.fetchone()
```

---

### ⚙️ Simplified Query with execute_query() (for use with wborm)

The new version of wbjdbc provides a helper method that returns a list of dictionaries with column names — perfect for integrating with wborm:

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

results = conn.execute_query("SELECT * FROM my_table")

for row in results:
    print(row)  # {'id': 1, 'name': 'Product A', 'price': 25.99}
```

> 🔁 The execute_query() method returns a list of dictionaries with column names as keys.

---

### 📋 Example Output:

```sh
(1, 'Product A', 25.99)
(2, 'Product B', 19.50)
(3, 'Product C', 32.75)
```

If your table has columns id, name and price, the query result will be a list of tuples.

---

## 🛠️ Advanced Configuration

### 🔍 Set a specific Java path
If JAVA_HOME is not correctly configured, you can specify a Java path:

```python
start_jvm(java_home="/path/to/java")
```

### 📦 Add additional JARs
If you need extra JDBC drivers, just add the .jar files at startup:

```python
start_jvm(extra_jars=["/path/to/driver.jar"])
```

---

## 🍎 macOS: set JAVA_HOME and validate the JVM

Use the native macOS helper to set JAVA_HOME and validate the JVM library.

```sh
# Detect and export JAVA_HOME for the current shell
export JAVA_HOME=$(/usr/libexec/java_home)

# Make it permanent on zsh
echo 'export JAVA_HOME=$(/usr/libexec/java_home)' >> ~/.zshrc
source ~/.zshrc

# Verify the JVM library (a full JDK must include this file)
ls -l "$JAVA_HOME/lib/server/libjvm.dylib"

# Check Java version
"$JAVA_HOME/bin/java" -version
```

If libjvm.dylib is missing, install a full JDK (e.g., Temurin/Adoptium) and point JAVA_HOME to .../Contents/Home. Starting from version 1.2.1, wbjdbc automatically detects the correct macOS library (.dylib).

Common macOS issues
- Error: “JVM not found: .../lib/server/libjvm.so” → on macOS the extension is .dylib. Upgrade to 1.2.1+ and verify JAVA_HOME.
- “No valid Java installation found.” → set JAVA_HOME as above and validate with "$JAVA_HOME/bin/java -version".

---

## 🐛 Debug Mode
To make troubleshooting easier, wbjdbc offers a Debug mode that prints useful information during execution.

### 🔎 Enabling Debug when starting the JVM:
```python
start_jvm(debug=1)
```

### 🔎 Enabling Debug when connecting to the database:
```python
conn = connect_to_db(
    db_type="informix-sqli",
    host="my-server",
    database="my_database",
    user="my_user",
    password="my_password",
    port=1526,
    server="my_informix_server",
    debug=1
)
```

This will output detailed logs about environment configuration, loaded JARs, and the connection.

---

## 🤝 Contribute
Pull requests are welcome via the official GitHub repository:
https://github.com/wanderbatistaf/wbjdbc

---

## 📜 License
This project is licensed under the MIT License. See the LICENSE file for more information:
https://github.com/wanderbatistaf/wbjdbc/blob/main/LICENSE

---

Made by a Brazilian Developer 🇧🇷