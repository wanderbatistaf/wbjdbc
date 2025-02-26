[![Publish Package to PyPI](https://github.com/wanderbatistaf/wbjdbc/actions/workflows/publish-package.yml/badge.svg?branch=v1.1.1)](https://github.com/wanderbatistaf/wbjdbc/actions/workflows/publish-package.yml) ![PyPI - Downloads](https://img.shields.io/pypi/dm/wbjdbc) [![Open Source](https://badgen.net/badge/Open%20Source/Yes/blue)](https://github.com/wanderbatistaf/wbjdbc)
# wbjdbc

**wbjdbc** é uma biblioteca Python que simplifica a configuração e o uso do **JDBC** e da **JVM**, especialmente para conexões com bancos de dados **Informix** e **MongoDB**. Com suporte interno para gerenciamento de drivers JDBC, **wbjdbc** permite inicializar a JVM automaticamente e configurar conexões de forma simplificada.

## Recursos Principais
- **Inicialização automática da JVM** com detecção de `JAVA_HOME`.
- **Suporte interno para múltiplos drivers JDBC**:
  - **Informix JDBC Driver** (`jdbc-4.50.10.1.jar`)
  - **MongoDB BSON Driver** (`bson-3.8.0.jar`)
- **Gerenciamento interno de dependências**, incluindo suporte para **JPype1**.
- **Configuração simplificada** para conexão com bancos de dados via JDBC.
- **Compatível com Python 3.8+**.

## Requisitos
- **Python** `3.8` ou superior.
- **Java JDK** compatível com o seu sistema operacional.

##Instalação
Para instalar a biblioteca via **PyPI**, execute:

```sh
pip install wbjdbc
```

## Uso

### Inicializando a JVM
A JVM pode ser inicializada automaticamente pelo `wbjdbc`, mas você também pode inicializá-la manualmente:

```python
from wbjdbc import start_jvm

start_jvm()
```

Isso garantirá que a JVM esteja disponível antes de realizar conexões via JDBC.

### Conectando-se ao Informix
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

### Configuração Avançada

#### Definir um caminho específico para o Java
Caso o `JAVA_HOME` não esteja corretamente configurado, você pode forçar um caminho específico para o Java:

```python
start_jvm(java_home="/caminho/para/o/java")
```

#### Adicionar JARs adicionais
Se precisar de drivers JDBC extras, basta adicionar os arquivos `.jar` na inicialização:

```python
start_jvm(extra_jars=["/caminho/para/outro-driver.jar"])
```

## 🤝 Contribuição
Se deseja contribuir com melhorias para o projeto, envie um **pull request** no [repositório oficial](https://github.com/wanderbatistaf/wbjdbc).

## Licença
Este projeto é licenciado sob a **Licença MIT**. Consulte o arquivo [`LICENSE`](https://github.com/wanderbatistaf/wbjdbc/blob/main/LICENSE) para mais informações.

