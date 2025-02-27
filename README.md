[![PyPI](https://img.shields.io/pypi/v/wbjdbc)](https://pypi.org/project/wbjdbc/) [![PyPI - Downloads](https://img.shields.io/pypi/dm/wbjdbc)](https://pypi.org/project/wbjdbc/) [![Build Status](https://github.com/wanderbatistaf/wbjdbc/actions/workflows/publish-package.yml/badge.svg)](https://github.com/wanderbatistaf/wbjdbc/actions) ![License: MIT](https://img.shields.io/github/license/wanderbatistaf/wbjdbc) [![Último Commit](https://img.shields.io/github/last-commit/wanderbatistaf/wbjdbc)](https://github.com/wanderbatistaf/wbjdbc) [![GitHub issues](https://img.shields.io/github/issues/wanderbatistaf/wbjdbc)](https://github.com/wanderbatistaf/wbjdbc/issues) [![GitHub forks](https://img.shields.io/github/forks/wanderbatistaf/wbjdbc?style=social)](https://github.com/wanderbatistaf/wbjdbc) [![GitHub stars](https://img.shields.io/github/stars/wanderbatistaf/wbjdbc?style=social)](https://github.com/wanderbatistaf/wbjdbc) 
# wbjdbc (v1.1.3)

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

# 📌 **wbjdbc (v1.1.3) - English Version**

## 📌 What is `wbjdbc`?

**wbjdbc** is a Python library that simplifies **JDBC** and **JVM** configuration, especially for **Informix** and **MongoDB** databases. The library manages drivers internally, ensuring automatic JVM initialization and easy connection setup.

### 🚀 **Main Features**:
- **Automatic JVM initialization** with `JAVA_HOME` detection.
- **Support for multiple JDBC drivers**:
  - **Informix JDBC Driver** (`jdbc-4.50.10.1.jar`)
  - **MongoDB BSON Driver** (`bson-3.8.0.jar`)
- **Internal dependency management**, including **JPype1** support.
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

### 📋 **Example Output**:

```sh
(1, 'Product A', 25.99)
(2, 'Product B', 19.50)
(3, 'Product C', 32.75)
```

For more details, check the official [GitHub repository](https://github.com/wanderbatistaf/wbjdbc).

---

## **Made by a Brazilian Developer 🇧🇷**

