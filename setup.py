import os
import subprocess
from setuptools import setup, find_packages
import pathlib

# Caminho para o README.md
current_dir = pathlib.Path(__file__).parent.resolve()
long_description = (current_dir / "README.md").read_text(encoding="utf-8")

import platform
import sys


def install_dependencies():
    try:
        import jpype
        print("JPype1 já está instalado.")
    except ImportError:
        import platform
        import sys
        import subprocess
        import os

        system = platform.system().lower()
        python_version = f"cp{sys.version_info.major}{sys.version_info.minor}"
        dependencies_dir = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "wbjdbc", "resources", "dependencies")
        )

        if system == "windows":
            wheel_file = f"jpype1-1.5.1-{python_version}-{python_version}-win_amd64.whl"
        elif system == "linux":
            wheel_file = f"jpype1-1.5.1-{python_version}-{python_version}-manylinux_2_17_x86_64.manylinux2014_x86_64.whl"
        elif system == "darwin":
            wheel_file = f"jpype1-1.5.1-{python_version}-{python_version}-macosx_10_9_universal2.whl"
        else:
            raise RuntimeError(f"Sistema operacional não suportado: {system}")

        wheel_path = os.path.join(dependencies_dir, wheel_file)

        if os.path.exists(wheel_path):
            print(f"Instalando JPype1 de {wheel_path} para {system}.")
            try:
                subprocess.check_call(["pip", "install", wheel_path])
            except subprocess.CalledProcessError as e:
                print(f"Erro ao instalar JPype1 de {wheel_path}: {e}")
                print("Tentando instalar JPype1 diretamente do PyPI como fallback...")
                subprocess.check_call(["pip", "install", "JPype1"])
        else:
            print(
                f"O arquivo {wheel_file} não foi encontrado no diretório {dependencies_dir}. Tentando instalar do PyPI...")
            subprocess.check_call(["pip", "install", "JPype1"])
    finally:
        # Validar se a instalação foi bem-sucedida
        try:
            import jpype
            print("JPype1 instalado com sucesso!")
        except ImportError:
            print("Erro: Falha ao instalar JPype1, mesmo após tentativa do PyPI.")
            raise RuntimeError("Falha na instalação do JPype1.")


# Chama a função para instalar JPype1
install_dependencies()

setup(
    name="wbjdbc",
    version="1.0.4",
    packages=find_packages(),
    include_package_data=True,
    package_data={
        "wbjdbc": [
            "resources/server/**",
            "resources/maven/com.ibm.informix/*",
            "resources/maven/org.mongodb/*",
            "resources/dependencies/*",
        ]
    },
    install_requires=[],  # Não lista JPype1 aqui, pois ele é instalado manualmente
    description="Library to simplify JDBC and JVM configuration for Informix and MongoDB",
    long_description=long_description,
    long_description_content_type="text/markdown",
    author="Wanderson Batista",
    author_email="wanderfreitasb@gmail.com",
    url="https://github.com/wanderbatistaf/wbjdbc",
)
