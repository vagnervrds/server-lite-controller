# Server Lite Controller

Uma interface leve e simples para gerenciar servidores, com funcionalidades de controle básico e atalhos úteis.

## Funcionalidades

- **Desligar/Reiniciar o Servidor**: Botões para desligar ou reiniciar o servidor diretamente pela interface.
- **Atalhos Personalizáveis**:
  - Interface para gerenciar downloads.
  - Gerenciamento de torrents (Deluge).
  - Links para outras interfaces web do servidor.
- **Interface Intuitiva**: Projetada para ser simples e fácil de usar.

## Como Usar

1. Clone este repositório:
   ```bash
   git clone https://github.com/vagnervrds/server-lite-controller.git
   cd server-lite-controller```
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
5. 
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

Licença

Este projeto está licenciado sob a Licença MIT. Consulte o arquivo LICENSE para mais informações.

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

Licença

Este projeto está licenciado sob a Licença MIT. Consulte o arquivo LICENSE para mais informações.
