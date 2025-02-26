import os
from .jvm import start_jvm
import jaydebeapi

# Configurações padrão para drivers
DEFAULT_DRIVERS = {
    "informix-sqli": {
        "driver_class": "com.informix.jdbc.IfxDriver",
        "default_port": 1526,
        "jar": os.path.join(os.path.dirname(__file__), "resources", "maven", "com.ibm.informix", "jdbc-4.50.10.1.jar"),
    },
    "mysql": {
        "driver_class": "com.mysql.cj.jdbc.Driver",
        "default_port": 3306,
        "jar": os.path.join(os.path.dirname(__file__), "resources", "maven", "mysql", "mysql-connector-java-8.0.26.jar"),
    },
    "postgresql": {
        "driver_class": "org.postgresql.Driver",
        "default_port": 5432,
        "jar": os.path.join(os.path.dirname(__file__), "resources", "maven", "postgresql", "postgresql-42.2.24.jar"),
    },
}

def connect_to_db(db_type, host, database, user, password, port=None, server=None, extra_jars=None, java_home=None):
    """
    Conecta ao banco de dados via JDBC sem exigir detalhes complexos do usuário.

    :param db_type: Tipo do banco de dados. As opções disponíveis são:
        - 1 :"informix-sqli" (para Informix)
        - 2 :"mysql" (para MySQL)
        - 3 :"postgresql" (para PostgreSQL)
    :param host: Endereço do servidor do banco de dados.
    :param database: Nome do banco de dados.
    :param user: Nome de usuário.
    :param password: Senha.
    :param port: Porta opcional (usa padrão se não for fornecida).
    :param server: Server do banco de dados informix.
    :param extra_jars: Lista de caminhos para JARs adicionais, se necessário.
    :param java_home: Caminho alternativo para JAVA_HOME (opcional).
    :return: Conexão ativa via jaydebeapi.
    """

    if db_type == 1:
        db_type = 'informix-sqli'
    elif db_type == 2:
        db_type = 'mysql'
    elif db_type == 3:
        db_type = 'postgresql'
    else:
        db_type = db_type

    if db_type not in DEFAULT_DRIVERS:
        raise ValueError(f"❌ Banco de dados '{db_type}' não suportado. Opções disponíveis: {list(DEFAULT_DRIVERS.keys())}")

    driver_config = DEFAULT_DRIVERS[db_type]
    driver_class = driver_config["driver_class"]
    jar_path = driver_config["jar"]
    port = port or driver_config["default_port"]

    # Debug
    # print(f"🔍 DB Type: {db_type}, Host: {host}, Database: {database}, Porta: {port}")

    # 🔹 Corrigindo a URL JDBC para Informix
    if db_type == "informix":
        jdbc_url = f"jdbc:informix-sqli://{host}:{port}/{database}:INFORMIXSERVER={server}"
    else:
        jdbc_url = f"jdbc:{db_type}://{host}:{port}/{database}"

    # Debug
    # print(f"🔹 URL JDBC Gerada: {jdbc_url}")

    # Debug
    # print("\n🟢 Chegou até aqui antes de iniciar a JVM")

    # Inicia a JVM com os JARs necessários
    jars = [jar_path] + (extra_jars if extra_jars else [])
    start_jvm(jars, java_home=java_home)

    # Conecta ao banco usando JayDeBeAPI
    try:
        conn = jaydebeapi.connect(driver_class, jdbc_url, [user, password], jars)
        print(f"✅ Conexão com {db_type.upper()} estabelecida com sucesso!")
        return conn
    except jaydebeapi.DatabaseError as e:
        print(f"❌ Erro ao conectar ao banco de dados: {e}")
        raise
