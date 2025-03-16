document.addEventListener("DOMContentLoaded", () => {
  let currentPath = "";
  let selectedItems = new Set(); // Para rastrear itens selecionados

  const messagesDiv = document.getElementById("messages");
  const navigationDiv = document.getElementById("navigation");
  const filesTableBody = document.querySelector("#files-table tbody");
  const uploadForm = document.getElementById("upload-form");
  const createFolderForm = document.getElementById("create-folder-form");
  const searchForm = document.getElementById("search-form");
  const searchInput = document.getElementById("search-input");
  const deleteSelectedBtn = document.getElementById("delete-selected-btn");
  const selectAllCheckbox = document.getElementById("select-all");

  // Função para exibir mensagens
  function showMessage(message, isError = false) {
    const msg = document.createElement("div");
    msg.className = isError ? "error-message" : "success-message";
    msg.innerHTML = isError
      ? `<i class="fas fa-exclamation-circle"></i> ${message}`
      : `<i class="fas fa-check-circle"></i> ${message}`;
    messagesDiv.innerHTML = ""; // Limpar mensagens anteriores
    messagesDiv.appendChild(msg);
    setTimeout(() => {
      msg.remove();
    }, 5000);
  }

  // Função para atualizar a navegação
  function updateNavigation() {
    navigationDiv.innerHTML = "";
    const backLink = document.createElement("a");
    backLink.href = "#";
    backLink.innerHTML = '<i class="fas fa-home"></i> Início';
    backLink.addEventListener("click", (e) => {
      e.preventDefault();
      currentPath = "";
      loadDirectory();
    });
    navigationDiv.appendChild(backLink);

    if (currentPath) {
      const pathParts = currentPath.split("/").filter(part => part);
      let pathAccumulator = "";

      pathParts.forEach((part, index) => {
        navigationDiv.appendChild(document.createTextNode(" / "));
        pathAccumulator += (index > 0 ? "/" : "") + part;
        const link = document.createElement("a");
        link.href = "#";
        link.innerText = part;
        link.addEventListener("click", (e) => {
          e.preventDefault();
          currentPath = pathAccumulator;
          loadDirectory();
        });
        navigationDiv.appendChild(link);
      });
    }
  }

  // Função para obter o ícone apropriado para o tipo de arquivo
  function getFileIcon(filename) {
    const extension = filename.split('.').pop().toLowerCase();

    const iconMap = {
      // Documentos
      'pdf': 'fas fa-file-pdf',
      'doc': 'fas fa-file-word',
      'docx': 'fas fa-file-word',
      'xls': 'fas fa-file-excel',
      'xlsx': 'fas fa-file-excel',
      'ppt': 'fas fa-file-powerpoint',
      'pptx': 'fas fa-file-powerpoint',
      'txt': 'fas fa-file-alt',
      'rtf': 'fas fa-file-alt',

      // Imagens
      'jpg': 'fas fa-file-image',
      'jpeg': 'fas fa-file-image',
      'png': 'fas fa-file-image',
      'gif': 'fas fa-file-image',
      'bmp': 'fas fa-file-image',
      'svg': 'fas fa-file-image',
      'webp': 'fas fa-file-image',

      // Áudio/Vídeo
      'mp3': 'fas fa-file-audio',
      'wav': 'fas fa-file-audio',
      'ogg': 'fas fa-file-audio',
      'mp4': 'fas fa-file-video',
      'avi': 'fas fa-file-video',
      'mov': 'fas fa-file-video',
      'mkv': 'fas fa-file-video',
      'webm': 'fas fa-file-video',

      // Arquivos compactados
      'zip': 'fas fa-file-archive',
      'rar': 'fas fa-file-archive',
      '7z': 'fas fa-file-archive',
      'tar': 'fas fa-file-archive',
      'gz': 'fas fa-file-archive',

      // Código
      'html': 'fas fa-file-code',
      'css': 'fas fa-file-code',
      'js': 'fas fa-file-code',
      'py': 'fas fa-file-code',
      'java': 'fas fa-file-code',
      'php': 'fas fa-file-code',
      'c': 'fas fa-file-code',
      'cpp': 'fas fa-file-code',
      'h': 'fas fa-file-code',
      'json': 'fas fa-file-code',
      'xml': 'fas fa-file-code',
    };

    return iconMap[extension] || 'fas fa-file';
  }

  // Função para carregar o diretório atual
  function loadDirectory() {
    fetch(`/filemanager/api/list?path=${encodeURIComponent(currentPath)}`)
      .then(response => {
        if (!response.ok) {
          throw new Error(`Erro ao carregar diretório: ${response.statusText}`);
        }
        return response.json();
      })
      .then(data => {
        if (data.type === "folder") {
          updateNavigation();
          renderFiles(data.items);
        } else {
          // Se for um arquivo, iniciar download
          window.location.href = `/filemanager/download/${encodeURIComponent(currentPath)}`;
        }
      })
      .catch(error => {
        showMessage(`Erro ao carregar diretório: ${error.message}`, true);
        console.error(error);
      });

    // Resetar seleções ao mudar de diretório
    selectedItems.clear();
    updateDeleteButton();
  }

  // Função para renderizar arquivos e pastas na tabela
  function renderFiles(items) {
    filesTableBody.innerHTML = "";

    // Adicionar link para voltar se não estivermos na raiz
    if (currentPath) {
      const row = document.createElement("tr");

      const checkboxCell = document.createElement("td");
      const checkbox = document.createElement("input");
      checkbox.type = "checkbox";
      checkbox.disabled = true; // Não permitir seleção deste item
      checkboxCell.appendChild(checkbox);
      row.appendChild(checkboxCell);

      const nameCell = document.createElement("td");
      const link = document.createElement("a");
      link.href = "#";
      link.innerHTML = '<i class="fas fa-arrow-left"></i> Voltar';
      link.addEventListener("click", e => {
        e.preventDefault();
        const parts = currentPath.split("/").filter(part => part);
        parts.pop();
        currentPath = parts.join("/");
        loadDirectory();
      });
      nameCell.appendChild(link);
      row.appendChild(nameCell);

      filesTableBody.appendChild(row);
    }

    // Ordenar: pastas primeiro, depois arquivos, ambos em ordem alfabética
    const sortedItems = [...items].sort((a, b) => {
      if (a.type !== b.type) {
        return a.type === "folder" ? -1 : 1;
      }
      return a.name.localeCompare(b.name);
    });

    if (sortedItems.length === 0) {
      const row = document.createElement("tr");
      const cell = document.createElement("td");
      cell.colSpan = 2;
      cell.innerText = "Esta pasta está vazia";
      cell.style.textAlign = "center";
      cell.style.padding = "20px";
      row.appendChild(cell);
      filesTableBody.appendChild(row);
    } else {
      sortedItems.forEach(item => {
        const row = document.createElement("tr");
        const isFolder = item.type === "folder";

        // Coluna de checkbox
        const checkboxCell = document.createElement("td");
        const checkbox = document.createElement("input");
        checkbox.type = "checkbox";
        checkbox.className = "select-item";
        checkbox.value = item.name;
        checkbox.addEventListener("change", (e) => {
          if (e.target.checked) {
            selectedItems.add(item.name);
          } else {
            selectedItems.delete(item.name);
          }
          updateDeleteButton();
        });
        checkboxCell.appendChild(checkbox);
        row.appendChild(checkboxCell);

        // Coluna de nome
        const nameCell = document.createElement("td");
        nameCell.className = "item-name";

        // Ícone
        const icon = document.createElement("i");
        icon.className = isFolder ? "fas fa-folder" : getFileIcon(item.name);

        const textSpan = document.createElement("span");
        textSpan.textContent = item.name + (isFolder ? "/" : "");

        if (isFolder) {
          const link = document.createElement("a");
          link.href = "#";
          link.appendChild(icon);
          link.appendChild(textSpan);
          link.addEventListener("click", e => {
            e.preventDefault();
            currentPath = currentPath ? `${currentPath}/${item.name}` : item.name;
            loadDirectory();
          });
          nameCell.appendChild(link);
        } else {
          const link = document.createElement("a");
          link.href = `/filemanager/download/${encodeURIComponent(
            currentPath ? currentPath + "/" + item.name : item.name
          )}`;
          link.appendChild(icon);
          link.appendChild(textSpan);
          nameCell.appendChild(link);
        }

        row.appendChild(nameCell);
        filesTableBody.appendChild(row);
      });
    }

    // Resetar o checkbox "Selecionar Todos"
    selectAllCheckbox.checked = false;
  }

  // Função para atualizar o estado do botão de exclusão
  function updateDeleteButton() {
    deleteSelectedBtn.disabled = selectedItems.size === 0;
  }

  // Função para deletar itens selecionados
  function deleteSelectedItems() {
    if (selectedItems.size === 0) {
      showMessage("Nenhum item selecionado para deletar.", true);
      return;
    }

    const targets = Array.from(selectedItems);

    if (!confirm(`Tem certeza que deseja deletar os itens selecionados: ${targets.join(", ")}?`)) {
      return;
    }

    fetch("/filemanager/api/delete_multiple", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        current_path: currentPath,
        targets: targets,
      }),
    })
      .then(response => response.json())
      .then(data => {
        if (data.success) {
          showMessage(data.message);
          selectedItems.clear(); // Limpar seleções após exclusão
          loadDirectory();
        } else {
          showMessage(data.message, true);
        }
      })
      .catch(error => {
        showMessage(`Erro ao deletar itens selecionados: ${error.message}`, true);
        console.error(error);
      });
  }

  // Manipulador de envio do formulário de upload
  uploadForm.addEventListener("submit", e => {
    e.preventDefault();
    const fileInput = document.getElementById("file-input");
    const files = fileInput.files;
    if (!files.length) {
      showMessage("Selecione pelo menos um arquivo para upload", true);
      return;
    }

    const formData = new FormData();
    for (let i = 0; i < files.length; i++) {
      formData.append("files", files[i]);
    }
    formData.append("current_path", currentPath);

    fetch("/filemanager/api/upload", {
      method: "POST",
      body: formData,
    })
      .then(response => response.json())
      .then(data => {
        if (data.success) {
          showMessage(data.message);
          uploadForm.reset();
          loadDirectory();
        } else {
          showMessage(data.message, true);
        }
      })
      .catch(error => {
        showMessage(`Erro ao fazer upload: ${error.message}`, true);
        console.error(error);
      });
  });

  // Manipulador de envio do formulário de criação de pasta
  createFolderForm.addEventListener("submit", e => {
    e.preventDefault();
    const folderNameInput = document.getElementById("folder-name-input");
    const folderName = folderNameInput.value.trim();
    if (!folderName) {
      showMessage("Digite um nome para a pasta", true);
      return;
    }

    const formData = new FormData();
    formData.append("folder_name", folderName);
    formData.append("current_path", currentPath);

    fetch("/filemanager/api/create_folder", {
      method: "POST",
      body: formData,
    })
      .then(response => response.json())
      .then(data => {
        if (data.success) {
          showMessage(data.message);
          createFolderForm.reset();
          loadDirectory();
        } else {
          showMessage(data.message, true);
        }
      })
      .catch(error => {
        showMessage(`Erro ao criar pasta: ${error.message}`, true);
        console.error(error);
      });
  });

  // Manipulador de envio do formulário de pesquisa
  searchForm.addEventListener("submit", e => {
    e.preventDefault();
    const query = searchInput.value.trim();
    if (!query) {
      showMessage("Digite algo para pesquisar", true);
      return;
    }

    fetch(`/filemanager/api/search?q=${encodeURIComponent(query)}`)
      .then(response => response.json())
      .then(data => {
        if (data.success) {
          renderSearchResults(data.results, query);
        } else {
          showMessage(data.message, true);
        }
      })
      .catch(error => {
        showMessage(`Erro ao realizar pesquisa: ${error.message}`, true);
        console.error(error);
      });
  });

  // Função para renderizar resultados de pesquisa
  function renderSearchResults(results, query) {
    filesTableBody.innerHTML = "";

    // Atualizar a navegação para mostrar que estamos vendo resultados de pesquisa
    navigationDiv.innerHTML = `
      <a href="#" onclick="event.preventDefault(); document.getElementById('search-input').value=''; loadDirectory();"><i class="fas fa-home"></i> Início</a>
      <span class="separator"> / </span>
      <span>Resultados da pesquisa: "${query}" (${results.length} encontrados)</span>
    `;

    if (results.length === 0) {
      const row = document.createElement("tr");
      const cell = document.createElement("td");
      cell.colSpan = 2;
      cell.innerText = "Nenhum resultado encontrado.";
      cell.style.textAlign = "center";
      cell.style.padding = "20px";
      row.appendChild(cell);
      filesTableBody.appendChild(row);
      return;
    }

    // Ordenar: pastas primeiro, depois arquivos
    const sortedResults = [...results].sort((a, b) => {
      if (a.type !== b.type) {
        return a.type === "folder" ? -1 : 1;
      }
      return a.path.localeCompare(b.path);
    });

    sortedResults.forEach(item => {
      const row = document.createElement("tr");
      const isFolder = item.type === "folder";

      // Coluna de checkbox (desabilitado para resultados de pesquisa)
      const checkboxCell = document.createElement("td");
      const checkbox = document.createElement("input");
      checkbox.type = "checkbox";
      checkbox.disabled = true; // Desabilitar checkbox nos resultados de pesquisa
      checkboxCell.appendChild(checkbox);
      row.appendChild(checkboxCell);

      // Coluna de nome com ícone e caminho
      const nameCell = document.createElement("td");
      nameCell.className = "item-name search-result";

      // Ícone conforme o tipo
      const icon = document.createElement("i");
      icon.className = isFolder ? "fas fa-folder" : getFileIcon(item.name);

      // Link para navegação ou download
      const link = document.createElement("a");
      link.href = "#";

      // Texto do item
      const textSpan = document.createElement("span");
      textSpan.textContent = item.name + (isFolder ? "/" : "");

      // Adicionar o caminho completo
      const pathSpan = document.createElement("span");
      pathSpan.className = "file-path";
      pathSpan.textContent = ` (${item.path})`;

      link.appendChild(icon);
      link.appendChild(textSpan);

      if (isFolder) {
        link.addEventListener("click", e => {
          e.preventDefault();
          currentPath = item.path;
          loadDirectory();
        });
      } else {
        // Para arquivos, vamos permitir navegar até a pasta
        const pathParts = item.path.split("/");
        pathParts.pop(); // Remover o nome do arquivo
        const dirPath = pathParts.join("/");

        link.addEventListener("click", e => {
          e.preventDefault();
          currentPath = dirPath;
          loadDirectory();
        });

        // Botão de download
        const downloadBtn = document.createElement("a");
        downloadBtn.href = `/filemanager/download/${encodeURIComponent(item.path)}`;
        downloadBtn.innerHTML = '<i class="fas fa-download"></i>';
        downloadBtn.title = "Download direto";
        downloadBtn.className = "download-button";

        nameCell.appendChild(link);
        nameCell.appendChild(pathSpan);
        nameCell.appendChild(downloadBtn);
        row.appendChild(nameCell);
        filesTableBody.appendChild(row);
        return;
      }

      nameCell.appendChild(link);
      nameCell.appendChild(pathSpan);
      row.appendChild(nameCell);
      filesTableBody.appendChild(row);
    });
  }

  // Adicionar evento ao botão "Deletar Selecionados"
  deleteSelectedBtn.addEventListener("click", deleteSelectedItems);

  // Adicionar evento ao checkbox "Selecionar Todos"
  selectAllCheckbox.addEventListener("change", e => {
    const isChecked = e.target.checked;
    const itemCheckboxes = document.querySelectorAll(".select-item");

    selectedItems.clear();

    itemCheckboxes.forEach(cb => {
      cb.checked = isChecked;
      if (isChecked) {
        selectedItems.add(cb.value);
      }
    });

    updateDeleteButton();
  });

  // Função para carregar o diretório e torná-la disponível globalmente
  window.loadDirectory = loadDirectory;

  // Carrega o diretório inicial
  loadDirectory();
});