// ===========================================================================
// translations.js — All UI strings for Duplicate Finder
// Add new language: add a key under TRANSLATIONS matching the lang code.
// ===========================================================================

const TRANSLATIONS = {
  de: {
    // Nav Rail
    nav_scan: 'Scan', nav_library: 'Mediathek', nav_scans: 'Scans',
    nav_history: 'Verlauf', nav_db: 'DB', nav_user: 'User', nav_exit: 'Exit',
    nav_help: 'Hilfe',
    // Sidebar
    directories: 'Verzeichnisse',
    tree_click: 'Baum-Klick setzt:',
    // Settings
    dir1_label: 'Verz 1:', dir2_label: 'Verz 2:',
    compare_toggle: 'Vergleichsmodus',
    tree_click_sets: 'Baum-Klick setzt:',
    placeholder_path1: '/path/to/your/media',
    placeholder_path2: '/path/to/your/media2',
    media_type_label: 'Medientyp',
    opt_images: 'Bilder', opt_videos: 'Videos', opt_both: 'Bilder + Videos',
    phash_threshold_lbl: 'pHash-Schwellenwert',
    min_frame_matches: 'Min. Frame-Treffer',
    duration_tolerance: 'Dauer-Toleranz (s)',
    intensiv: 'Intensiver Abgleich',
    edge_section: 'Rand-Abschnitt:',
    worker: 'Worker',
    scan_start: 'Scan starten',
    dir_hint: 'Verzeichnis wählen und Scan starten.',
    // Modal
    modal_titel: 'Löschen bestätigen',
    modal_cancel: 'Abbrechen',
    modal_bestaetigen: 'Löschen',
    // Library sort
    sortierung: 'Sortierung:',
    sort_name: 'Name', sort_date: 'Datum', sort_size: 'Größe',
    // View headings (used in renderX functions)
    datenbank: 'Datenbank',
    delete_history_label: 'Lösch-Verlauf',
    scan_history_label: 'Scan-Verlauf',
    user_management: 'Benutzerverwaltung',
    // Login
    login_title_key: 'Anmelden',
    login_subtitle: 'Duplikat-Finder',
    login_btn: 'Anmelden',
    login_username_lbl: 'Benutzername',
    login_password_lbl: 'Passwort',
    setup_title: 'Ersteinrichtung',
    setup_subtitle: 'Ersten Administrator-Account anlegen',
    setup_btn: 'Account anlegen',
    // Validation / errors
    fill_fields: 'Bitte alle Felder ausfüllen.',
    pass_min_chars_error: 'Passwort muss mindestens 6 Zeichen haben.',
    connection_error: 'Verbindungsfehler.',
    login_failed: 'Anmeldung fehlgeschlagen.',
    setup_error: 'Fehler bei der Einrichtung.',
    // Scan status
    loading: 'Lade…',
    scan_running: 'Scan läuft…',
    scan_waiting: 'Scan wartet…',
    scan_started: '▶ Scan gestartet.',
    scan_cancelled: 'Scan abgebrochen.',
    scan_error_toast: 'Scan-Fehler aufgetreten.',
    scan_error_log: 'Scan-Fehler — siehe Log oben.',
    connection_lost: 'Verbindung zum Server unterbrochen.',
    scan_queued: '⏳ Scan eingereiht — wartet auf laufenden Scan…',
    scan_not_started: 'Scan konnte nicht gestartet werden: ',
    select_dir: 'Bitte ein Verzeichnis wählen.',
    stop: '⏹ Stoppen',
    stopping: '⏳ Wird gestoppt…',
    results_load_error: 'Ergebnisse konnten nicht geladen werden: ',
    last_scan_lbl: '↩ Letzter Scan: ',
    show_results: 'Ergebnisse anzeigen →',
    scan_banner_text: '⟳ Scan läuft…',
    click_show: 'Klicken zum Anzeigen',
    click_go_back: 'Klicken um zum Scan zurückzukehren',
    // Results
    groups: 'Gruppen',
    files_pl: 'Dateien',
    wasted: 'verschwendet',
    image_exact_lbl: 'Exakte Bild-Duplikate',
    image_visual_lbl: 'Visuelle Bild-Duplikate',
    video_exact_lbl: 'Exakte Video-Duplikate',
    video_visual_lbl: 'Visuelle Video-Duplikate',
    video_intensive_lbl: 'Intensiv-Duplikate (Start/End-Block)',
    cross_dir: ' (Cross-Dir)',
    storage_wasted: 'Verschwendeter Speicher (ca.):',
    unprocessable: '⚠ Nicht verarbeitbar:',
    unprocessable_title: 'Nicht verarbeitbare Dateien',
    gruppe_nr: 'Gruppe #',
    none_found: 'Keine gefunden.',
    deselect_all: 'Alle de-/selektieren',
    delete_selected: 'Ausgewählte löschen',
    keep_badge: '✓ Beste Qualität',
    delete_badge: '✗ Löschen',
    also_delete: 'Löschen',
    mark_delete: 'Löschen',
    no_preview: 'Keine Vorschau',
    no_preview_video: '🎬 Keine Vorschau',
    link_title_img: 'Linksklick: Lightbox — Mittelklick: Neuer Tab',
    link_title_vid: 'Linksklick: Player — Mittelklick: Neuer Tab',
    frame_click: '— Klick: Großansicht',
    phash_0: 'pixelidentisch',
    phash_low: 'fast identisch',
    phash_mid: 'sehr ähnlich',
    phash_high: 'ähnlich',
    new_scan: '← Neuer Scan',
    goBack: '← Zurück',
    // Counter (pluralizable)
    marked_n: (n) => `${n} Datei${n !== 1 ? 'en' : ''} zum Löschen markiert`,
    delete_n: (n) => `${n} Datei${n !== 1 ? 'en' : ''} unwiderruflich löschen?`,
    files_n: (n) => `${n} Datei${n !== 1 ? 'en' : ''}`,
    freed_text: (n) => `durch Löschen von Duplikaten gespart — ${n} Datei${n !== 1 ? 'en' : ''} gelöscht`,
    error_n: (n) => `Fehler bei ${n} Datei${n !== 1 ? 'en' : ''}:\n`,
    cleanup_done_msg: (b, v) => `Bereinigt: ${b} Bild-Einträge, ${v} Video-Einträge entfernt.`,
    delete_user_confirm: (name) => `Benutzer "${name}" wirklich löschen?`,
    // Scan history
    hist_date: 'Datum', hist_dir: 'Verzeichnis', hist_status: 'Status',
    no_scan_yet: 'Noch keine Scans gespeichert.',
    status_done: '✓ Fertig', status_error: '✗ Fehler',
    status_cancelled: '⏹ Abgebrochen', status_running: '⟳ Läuft',
    load_results: 'Ergebnisse laden',
    // Delete history
    db_size: 'Datenbankgröße',
    hist_filename: 'Dateiname', hist_directory: 'Verzeichnis',
    hist_size: 'Größe', hist_deleted_at: 'Gelöscht am',
    no_deletes_yet: 'Noch keine Dateien gelöscht.',
    clear_history_btn: 'Verlauf löschen',
    clear_history_confirm: 'Gesamten Lösch-Verlauf unwiderruflich löschen?',
    // Database
    cached_images: 'Gecachte Bilder:', cached_videos: 'Gecachte Videos:',
    db_file: 'Datenbankdatei:',
    cache_reset_btn: 'Scan-Cache zurücksetzen',
    cache_reset_info: 'Löscht alle gecachten Hashes und Metadaten. Die Lösch-Historie bleibt erhalten. Beim nächsten Scan werden alle Dateien neu verarbeitet.',
    cache_reset_confirm: 'Scan-Cache zurücksetzen?\n\nAlle gecachten Bild- und Video-Daten werden gelöscht. Die Lösch-Historie bleibt erhalten.',
    cleanup_btn: 'Veraltete Einträge bereinigen',
    cleanup_info: 'Entfernt Cache-Einträge für Dateien die nicht mehr auf dem Dateisystem existieren (z.B. gelöscht oder verschoben).',
    // Users
    existing_users: 'Vorhandene Benutzer',
    no_users: 'Keine Benutzer vorhanden.',
    username_col: 'Benutzername', created_col: 'Erstellt',
    you_label: '(du)',
    delete_btn_small: 'Löschen',
    no_self_delete: 'Eigenen Account kann man nicht löschen',
    add_user: 'Benutzer hinzufügen',
    username_lbl: 'Benutzername',
    password_lbl: 'Passwort',
    min_chars_hint: 'mind. 6 Zeichen',
    create_btn: 'Anlegen',
    change_pw_title: 'Eigenes Passwort ändern',
    new_pw_lbl: 'Neues Passwort',
    save_btn: 'Speichern',
    pw_changed: 'Passwort erfolgreich geändert.',
    // Library
    no_dir: 'Kein Verzeichnis ausgewählt.',
    empty_library: 'Keine Bilder oder Videos in diesem Verzeichnis.',
    open_in_tab: 'In neuem Tab öffnen',
    open_library: 'Mediathek öffnen',
    setup_scan: 'Scan einrichten',
    // Error / misc
    click_close: ' (klicken zum Schließen)',
    error_msg: 'Fehler: ',

    // ===========================================================================
    // Help page
    // ===========================================================================
    help_title: 'Hilfe & Dokumentation',

    help_usage_title: 'Bedienung',
    help_usage_html: `
<section class="help-section">
  <h3>1. Verzeichnis wählen</h3>
  <p>Im Ordnerbaum links ein Verzeichnis anklicken. Der gewählte Pfad wird automatisch in das Scan-Formular übernommen.</p>
  <p>Mit <strong>Vergleichsmodus</strong> lassen sich zwei Verzeichnisse gegeneinander prüfen — nützlich z.B. um ein Backup mit dem Original zu vergleichen. Ist der Vergleichsmodus aktiv, erscheint unterhalb des Baums ein kleiner Selektor <em>„Baum-Klick setzt"</em>. Damit legst du fest, welches Verzeichnis der nächste Klick im Baum befüllt — <strong style="color:#80c0ff">Verz&nbsp;1</strong> (blau) oder <strong style="color:#ff8080">Verz&nbsp;2</strong> (rot). Einfach Ziel umschalten, dann das gewünschte Verzeichnis im Baum anklicken.</p>
</section>
<section class="help-section">
  <h3>2. Scan konfigurieren</h3>
  <dl>
    <dt>Medientyp</dt>
    <dd>Wähle ob Bilder, Videos oder beides gescannt werden sollen.</dd>
    <dt>pHash-Schwellenwert (Bilder)</dt>
    <dd>Bestimmt wie ähnlich zwei Bilder sein müssen um als Duplikat zu gelten. <strong>0</strong> = pixelidentisch, <strong>8</strong> = sehr ähnlich, <strong>16+</strong> = locker (mehr Treffer, mehr Fehlalarme). Empfehlung: 6–10.</dd>
    <dt>Min. Frame-Treffer (Videos)</dt>
    <dd>Wie viele übereinstimmende Frames ein Videopaar mindestens haben muss. Höherer Wert = strengerer Abgleich.</dd>
    <dt>Dauer-Toleranz (Videos)</dt>
    <dd>Maximale Abweichung der Videolänge in Sekunden. Videos mit sehr unterschiedlicher Länge werden damit ausgeschlossen.</dd>
    <dt>Intensiver Abgleich</dt>
    <dd>Vergleicht zusätzlich die ersten und letzten X Sekunden jedes Videos (Standard: 30 s, einstellbar von 5–120 s). Findet auch Kopien mit abweichenden Mittelbereichen (z.B. re-encodiert mit anderen Credits). Erhöht die Scanzeit spürbar bei großen Bibliotheken.</dd>
    <dt>Rand-Abschnitt</dt>
    <dd>Dauer des Start-/End-Blocks in Sekunden (Standard: 30 s, Min: 5 s, Max: 120 s). Nur beim intensiven Abgleich relevant.</dd>
    <dt>Worker</dt>
    <dd>Anzahl paralleler Prozesse. Mehr Worker = schneller, aber mehr CPU- und RAM-Last.</dd>
  </dl>
</section>
<section class="help-section">
  <h3>3. Scan starten & Fortschritt verfolgen</h3>
  <p>Klicke <strong>Scan starten</strong>. Der Fortschritt wird in Echtzeit im Log angezeigt. Ein laufender Scan kann jederzeit gestoppt werden. Läuft bereits ein Scan, wird der neue eingereiht und startet automatisch danach.</p>
  <p>Der Banner am oberen Rand zeigt den Scan-Fortschritt auch wenn man zu einer anderen Ansicht wechselt — Klick darauf springt zurück zum Scan.</p>
</section>
<section class="help-section">
  <h3>4. Ergebnisse auswerten</h3>
  <p>Nach dem Scan werden Duplikat-Gruppen angezeigt, unterteilt in:</p>
  <ul>
    <li><strong>Exakte Duplikate</strong> — identischer MD5-Hash</li>
    <li><strong>Visuelle Duplikate</strong> — ähnlicher perceptual Hash</li>
    <li><strong>Intensiv-Duplikate</strong> (Videos) — ähnliche Start-/End-Blöcke</li>
  </ul>
  <p>Innerhalb jeder Gruppe wird die Datei mit der besten Qualität (höchste Auflösung / größte Dateigröße) automatisch mit <em>Beste Qualität</em> markiert — alle anderen als Löschen-Kandidaten vorgeschlagen. Die Markierung kann manuell angepasst werden.</p>
</section>
<section class="help-section">
  <h3>5. Dateien löschen</h3>
  <p>Markierte Dateien werden über den roten <strong>Ausgewählte löschen</strong>-Button nach einer Bestätigung endgültig vom Dateisystem entfernt. Der Lösch-Verlauf ist unter <em>Verlauf</em> einsehbar.</p>
  <p><strong>Achtung:</strong> Das Löschen ist unwiderruflich. Es gibt keinen Papierkorb.</p>
</section>
<section class="help-section">
  <h3>6. Mediathek</h3>
  <p>Zeigt alle Bilder und Videos im gewählten Verzeichnis als Grid. Bilder lassen sich per Klick in einer Lightbox vergrößern, Videos im eingebetteten Player abspielen. Sortierung nach Name, Datum oder Dateigröße möglich.</p>
</section>`,

    help_technical_title: 'Technische Funktionsweise',
    help_technical_html: `
<section class="help-section">
  <h3>Architektur</h3>
  <p>Die Anwendung besteht aus einem <strong>FastAPI</strong>-Backend (<code>app.py</code>), einer Scan-Engine (<code>engine.py</code>) und diesem Single-Page-Frontend (<code>frontend.html</code>). Datenhaltung erfolgt in einer lokalen <strong>SQLite</strong>-Datenbank.</p>
</section>
<section class="help-section">
  <h3>Bild-Duplikaterkennung</h3>
  <dl>
    <dt>MD5-Hash (exakt)</dt>
    <dd>Jede Datei wird als Byte-Stream gehasht. Identische Hashes bedeuten byte-gleiche Dateien.</dd>
    <dt>Perceptual Hash — pHash</dt>
    <dd>Das Bild wird auf 32×32 Pixel skaliert, in Graustufen konvertiert und eine Diskrete Cosinus-Transformation (DCT) angewendet. Die obere linke 8×8-Region der DCT ergibt einen 64-Bit-Fingerprint. Der Abstand zwischen zwei Fingerprints (Hamming-Distanz) gibt an wie ähnlich zwei Bilder sind — unabhängig von Skalierung, leichter Kompression oder Farbkorrekturen.</dd>
  </dl>
  <p>Berechnete Hashes werden in der SQLite-Datenbank gecacht. Beim nächsten Scan einer bereits bekannten Datei wird der gespeicherte Wert direkt verwendet — das macht Folge-Scans deutlich schneller.</p>
</section>
<section class="help-section">
  <h3>Video-Duplikaterkennung</h3>
  <dl>
    <dt>MD5-Hash (exakt)</dt>
    <dd>Wie bei Bildern — byte-genaue Übereinstimmung.</dd>
    <dt>Frame-Sampling</dt>
    <dd>Aus jedem Video werden gleichmäßig verteilte Frames extrahiert. Von jedem Frame wird ein pHash berechnet. Zwei Videos gelten als visuelles Duplikat wenn eine ausreichende Anzahl Frame-Paare unter dem Schwellenwert liegt.</dd>
    <dt>Intensiver Abgleich (Start/End-Block)</dt>
    <dd>Die ersten und letzten X Sekunden (Standard: 30 s, 1 fps) werden separat verglichen. Damit werden auch Videos gefunden die im Mittelteil abweichen (z.B. unterschiedliche Werbeeinblendungen oder neu-enkodierte Fassungen mit geänderten Credits).</dd>
  </dl>
</section>
<section class="help-section">
  <h3>Datenbank</h3>
  <p>Die SQLite-Datenbank speichert:</p>
  <ul>
    <li>Bild-Hashes (MD5 + pHash) mit Dateipfad, Größe und Änderungsdatum</li>
    <li>Video-Hashes (MD5 + Frame-Hashes) mit Metadaten</li>
    <li>Lösch-Verlauf (welche Datei, wann, aus welcher Duplikat-Gruppe)</li>
    <li>Scan-Verlauf (Startzeit, Verzeichnis, Status, Ergebnis-JSON)</li>
  </ul>
  <p><strong>Cache zurücksetzen</strong> löscht alle Hash-Einträge, behält aber den Lösch-Verlauf. <strong>Veraltete Einträge bereinigen</strong> entfernt nur Einträge deren Dateipfad nicht mehr existiert.</p>
</section>
<section class="help-section">
  <h3>Echtzeit-Fortschritt</h3>
  <p>Der Scan-Fortschritt wird über <strong>Server-Sent Events (SSE)</strong> übertragen. Das Frontend öffnet eine persistente HTTP-Verbindung zum Backend, das laufend Status-Updates schickt — ohne Polling.</p>
</section>`,
  },

  en: {
    // Nav Rail
    nav_scan: 'Scan', nav_library: 'Library', nav_scans: 'Scans',
    nav_history: 'History', nav_db: 'DB', nav_user: 'User', nav_exit: 'Exit',
    nav_help: 'Help',
    // Sidebar
    directories: 'Directories',
    tree_click: 'Tree click sets:',
    // Settings
    dir1_label: 'Dir 1:', dir2_label: 'Dir 2:',
    compare_toggle: 'Compare mode',
    tree_click_sets: 'Tree click sets:',
    placeholder_path1: '/path/to/your/media',
    placeholder_path2: '/path/to/your/media2',
    media_type_label: 'Media type',
    opt_images: 'Images', opt_videos: 'Videos', opt_both: 'Images + Videos',
    phash_threshold_lbl: 'pHash threshold',
    min_frame_matches: 'Min. frame matches',
    duration_tolerance: 'Duration tolerance (s)',
    intensiv: 'Deep comparison',
    edge_section: 'Edge section:',
    worker: 'Workers',
    scan_start: 'Start scan',
    dir_hint: 'Select a directory and start scan.',
    // Modal
    modal_titel: 'Confirm deletion',
    modal_cancel: 'Cancel',
    modal_bestaetigen: 'Delete',
    // Library sort
    sortierung: 'Sort:',
    sort_name: 'Name', sort_date: 'Date', sort_size: 'Size',
    // View headings
    datenbank: 'Database',
    delete_history_label: 'Delete History',
    scan_history_label: 'Scan History',
    user_management: 'User Management',
    // Login
    login_title_key: 'Sign in',
    login_subtitle: 'Duplicate Finder',
    login_btn: 'Sign in',
    login_username_lbl: 'Username',
    login_password_lbl: 'Password',
    setup_title: 'Initial Setup',
    setup_subtitle: 'Create the first administrator account',
    setup_btn: 'Create account',
    // Validation / errors
    fill_fields: 'Please fill in all fields.',
    pass_min_chars_error: 'Password must be at least 6 characters.',
    connection_error: 'Connection error.',
    login_failed: 'Login failed.',
    setup_error: 'Setup error.',
    // Scan status
    loading: 'Loading…',
    scan_running: 'Scan running…',
    scan_waiting: 'Scan queued…',
    scan_started: '▶ Scan started.',
    scan_cancelled: 'Scan cancelled.',
    scan_error_toast: 'Scan error occurred.',
    scan_error_log: 'Scan error — see log above.',
    connection_lost: 'Connection to server lost.',
    scan_queued: '⏳ Scan queued — waiting for running scan…',
    scan_not_started: 'Scan could not be started: ',
    select_dir: 'Please select a directory.',
    stop: '⏹ Stop',
    stopping: '⏳ Stopping…',
    results_load_error: 'Could not load results: ',
    last_scan_lbl: '↩ Last scan: ',
    show_results: 'Show results →',
    scan_banner_text: '⟳ Scan running…',
    click_show: 'Click to view',
    click_go_back: 'Click to return to scan',
    // Results
    groups: 'groups',
    files_pl: 'files',
    wasted: 'wasted',
    image_exact_lbl: 'Exact image duplicates',
    image_visual_lbl: 'Visual image duplicates',
    video_exact_lbl: 'Exact video duplicates',
    video_visual_lbl: 'Visual video duplicates',
    video_intensive_lbl: 'Deep duplicates (start/end block)',
    cross_dir: ' (Cross-Dir)',
    storage_wasted: 'Wasted storage (approx.):',
    unprocessable: '⚠ Unprocessable:',
    unprocessable_title: 'Unprocessable files',
    gruppe_nr: 'Group #',
    none_found: 'None found.',
    deselect_all: 'Select/deselect all',
    delete_selected: 'Delete selected',
    keep_badge: '✓ Best quality',
    delete_badge: '✗ Delete',
    also_delete: 'Delete',
    mark_delete: 'Delete',
    no_preview: 'No preview',
    no_preview_video: '🎬 No preview',
    link_title_img: 'Left click: Lightbox — Middle click: New tab',
    link_title_vid: 'Left click: Player — Middle click: New tab',
    frame_click: '— Click: Full view',
    phash_0: 'pixel-identical',
    phash_low: 'nearly identical',
    phash_mid: 'very similar',
    phash_high: 'similar',
    new_scan: '← New Scan',
    goBack: '← Back',
    // Counter (pluralizable)
    marked_n: (n) => `${n} file${n !== 1 ? 's' : ''} marked for deletion`,
    delete_n: (n) => `Delete ${n} file${n !== 1 ? 's' : ''} permanently?`,
    files_n: (n) => `${n} file${n !== 1 ? 's' : ''}`,
    freed_text: (n) => `saved by deleting duplicates — ${n} file${n !== 1 ? 's' : ''} deleted`,
    error_n: (n) => `Error with ${n} file${n !== 1 ? 's' : ''}:\n`,
    cleanup_done_msg: (b, v) => `Cleaned up: ${b} image entries, ${v} video entries removed.`,
    delete_user_confirm: (name) => `Really delete user "${name}"?`,
    // Scan history
    hist_date: 'Date', hist_dir: 'Directory', hist_status: 'Status',
    no_scan_yet: 'No scans saved yet.',
    status_done: '✓ Done', status_error: '✗ Error',
    status_cancelled: '⏹ Cancelled', status_running: '⟳ Running',
    load_results: 'Load results',
    // Delete history
    db_size: 'Database size',
    hist_filename: 'Filename', hist_directory: 'Directory',
    hist_size: 'Size', hist_deleted_at: 'Deleted on',
    no_deletes_yet: 'No files deleted yet.',
    clear_history_btn: 'Clear history',
    clear_history_confirm: 'Permanently clear entire delete history?',
    // Database
    cached_images: 'Cached images:', cached_videos: 'Cached videos:',
    db_file: 'Database file:',
    cache_reset_btn: 'Reset scan cache',
    cache_reset_info: 'Deletes all cached hashes and metadata. Delete history is preserved. All files will be reprocessed on next scan.',
    cache_reset_confirm: 'Reset scan cache?\n\nAll cached image and video data will be deleted. Delete history is preserved.',
    cleanup_btn: 'Clean up stale entries',
    cleanup_info: 'Removes cache entries for files that no longer exist on the filesystem (e.g. deleted or moved).',
    // Users
    existing_users: 'Existing users',
    no_users: 'No users found.',
    username_col: 'Username', created_col: 'Created',
    you_label: '(you)',
    delete_btn_small: 'Delete',
    no_self_delete: 'Cannot delete your own account',
    add_user: 'Add user',
    username_lbl: 'Username',
    password_lbl: 'Password',
    min_chars_hint: 'min. 6 chars',
    create_btn: 'Create',
    change_pw_title: 'Change own password',
    new_pw_lbl: 'New password',
    save_btn: 'Save',
    pw_changed: 'Password changed successfully.',
    // Library
    no_dir: 'No directory selected.',
    empty_library: 'No images or videos in this directory.',
    open_in_tab: 'Open in new tab',
    open_library: 'Open library',
    setup_scan: 'Set up scan',
    // Error / misc
    click_close: ' (click to close)',
    error_msg: 'Error: ',

    // ===========================================================================
    // Help page
    // ===========================================================================
    help_title: 'Help & Documentation',

    help_usage_title: 'How to use',
    help_usage_html: `
<section class="help-section">
  <h3>1. Select a directory</h3>
  <p>Click a directory in the folder tree on the left. The selected path is automatically filled into the scan form.</p>
  <p>Enable <strong>Compare mode</strong> to scan two directories against each other — useful for comparing a backup with the original. Once active, a small <em>"Tree click sets"</em> selector appears below the tree. Use it to choose which directory the next tree click will fill — <strong style="color:#80c0ff">Dir&nbsp;1</strong> (blue) or <strong style="color:#ff8080">Dir&nbsp;2</strong> (red). Switch the target, then click the desired directory in the tree.</p>
</section>
<section class="help-section">
  <h3>2. Configure the scan</h3>
  <dl>
    <dt>Media type</dt>
    <dd>Choose whether to scan images, videos, or both.</dd>
    <dt>pHash threshold (images)</dt>
    <dd>Determines how similar two images must be to count as duplicates. <strong>0</strong> = pixel-identical, <strong>8</strong> = very similar, <strong>16+</strong> = loose (more matches, more false positives). Recommended: 6–10.</dd>
    <dt>Min. frame matches (videos)</dt>
    <dd>Minimum number of matching frames required for a video pair to be flagged. Higher = stricter.</dd>
    <dt>Duration tolerance (videos)</dt>
    <dd>Maximum allowed difference in video length in seconds. Videos with very different lengths are excluded.</dd>
    <dt>Deep comparison</dt>
    <dd>Additionally compares the first and last X seconds of each video (default: 30 s, configurable from 5–120 s). Finds copies with differing middle sections (e.g. re-encoded with different credits). Noticeably increases scan time on large libraries.</dd>
    <dt>Edge section</dt>
    <dd>Duration of the start/end block in seconds (default: 30 s, min: 5 s, max: 120 s). Only relevant for deep comparison.</dd>
    <dt>Workers</dt>
    <dd>Number of parallel processes. More workers = faster, but higher CPU and RAM usage.</dd>
  </dl>
</section>
<section class="help-section">
  <h3>3. Start scan &amp; monitor progress</h3>
  <p>Click <strong>Start scan</strong>. Progress is shown in real time in the log. A running scan can be stopped at any time. If a scan is already running, the new one is queued and starts automatically afterwards.</p>
  <p>The banner at the top shows scan progress even when you switch to another view — click it to jump back to the scan.</p>
</section>
<section class="help-section">
  <h3>4. Review results</h3>
  <p>After the scan, duplicate groups are displayed, split into:</p>
  <ul>
    <li><strong>Exact duplicates</strong> — identical MD5 hash</li>
    <li><strong>Visual duplicates</strong> — similar perceptual hash</li>
    <li><strong>Deep duplicates</strong> (videos) — similar start/end blocks</li>
  </ul>
  <p>Within each group, the file with the best quality (highest resolution / largest file size) is automatically marked as <em>Best quality</em> — all others are suggested for deletion. Selections can be adjusted manually.</p>
</section>
<section class="help-section">
  <h3>5. Delete files</h3>
  <p>Marked files are permanently deleted from the filesystem after confirmation via the red <strong>Delete selected</strong> button. The delete history is accessible under <em>History</em>.</p>
  <p><strong>Warning:</strong> Deletion is irreversible. There is no recycle bin.</p>
</section>
<section class="help-section">
  <h3>6. Media library</h3>
  <p>Shows all images and videos in the selected directory as a grid. Images can be enlarged in a lightbox, videos played in the embedded player. Sorting by name, date, or file size is available.</p>
</section>`,

    help_technical_title: 'How it works technically',
    help_technical_html: `
<section class="help-section">
  <h3>Architecture</h3>
  <p>The application consists of a <strong>FastAPI</strong> backend (<code>app.py</code>), a scan engine (<code>engine.py</code>), and this single-page frontend (<code>frontend.html</code>). Data is stored in a local <strong>SQLite</strong> database.</p>
</section>
<section class="help-section">
  <h3>Image duplicate detection</h3>
  <dl>
    <dt>MD5 hash (exact)</dt>
    <dd>Each file is hashed as a byte stream. Identical hashes mean byte-identical files.</dd>
    <dt>Perceptual hash — pHash</dt>
    <dd>The image is scaled to 32×32 pixels, converted to grayscale, and a Discrete Cosine Transform (DCT) is applied. The upper-left 8×8 region of the DCT produces a 64-bit fingerprint. The distance between two fingerprints (Hamming distance) indicates how similar two images are — regardless of scaling, minor compression, or color corrections.</dd>
  </dl>
  <p>Computed hashes are cached in the SQLite database. On the next scan of an already-known file, the stored value is used directly — making subsequent scans significantly faster.</p>
</section>
<section class="help-section">
  <h3>Video duplicate detection</h3>
  <dl>
    <dt>MD5 hash (exact)</dt>
    <dd>Same as for images — byte-exact match.</dd>
    <dt>Frame sampling</dt>
    <dd>Evenly spaced frames are extracted from each video. A pHash is computed for each frame. Two videos are considered visual duplicates if a sufficient number of frame pairs fall below the threshold.</dd>
    <dt>Deep comparison (start/end block)</dt>
    <dd>In addition to the overall comparison, frames from the first and last X percent are compared separately. This also finds videos that differ in the middle (e.g. different ad inserts or re-encoded versions with changed credits).</dd>
  </dl>
</section>
<section class="help-section">
  <h3>Database</h3>
  <p>The SQLite database stores:</p>
  <ul>
    <li>Image hashes (MD5 + pHash) with file path, size, and modification date</li>
    <li>Video hashes (MD5 + frame hashes) with metadata</li>
    <li>Delete history (which file, when, from which duplicate group)</li>
    <li>Scan history (start time, directory, status, result JSON)</li>
  </ul>
  <p><strong>Reset scan cache</strong> deletes all hash entries but keeps the delete history. <strong>Clean up stale entries</strong> only removes entries whose file path no longer exists.</p>
</section>
<section class="help-section">
  <h3>Real-time progress</h3>
  <p>Scan progress is transmitted via <strong>Server-Sent Events (SSE)</strong>. The frontend opens a persistent HTTP connection to the backend, which continuously sends status updates — no polling required.</p>
</section>`,
  }
};
