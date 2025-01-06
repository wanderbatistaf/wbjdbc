import os
import sys
import subprocess
import jpype
from pkg_resources import resource_filename


class JVMError(Exception):
    """Classe personalizada para erros de JVM."""
    pass


def ensure_jpype_installed():
    """Garante que JPype1 seja instalado a partir do wheel interno."""
    try:
        import jpype
    except ImportError:
        # Localiza o diretório de wheels dentro do pacote
        wheels_dir = resource_filename("wbjdbc", "wheels")

        # Verifica a existência do diretório de wheels
        if not os.path.isdir(wheels_dir):
            raise JVMError(f"Diretório de wheels não encontrado: {wheels_dir}")

        # Localiza o arquivo JPype1 no diretório de wheels
        wheel_file = next((f for f in os.listdir(wheels_dir) if "JPype1" in f and f.endswith(".whl")), None)
        if not wheel_file:
            raise JVMError("Wheel do JPype1 não encontrado no diretório de wheels.")

        # Instala o JPype1 a partir do wheel interno
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", os.path.join(wheels_dir, wheel_file)])
            print("JPype1 instalado com sucesso.")
        except subprocess.CalledProcessError as e:
            raise JVMError(f"Falha ao instalar JPype1: {e}")


# Garante que JPype1 está instalado antes de prosseguir
ensure_jpype_installed()


def start_jvm():
    """Inicia a JVM com os recursos internos."""
    try:
        # Localiza os arquivos necessários
        jvm_path = resource_filename("wbjdbc", "resources/server/jdk-17.0.2/bin/server/jvm.dll")
        jdbc_driver_path = resource_filename("wbjdbc", "resources/maven/com.ibm.informix/jdbc-4.50.10.1.jar")
        bson_jar_path = resource_filename("wbjdbc", "resources/maven/org.mongodb/bson-3.8.0.jar")

        # Verifica a existência dos arquivos
        for file_path, desc in [
            (jvm_path, "JVM"),
            (jdbc_driver_path, "JDBC Driver"),
            (bson_jar_path, "BSON Jar"),
        ]:
            if not os.path.isfile(file_path):
                raise JVMError(f"Arquivo {desc} não encontrado: {file_path}")

        # Configuração do classpath
        classpath = f"{jdbc_driver_path};{bson_jar_path}"

        # Inicializa a JVM
        if not jpype.isJVMStarted():
            jpype.startJVM(jvm_path, f"-Djava.class.path={classpath}")
            print("JVM inicializada com sucesso!")
        else:
            print("JVM já está inicializada.")
    except JVMError as e:
        print(f"Erro na inicialização da JVM: {e}")
        raise
    except jpype.JVMNotSupportedException as e:
        print(f"A JVM não é suportada: {e}")
        raise
    except Exception as e:
        print(f"Erro inesperado ao inicializar a JVM: {e}")
        raise
