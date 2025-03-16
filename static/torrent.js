// Variáveis globais
let isListingFiles = false;

document.addEventListener("DOMContentLoaded", () => {
    const downloadsContainer = document.getElementById("downloads-container");
    const form = document.getElementById("add-download-form");

    // Função para atualizar a lista de downloads
    function fetchDownloads() {
        if (isListingFiles) return; // Pausa o fetch se estiver listando arquivos
        fetch("/torrent/downloads")
            .then((response) => response.json())
            .then((data) => {
                if (data.downloads && data.downloads.length > 0) {
                    downloadsContainer.innerHTML = ""; // Limpa o contêiner
                    data.downloads.forEach((download) => {
                        const downloadItem = document.createElement("div");
                        downloadItem.className = "download-item";
                        downloadItem.setAttribute("data-id", download.id);

                        // Determina qual botão mostrar com base no estado do download
                        let actionButton;
                        if (download.state === "Paused") {
                            actionButton = `<button class="btn-resume" data-id="${download.id}">Continuar</button>`;
                        } else {
                            actionButton = `<button class="btn-stop" data-id="${download.id}">Parar</button>`;
                        }

                        downloadItem.innerHTML = `
                          <div>${download.name}</div>
                          <div class="progress-bar">
                              <div class="progress-fill" style="width: ${download.progress}%"></div>
                          </div>
                          <div>Status: ${download.state} - ${download.progress}%</div>
                          <div class="actions">
                              ${actionButton}
                              <button class="btn-cancel" data-id="${download.id}">Cancelar</button>
                              <button class="btn-delete" data-id="${download.id}">Apagar</button>
                              <button class="btn-list-files" data-id="${download.id}">Listar Arquivos</button>
                          </div>
                        `;

                        downloadsContainer.appendChild(downloadItem);

                        // Adiciona eventos aos botões
                        addActionListeners(downloadItem);
                    });
                } else {
                    downloadsContainer.innerHTML = "<p>Nenhum download ativo no momento.</p>";
                }
            })
            .catch((err) => {
                downloadsContainer.innerHTML = `<p>Erro ao carregar downloads: ${err.message}</p>`;
                console.error(err);
            });
    }

    // Função para listar arquivos
    function listFiles(torrentId, container) {
        isListingFiles = true; // Pausa atualizações automáticas

        fetch(`/torrent/list-files/${torrentId}`, { method: "GET" })
            .then((response) => response.json())
            .then((data) => {
                let files = data.files;
                let sortDirection = {
                    name: 'asc',
                    size: 'asc',
                };

                const convertSizeToBytes = (size) => {
                    const units = ['B', 'KB', 'MB', 'GB', 'TB'];
                    const [value, unit] = size.split(' ');
                    const unitIndex = units.indexOf(unit);
                    return parseFloat(value) * Math.pow(1024, unitIndex);
                };

                const renderTable = () => {
                    const fileTable = `
                        <div class="files-container">
                            <h3>Selecione os arquivos para download</h3>
                            <table class="file-table">
                                <thead>
                                    <tr>
                                        <th>Baixar</th>
                                        <th data-sort="name">Nome</th>
                                        <th data-sort="size">Tamanho</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    ${files
                            .map(
                                (file, index) => `
                                            <tr>
                                                <td><input type="checkbox" data-index="${index}" checked></td>
                                                <td>${file.name}</td>
                                                <td>${file.size}</td>
                                            </tr>`
                            )
                            .join("")}
                                </tbody>
                            </table>
                            <button class="btn-save-files">Salvar</button>
                            <button class="btn-close-files">Cancelar</button>
                        </div>
                    `;

                    container.innerHTML = fileTable;

                    // Adicionar eventos de ordenação
                    container.querySelectorAll("th[data-sort]").forEach((header) => {
                        header.addEventListener("click", () => {
                            const sortKey = header.getAttribute("data-sort");
                            const direction = sortDirection[sortKey] === 'asc' ? 1 : -1;

                            files.sort((a, b) => {
                                if (sortKey === 'size') {
                                    return direction * (convertSizeToBytes(a[sortKey]) - convertSizeToBytes(b[sortKey]));
                                } else {
                                    return direction * a[sortKey].localeCompare(b[sortKey]);
                                }
                            });

                            sortDirection[sortKey] = sortDirection[sortKey] === 'asc' ? 'desc' : 'asc';
                            renderTable(); // Re-renderiza a tabela após ordenar
                        });
                    });

                    // Evento para fechar sem salvar
                    container.querySelector(".btn-close-files").addEventListener("click", () => {
                        isListingFiles = false; // Retoma atualizações automáticas
                        container.innerHTML = ""; // Limpa a tabela
                        fetchDownloads(); // Atualiza os downloads
                    });

                    // Evento para salvar seleções
                    container.querySelector(".btn-save-files").addEventListener("click", () => {
                        // Gera o dicionário com base nos checkboxes
                        const fileSelections = {};
                        container.querySelectorAll("input[type=checkbox]").forEach((checkbox) => {
                            const index = checkbox.getAttribute("data-index");
                            fileSelections[files[index].name] = checkbox.checked;
                        });

                        console.log("Arquivo selecionado para download:", fileSelections);

                        // Envia fileSelections para o servidor
                        fetch(`/torrent/cancel-files/${torrentId}`, {
                            method: "POST",
                            headers: {
                                "Content-Type": "application/json",
                            },
                            body: JSON.stringify({ file_selections: fileSelections }),
                        })
                            .then((response) => {
                                if (!response.ok) {
                                    throw new Error("Erro ao enviar seleção de arquivos");
                                }
                                return response.json();
                            })
                            .then((data) => {
                                console.log("Resposta do servidor:", data);
                                alert("Seleção de arquivos aplicada com sucesso!");
                            })
                            .catch((err) => {
                                console.error("Erro ao enviar seleção de arquivos:", err);
                                alert("Erro ao aplicar seleção: " + err.message);
                            });

                        isListingFiles = false; // Retoma atualizações automáticas
                        container.innerHTML = ""; // Limpa a tabela
                        fetchDownloads(); // Atualiza os downloads
                    });
                };

                renderTable();
            })
            .catch((err) => {
                console.error(err);
                alert("Erro ao listar arquivos: " + err.message);
                isListingFiles = false;
                container.innerHTML = "";
                fetchDownloads();
            });
    }

    // Adiciona listeners aos botões de ação
    function addActionListeners(downloadItem) {
        const torrentId = downloadItem.dataset.id;

        // Botão Parar (se presente)
        const stopButton = downloadItem.querySelector(".btn-stop");
        if (stopButton) {
            stopButton.addEventListener("click", () => {
                fetch(`/torrent/stop/${torrentId}`, { method: "POST" })
                    .then((response) => response.json())
                    .then((data) => {
                        alert(data.message);
                        fetchDownloads(); // Atualiza os downloads após parar
                    })
                    .catch((err) => console.error(err));
            });
        }

        // Botão Continuar (se presente)
        const resumeButton = downloadItem.querySelector(".btn-resume");
        if (resumeButton) {
            resumeButton.addEventListener("click", () => {
                fetch(`/torrent/resume/${torrentId}`, { method: "POST" })
                    .then((response) => response.json())
                    .then((data) => {
                        alert(data.message);
                        fetchDownloads(); // Atualiza os downloads após continuar
                    })
                    .catch((err) => console.error(err));
            });
        }

        // Botão Cancelar
        downloadItem
            .querySelector(".btn-cancel")
            .addEventListener("click", () => {
                if (confirm("Tem certeza que deseja cancelar este download? Os arquivos baixados serão mantidos.")) {
                    fetch(`/torrent/cancel/${torrentId}`, { method: "POST" })
                        .then((response) => response.json())
                        .then((data) => {
                            alert(data.message);
                            fetchDownloads(); // Atualiza os downloads após cancelar
                        })
                        .catch((err) => console.error(err));
                }
            });

        // Botão Apagar
        downloadItem
            .querySelector(".btn-delete")
            .addEventListener("click", () => {
                if (confirm("Tem certeza que deseja apagar este download e TODOS os arquivos já baixados?")) {
                    fetch(`/torrent/delete/${torrentId}`, { method: "POST" })
                        .then((response) => response.json())
                        .then((data) => {
                            alert(data.message);
                            fetchDownloads(); // Atualiza os downloads após apagar
                        })
                        .catch((err) => console.error(err));
                }
            });

        // Botão Listar Arquivos
        downloadItem
            .querySelector(".btn-list-files")
            .addEventListener("click", () => {
                const container = downloadItem.querySelector(".actions");
                listFiles(torrentId, container);
            });
    }

    // Manipula o envio do formulário para adicionar novo download
    form.addEventListener("submit", (event) => {
        event.preventDefault(); // Impede o comportamento padrão do formulário
        const magnetLink = document.getElementById("magnet_link").value;

        const formData = new FormData(); // Cria um FormData
        formData.append("magnet_link", magnetLink); // Adiciona o magnet link

        fetch("/torrent/", {
            method: "POST",
            body: formData, // Envia o FormData como corpo da requisição
        })
            .then((response) => {
                if (response.ok) {
                    // Se a resposta foi bem-sucedida, atualiza a lista de downloads
                    alert("Download adicionado com sucesso!");
                    document.getElementById("magnet_link").value = ""; // Limpa o campo de entrada
                    fetchDownloads(); // Atualiza a lista de downloads
                } else {
                    return response.text().then((text) => {
                        throw new Error(text || "Erro ao adicionar o download.");
                    });
                }
            })
            .catch((err) => {
                console.error(err);
                alert("Erro: " + err.message);
            });
    });

    // Atualiza a lista de downloads a cada 5 segundos
    setInterval(fetchDownloads, 5000);

    // Carrega os downloads inicialmente
    fetchDownloads();
});