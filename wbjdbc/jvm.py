import os
import sys
import subprocess
import jpype
from pkg_resources import resource_filename


class JVMError(Exception):
    """Classe personalizada para erros de JVM."""
    pass


def ensure_jpype_installed():
    """Garante que JPype1 esteja instalado corretamente."""
    try:
        import jpype
        # Debug
        # print("✅ JPype1 já instalado.")
    except ImportError:
        wheels_dir = resource_filename("wbjdbc", "wheels")

        if not os.path.isdir(wheels_dir):
            raise JVMError(f"❌ Diretório de wheels não encontrado: {wheels_dir}")

        wheel_file = next((f for f in os.listdir(wheels_dir) if "JPype1" in f and f.endswith(".whl")), None)
        if not wheel_file:
            raise JVMError("❌ Wheel do JPype1 não encontrado no diretório de wheels.")

        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", os.path.join(wheels_dir, wheel_file)])
            print("✅ JPype1 instalado com sucesso.")
        except subprocess.CalledProcessError as e:
            raise JVMError(f"❌ Falha ao instalar JPype1: {e}")


# Garante que JPype1 está instalado antes de prosseguir
ensure_jpype_installed()

class JVMError(Exception):
    """Classe personalizada para erros de JVM."""
    pass


def find_java_executable():
    """Encontra o caminho do executável do Java (`java.exe` ou `java`)."""
    try:
        java_path = subprocess.check_output("where java", shell=True).decode().strip().split("\n")[0]
        print(f"\n🔍 **Java Detectado:** {java_path}\n")
        return java_path
    except subprocess.CalledProcessError:
        raise JVMError("❌ Não foi possível localizar o executável Java (java.exe). Verifique se está instalado e no PATH.")


def detect_java_home():
    """Detecta automaticamente o JAVA_HOME correto."""
    java_home = os.environ.get("JAVA_HOME")

    if java_home:
        java_exe = os.path.join(java_home, "bin", "java.exe") if os.name == "nt" else os.path.join(java_home, "bin", "java")
        if os.path.isfile(java_exe):
            return java_home  # Retorna se JAVA_HOME for válido

    try:
        java_path = subprocess.check_output("where java", shell=True).decode().strip().split("\n")[0]
        java_home = os.path.dirname(os.path.dirname(java_path))  # Volta dois diretórios para encontrar o JDK
        if os.path.isdir(java_home):
            return java_home
    except Exception:
        pass

    return None  # Falha ao detectar Java


def start_jvm(jars=None, java_home=None):
    """
    Inicia a JVM garantindo que o Java correto seja usado.

    :param jars: Lista de arquivos JAR adicionais.
    :param java_home: Caminho alternativo para JAVA_HOME (opcional).
    """
    try:
        # Debug
        # print("\n🔹 VALIDANDO CAMINHOS NECESSÁRIOS PARA JVM...\n")

        # Detecta JAVA_HOME automaticamente se não for fornecido
        java_home = java_home or detect_java_home()
        if not java_home:
            raise JVMError("❌ Nenhuma instalação válida do Java foi encontrada.")

        print(f"🟢 JAVA_HOME detectado: {java_home}\n")

        # Define o caminho da JVM
        jvm_path = os.path.join(java_home, "bin", "server", "jvm.dll") if os.name == "nt" else os.path.join(java_home,
                                                                                                            "lib",
                                                                                                            "server",
                                                                                                            "libjvm.so")

        if not os.path.isfile(jvm_path):
            raise JVMError(f"❌ JVM não encontrada: {jvm_path}")

        #Debug
        # print(f"🟢 JVM Path: {jvm_path}  -->  ✅ Encontrado\n")

        # Configuração dos JARs
        if jars is None:
            jars = []

        # Adiciona o JAR do Informix
        informix_jar = resource_filename("wbjdbc", "resources/maven/com.ibm.informix/jdbc-4.50.10.1.jar")
        jars.insert(0, informix_jar)

        # Adiciona o JAR do BSON (MongoDB)
        bson_jar = resource_filename("wbjdbc", "resources/maven/org.mongodb/bson-3.8.0.jar")
        if os.path.isfile(bson_jar):
            jars.append(bson_jar)
        else:
            raise JVMError(f"❌ Arquivo BSON JAR não encontrado: {bson_jar}")

        # Verifica se os JARs existem
        for jar in jars:
            if not os.path.isfile(jar):
                raise JVMError(f"❌ Arquivo JAR não encontrado: {jar}")

        classpath = os.pathsep.join(jars)  # `;` no Windows, `:` no Linux/Mac

        # Debug
        # print("🔹 VALIDANDO JARS NECESSÁRIOS...\n")
        for jar in jars:
            print(f"🟢 JAR: {jar}  -->  ✅ Encontrado")

        print(f"\n🔹 Classpath Final: {classpath}\n")

        # Inicializa a JVM apenas se ainda não estiver rodando
        if not jpype.isJVMStarted():
            print("\n🔄 Tentando iniciar a JVM...\n")
            jpype.startJVM(jvm_path, f"-Djava.class.path={classpath}")

            # Verifica se o DriverManager do JDBC está carregado corretamente
            try:
                jpype.java.lang.Class.forName("java.sql.DriverManager")
                # Debug
                # print("✅ Classe java.sql.DriverManager carregada com sucesso!")
            except jpype.JClassNotFoundException:
                raise JVMError("❌ Erro: Não foi possível carregar a classe java.sql.DriverManager!")

            print("✅ JVM inicializada com sucesso!")
        else:
            print("✅ JVM já está inicializada.")

    except JVMError as e:
        print(f"❌ Erro na inicialização da JVM: {e}")
        raise
    except jpype.JVMNotSupportedException as e:
        print(f"❌ A JVM não é suportada: {e}")
        raise
    except Exception as e:
        print(f"❌ Erro inesperado ao inicializar a JVM: {e}")
        raise


