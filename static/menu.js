(function () {
    const MENU_ITEMS = [
        { label: 'Torrents', icon: '⬇', url: '/torrent/' },
        { label: 'Magnet Links', icon: '🔗', url: '/magnet/' },
        { label: 'Arquivos', icon: '📁', url: '/filemanager/' },
        { label: 'Downloads', icon: '📦', url: '/downloads' },
        { label: 'Monitor', icon: '📊', url: '/monitor/dashboard/' },
        { label: 'Configurações', icon: '⚙', url: '/config' },
        { label: 'Inicio', icon: '🏠', url: '/' },
    ];

    const style = document.createElement('style');
    style.textContent = `
        /* Overlay */
        #float-menu-overlay {
            position: fixed;
            inset: 0;
            background: rgba(0, 0, 0, 0.55);
            backdrop-filter: blur(3px);
            -webkit-backdrop-filter: blur(3px);
            z-index: 9990;
            opacity: 0;
            pointer-events: none;
            transition: opacity 0.22s ease;
        }
        #float-menu-overlay.open {
            opacity: 1;
            pointer-events: auto;
        }

        /* Botão flutuante */
        #float-menu-btn {
            position: fixed;
            bottom: 20px;
            right: 20px;
            z-index: 9999;
            background: #2a2a2a;
            color: #888;
            border: 1px solid #444;
            border-radius: 6px;
            padding: 5px 10px;
            font-size: 11px;
            font-weight: 600;
            letter-spacing: 0.06em;
            cursor: pointer;
            box-shadow: 0 2px 8px rgba(0,0,0,0.4);
            transition: background 0.2s, color 0.2s, border-color 0.2s;
            user-select: none;
            max-width: 100px;
        }
        #float-menu-btn:hover { background: #3a3a3a; color: #ccc; border-color: #666; }
        #float-menu-btn.open  { background: #3c3c3c; color: #aaa; }

        /* Painel do menu */
        #float-menu-panel {
            position: fixed;
            bottom: 80px;
            right: 24px;
            z-index: 9998;
            background: #1e1e1e;
            border: 1px solid #3c3c3c;
            border-radius: 14px;
            padding: 8px;
            min-width: 220px;
            box-shadow: 0 12px 40px rgba(0,0,0,0.7);

            opacity: 0;
            transform: translateY(12px) scale(0.96);
            transform-origin: bottom right;
            pointer-events: none;
            transition: opacity 0.2s ease, transform 0.2s ease;
        }
        #float-menu-panel.open {
            opacity: 1;
            transform: translateY(0) scale(1);
            pointer-events: auto;
        }

        /* Cabeçalho do painel */
        #float-menu-header {
            padding: 8px 12px 10px;
            font-size: 10px;
            font-weight: 700;
            letter-spacing: 0.1em;
            text-transform: uppercase;
            color: #555;
            border-bottom: 1px solid #2d2d2d;
            margin-bottom: 4px;
        }

        /* Itens */
        .float-menu-item {
            display: flex;
            align-items: center;
            gap: 12px;
            padding: 10px 14px;
            border-radius: 9px;
            text-decoration: none;
            color: #c8c8c8;
            font-size: 13px;
            font-weight: 500;
            transition: background 0.15s, color 0.15s;
            position: relative;
        }
        .float-menu-item:hover {
            background: #2a2d2e;
            color: #fff;
        }
        .float-menu-item.active-page {
            background: #1a3a5c;
            color: #4db8ff;
        }
        .float-menu-item.active-page::before {
            content: '';
            position: absolute;
            left: 0;
            top: 20%;
            height: 60%;
            width: 3px;
            background: #0078d4;
            border-radius: 2px;
        }
        .fmi-icon {
            font-size: 15px;
            width: 22px;
            text-align: center;
            flex-shrink: 0;
        }
        .fmi-label { flex: 1; }

        /* Separador */
        .float-menu-sep {
            height: 1px;
            background: #2d2d2d;
            margin: 4px 8px;
        }
    `;
    document.head.appendChild(style);

    const currentPath = window.location.pathname;

    // Overlay
    const overlay = document.createElement('div');
    overlay.id = 'float-menu-overlay';

    // Painel
    const panel = document.createElement('div');
    panel.id = 'float-menu-panel';

    const header = document.createElement('div');
    header.id = 'float-menu-header';
    header.textContent = 'Navegação';
    panel.appendChild(header);

    MENU_ITEMS.forEach((item, i) => {
        if (i === 4) {
            const sep = document.createElement('div');
            sep.className = 'float-menu-sep';
            panel.appendChild(sep);
        }

        const a = document.createElement('a');
        a.className = 'float-menu-item';
        a.href = item.url;

        const icon = document.createElement('span');
        icon.className = 'fmi-icon';
        icon.textContent = item.icon;

        const label = document.createElement('span');
        label.className = 'fmi-label';
        label.textContent = item.label;

        a.appendChild(icon);
        a.appendChild(label);

        if (currentPath === item.url ||
            (item.url !== '/' && currentPath.startsWith(item.url))) {
            a.classList.add('active-page');
        }

        panel.appendChild(a);
    });

    // Botão
    const btn = document.createElement('button');
    btn.id = 'float-menu-btn';
    btn.textContent = 'Menu';

    let open = false;

    function toggleMenu(force) {
        open = force !== undefined ? force : !open;
        panel.classList.toggle('open', open);
        overlay.classList.toggle('open', open);
        btn.classList.toggle('open', open);
        btn.textContent = open ? '✕ Fechar' : 'Menu';
    }

    btn.addEventListener('click', (e) => {
        e.stopPropagation();
        toggleMenu();
    });

    overlay.addEventListener('click', () => toggleMenu(false));
    panel.addEventListener('click', (e) => e.stopPropagation());

    document.body.appendChild(overlay);
    document.body.appendChild(panel);
    document.body.appendChild(btn);
})();
