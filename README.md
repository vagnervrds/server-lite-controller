# Server Lite Controller

**Server Lite Controller** é uma interface leve e simples para gerenciar servidores, oferecendo funcionalidades básicas de controle e atalhos úteis para diversas tarefas. A interface foi projetada para ser intuitiva, atendendo tanto usuários iniciantes quanto avançados.

## Funcionalidades

### Controle do Servidor

- **Desligar ou Reiniciar**: Com apenas um clique, você pode desligar ou reiniciar o servidor diretamente pela interface web.

### Gerenciamento de Downloads

- **Downloads HTTP**: Interface para gerenciar downloads diretamente pelo servidor, utilizando `requests` do Flask.
- **Gerenciamento de Torrents**: Integração com o cliente Deluge para adicionar, monitorar e controlar torrents.

### Atalhos Personalizáveis

- Links rápidos para acessar outras interfaces web do servidor, otimizando o acesso a ferramentas e serviços adicionais.

### Interface Responsiva

- **Otimizada para Celulares e Computadores**: A interface é projetada para funcionar perfeitamente em qualquer dispositivo, proporcionando uma experiência fluida e adaptada.

## Como Usar

1. Clone este repositório:
   ```bash
   git clone https://github.com/vagnervrds/server-lite-controller.git
   cd server-lite-controller
   ```
2. Crie um ambiente virtual (venv):

```bash python3 -m venv venv
source venv/bin/activate  # Linux/Mac
venv\Scripts\activate     # Windows
```

3. Instale as dependências:

```bash
pip install -r requirements.txt
```

4. Execute a aplicação:

```bash
python app.py
```

5.  Acesse a interface pelo navegador:

        http://localhost:5010

Nota: A aplicação utiliza a porta padrão 5010, mas você pode alterá-la facilmente no arquivo app.py modificando este trecho:

app.run(host='0.0.0.0', port=5010, debug=True)

Requisitos

    Python 3.7 ou superior
    Flask
    Deluge instalado e configurado

Configuração do Deluge

Certifique-se de que o Deluge está configurado corretamente:

    Habilite o plugin DelugeRPC.
    Configure as credenciais em app.py:

    DELUGE_HOST = "localhost"
    DELUGE_PORT = 58846
    DELUGE_USERNAME = "seu_usuario"
    DELUGE_PASSWORD = "sua_senha"

Sobre o Projeto

Este projeto é um esforço de um desenvolvedor por diversão, e você está livre para usar este código como quiser. Seja para aprender, adaptar ou melhorar, sinta-se à vontade para explorá-lo.

Contribuições são sempre bem-vindas!
Como Contribuir

    Faça um fork deste repositório.
    Crie uma branch para suas alterações:

git checkout -b minha-branch

Faça commit das alterações:

git commit -m "Descrição do que foi alterado"

Envie para o repositório remoto:

    git push origin minha-branch

    Abra um Pull Request explicando suas alterações.

Instale as dependências:

pip install -r requirements.txt

Execute a aplicação:

python app.py

Acesse a interface pelo navegador:

    http://localhost:5010

Nota: A aplicação utiliza a porta padrão 5010, mas você pode alterá-la facilmente no arquivo app.py modificando este trecho:

app.run(host='0.0.0.0', port=5010, debug=True)

Requisitos

    Python 3.7 ou superior
    Flask
    Deluge instalado e configurado

Configuração do Deluge

Certifique-se de que o Deluge está configurado corretamente:

    Habilite o plugin DelugeRPC.
    Configure as credenciais em app.py:

    DELUGE_HOST = "localhost"
    DELUGE_PORT = 58846
    DELUGE_USERNAME = "seu_usuario"
    DELUGE_PASSWORD = "sua_senha"

Sobre o Projeto

Este projeto é um esforço de um desenvolvedor por diversão, e você está livre para usar este código como quiser. Seja para aprender, adaptar ou melhorar, sinta-se à vontade para explorá-lo.

Contribuições são sempre bem-vindas!
Como Contribuir

    Faça um fork deste repositório.
    Crie uma branch para suas alterações:

git checkout -b minha-branch

Faça commit das alterações:

git commit -m "Descrição do que foi alterado"

Envie para o repositório remoto:

    git push origin minha-branch

    Abra um Pull Request explicando suas alterações.

## Como configurar o serviço para que o aplicativo Flask rode continuamente no servidor.

### Criar o Arquivo do Serviço

Crie um arquivo de serviço no systemd para rodar o aplicativo continuamente:

    sudo nano /etc/systemd/system/server-lite-controller.service

Adicione o seguinte conteúdo ao arquivo:

[Unit]
Description=Server Lite Controller
After=network.target

[Service]
User=root
WorkingDirectory=/caminho/para/seu/projeto
Environment="PATH=/caminho/para/seu/projeto/venv/bin"
ExecStart=/caminho/para/seu/projeto/venv/bin/python app.py
Restart=always

[Install]
WantedBy=multi-user.target

    Nota: Substitua /caminho/para/seu/projeto pelo caminho real onde os arquivos estão localizados no servidor.

### Configurar e Iniciar o Serviço

    Recarregue o systemd para reconhecer o novo serviço:

sudo systemctl daemon-reload

Inicie o serviço:

    sudo systemctl start server-lite-controller

Habilite o serviço para iniciar automaticamente no boot:

    sudo systemctl enable server-lite-controller

Verifique o status do serviço:

    sudo systemctl status server-lite-controller

### Testar o Funcionamento

Acesse o aplicativo no navegador usando o IP do servidor e a porta configurada (por padrão, 5010):

http://<IP_DO_SERVIDOR>:5010/

Licença

Este projeto está licenciado sob a Licença MIT.
