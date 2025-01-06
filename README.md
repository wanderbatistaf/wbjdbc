[![Publish Package to PyPI](https://github.com/wanderbatistaf/wbjdbc/actions/workflows/publish-package.yml/badge.svg?branch=main)](https://github.com/wanderbatistaf/wbjdbc/actions/workflows/publish-package.yml)

<h1>wbjdbc</h1>

<p>wbjdbc é uma biblioteca Python que simplifica a configuração e o uso do JDBC e da JVM, especialmente para conexões com bancos de dados <strong>Informix</strong> e <strong>MongoDB</strong>. Ela fornece uma abordagem integrada para gerenciar drivers JDBC, iniciar a JVM e configurar o ambiente necessário para o acesso ao banco de dados.</p>

<h3>Recursos</h3>
<ul>
    <li>Inicialização simplificada da JVM (<code>jvm.dll</code>).</li>
    <li>Suporte interno para os drivers JDBC:
        <ul>
            <li><strong>Informix JDBC Driver</strong>: <code>jdbc-4.50.10.1.jar</code></li>
            <li><strong>MongoDB BSON Driver</strong>: <code>bson-3.8.0.jar</code></li>
        </ul>
    </li>
    <li>Precompilação de dependências para evitar erros de compatibilidade.</li>
    <li>Pacote leve e fácil de instalar.</li>
</ul>

<h3>Requisitos</h3>
<ul>
    <li>Python 3.8 ou superior.</li>
    <li>Java JDK compatível com o seu sistema operacional.</li>
</ul>

<h3>Instalação</h3>
<p>Para instalar a biblioteca:</p>
<pre><code>pip install wbjdbc</code></pre>

<h2>Uso</h2>

<h3>Inicializando a JVM</h3>
<p>Basta importar a biblioteca e chamar o método <code>start_jvm()</code>:</p>
<pre><code>from wbjdbc import start_jvm

start_jvm()
</code></pre>

<h3>Exemplo de Conexão JDBC</h3>
<p>Aqui está um exemplo de como usar o <strong>wbjdbc</strong> para se conectar a um banco de dados Informix:</p>
<pre><code>from wbjdbc import start_jvm
import jaydebeapi

start_jvm()

# Configuração da conexão JDBC
jdbc_url = "jdbc:informix-sqli://<host>:<port>/<database>:INFORMIXSERVER=<server>"
user = "<usuario>"
password = "<senha>"

# Conectando ao banco de dados
conn = jaydebeapi.connect("com.informix.jdbc.IfxDriver", jdbc_url, [user, password])
cursor = conn.cursor()

# Executando uma consulta
cursor.execute("SELECT * FROM minha_tabela")
resultados = cursor.fetchall()

for linha in resultados:
    print(linha)

cursor.close()
conn.close()
</code></pre>

<h3>Contribuição</h3>
<p>Se você deseja contribuir para o projeto, envie um pull request no <a href="https://github.com/wanderbatistaf/wbjdbc">repositório do GitHub</a>.</p>

<h3>Licença</h3>
<p>Este projeto é licenciado sob a licença MIT. Consulte o arquivo <code>LICENSE</code> para mais informações.</p>
