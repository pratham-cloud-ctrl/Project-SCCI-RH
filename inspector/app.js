const $ = (id) => document.getElementById(id);
const repo = 'https://github.com/pratham-cloud-ctrl/Project-SCCI-RH/blob/main/';
const sourceURL = (path) => repo + String(path || '').split('/').map(encodeURIComponent).join('/');
const bytes = (value) => value >= 1e6 ? `${(value / 1e6).toFixed(1)} MB` : `${Math.round(value / 1e3)} KB`;
const node = (tag, text, attrs = {}) => { const element = document.createElement(tag); if (text != null) element.textContent = text; for (const [key, value] of Object.entries(attrs)) element.setAttribute(key, value); return element; };
let catalog, target = 'future', view = 'model', activeSheet = null;
let three, renderer, scene, camera, controls, loader, modelRoot, selectionBox, grid;
let parts = [], selected = null, loadSequence = 0, currentModel = null;
let raycaster, pointer, pointerDown;
const drawings = {};

async function getJSON(path) {
  const response = await fetch(path);
  if (!response.ok) throw new Error(`${path}: HTTP ${response.status}`);
  return response.json();
}

function design() { return catalog.designs.find((entry) => entry.id === target); }
function board() { return catalog.boards.find((entry) => entry.id === target); }
function updateURL() {
  const url = new URL(location.href);
  url.searchParams.set('design', target);
  url.searchParams.set('view', view);
  if (view === 'schematic' && activeSheet) url.searchParams.set('sheet', activeSheet.id);
  else url.searchParams.delete('sheet');
  history.replaceState(null, '', url);
}

function setView(next, focus = false) {
  if (!['model', 'pcb', 'copper', 'schematic', 'downloads'].includes(next)) next = 'model';
  view = next;
  document.querySelectorAll('[role=tab]').forEach((button) => {
    const active = button.dataset.tab === view;
    button.setAttribute('aria-selected', String(active));
    button.tabIndex = active ? 0 : -1;
    $('panel-' + button.dataset.tab).hidden = !active;
  });
  if (focus) $('tab-' + view).focus();
  if (view === 'model') loadModel();
  if (view === 'pcb') showPCB();
  if (view === 'copper') showCopper();
  if (view === 'schematic') showSheets();
  if (view === 'downloads') showDownloads();
  updateURL();
}

function setTarget(id) {
  if (!catalog.designs.some((entry) => entry.id === id)) id = 'future';
  target = id;
  ++loadSequence;
  $('target').value = target;
  const selectedDesign = design();
  $('target-type').textContent = selectedDesign.kind === 'board' ? 'POPULATED CIRCUIT BOARD' : 'MECHANICAL ASSEMBLY';
  $('target-size').textContent = selectedDesign.dimensions || '';
  $('source-link').href = sourceURL(selectedDesign.pcb_source || selectedDesign.source);
  $('tab-model').textContent = selectedDesign.kind === 'board' ? '3D board' : '3D assembly';
  $('explode-control').hidden = selectedDesign.kind === 'board';
  $('cover-control').hidden = selectedDesign.kind === 'board';
  $('allocation-control').hidden = target !== 'future';
  $('show-allocations').checked = false;
  $('show-covers').checked = target !== 'reference';
  $('part-search').value = '';
  activeSheet = null;
  setView(view);
}

async function init3D() {
  if (renderer) return;
  const THREE = await import('three');
  const [{ OrbitControls }, { GLTFLoader }] = await Promise.all([
    import('three/addons/controls/OrbitControls.js'),
    import('three/addons/loaders/GLTFLoader.js'),
  ]);
  three = THREE;
  renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true, powerPreference: 'low-power' });
  renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
  renderer.setClearColor(0xecf2f3, 0);
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  $('model-canvas').replaceChildren(renderer.domElement);
  scene = new THREE.Scene();
  camera = new THREE.PerspectiveCamera(38, 1, .0001, 100);
  controls = new OrbitControls(camera, renderer.domElement);
  controls.enableDamping = true;
  controls.dampingFactor = .09;
  controls.addEventListener('change', render);
  scene.add(new THREE.HemisphereLight(0xffffff, 0x6d8792, 2.7));
  const light = new THREE.DirectionalLight(0xffffff, 3.0); light.position.set(2, 4, 3); scene.add(light);
  const fill = new THREE.DirectionalLight(0xdbeefa, 1.6); fill.position.set(-3, 1, -2); scene.add(fill);
  loader = new GLTFLoader();
  raycaster = new THREE.Raycaster(); pointer = new THREE.Vector2();
  renderer.domElement.addEventListener('pointerdown', (event) => { pointerDown = [event.clientX, event.clientY]; });
  renderer.domElement.addEventListener('pointerup', (event) => {
    if (!pointerDown || Math.hypot(event.clientX - pointerDown[0], event.clientY - pointerDown[1]) > 5) return;
    const rect = renderer.domElement.getBoundingClientRect();
    pointer.set((event.clientX - rect.left) / rect.width * 2 - 1, -(event.clientY - rect.top) / rect.height * 2 + 1);
    raycaster.setFromCamera(pointer, camera);
    const hits = raycaster.intersectObjects(parts.filter((part) => part.object.visible).map((part) => part.object), true);
    for (const hit of hits) {
      let object = hit.object;
      while (object && !object.userData.inspectorPartID) object = object.parent;
      if (object) { selectPart(object.userData.inspectorPartID); break; }
    }
  });
  new ResizeObserver(resize3D).observe($('canvas-wrap'));
  function animate() { requestAnimationFrame(animate); if (view === 'model') controls.update(); }
  animate();
  resize3D();
}

function resize3D() {
  if (!renderer) return;
  const width = $('model-canvas').clientWidth, height = $('model-canvas').clientHeight;
  if (!width || !height) return;
  renderer.setSize(width, height, false);
  camera.aspect = width / height; camera.updateProjectionMatrix(); render();
}
function render() { if (renderer && scene && camera) renderer.render(scene, camera); }
function dispose(object) {
  object?.traverse((child) => {
    child.geometry?.dispose();
    if (child.material) for (const material of [child.material].flat()) material.dispose();
  });
}

async function loadModel() {
  const item = design();
  const sequence = ++loadSequence;
  if (currentModel === item.id && modelRoot) { applyVisibility(); listParts(); resize3D(); return; }
  $('model-status').hidden = false; $('model-status').textContent = 'Loading source-derived geometry…';
  $('model-fallback').hidden = true;
  $('fallback-preview').href = item.preview ? item.preview : sourceURL(item.source);
  $('model-label').textContent = item.title;
  $('model-limit').textContent = item.note || 'Browser meshes are inspection copies. STEP and native CAD retain the engineering geometry.';
  $('part-list').replaceChildren(); $('part-summary').textContent = 'Loading parts…';
  try {
    if (!item.model) throw new Error('No browser model is available for this design.');
    await init3D();
    const gltf = await loader.loadAsync(item.model);
    if (sequence !== loadSequence) { dispose(gltf.scene); return; }
    if (modelRoot) { scene.remove(modelRoot); dispose(modelRoot); }
    if (grid) { scene.remove(grid); dispose(grid); }
    if (selectionBox) { scene.remove(selectionBox); dispose(selectionBox); selectionBox = null; }
    modelRoot = gltf.scene; scene.add(modelRoot); parts = []; selected = null;
    const descriptors = new Map((item.parts || []).map((part) => [String(part.id), part]));
    modelRoot.traverse((object) => {
      const data = object.userData;
      const id = data.id != null ? String(data.id) : object.name;
      if (!descriptors.has(id)) return;
      const descriptor = descriptors.get(id);
      object.userData.inspectorPartID = id;
      parts.push({ ...descriptor, id, object, base: object.position.clone(),
        label: descriptor.label || data.label || object.name,
        group: descriptor.group || data.group || 'Part',
        allocation: descriptor.allocation ?? data.allocation ?? false,
        cover: descriptor.cover || data.cover || /^(lid|cover|top.?panel)/i.test(descriptor.label || object.name),
        explode: descriptor.explode || data.explode,
      });
    });
    if (!parts.length) throw new Error('Part identities did not match the export manifest.');
    currentModel = item.id; $('explode').value = '0'; $('explode-value').textContent = '0%';
    const bounds = new three.Box3().setFromObject(modelRoot);
    const size = bounds.getSize(new three.Vector3());
    const extent = Math.max(size.x, size.y, size.z);
    grid = new three.GridHelper(extent * 1.8, 12, 0xbacbd0, 0xdbe5e7);
    grid.position.set(bounds.getCenter(new three.Vector3()).x, bounds.min.y - extent * .014, bounds.getCenter(new three.Vector3()).z);
    grid.material.transparent = true; grid.material.opacity = .35; scene.add(grid);
    applyVisibility(); listParts(); fitModel();
    const physical = parts.filter((part) => !part.allocation).length;
    const allocations = parts.filter((part) => part.allocation).length;
    $('model-count').textContent = `${physical.toLocaleString()} physical ${item.kind === 'board' ? 'objects' : 'parts'}${allocations ? ` · ${allocations} optional allocation volumes` : ''} · ${bytes(item.modelBytes || 0)}`;
    $('model-status').hidden = true;
    $('part-detail').replaceChildren(node('p', 'Select a part in the model or list to inspect its identity.'));
  } catch (error) {
    if (sequence !== loadSequence) return;
    $('model-status').textContent = 'Interactive 3D unavailable';
    $('part-summary').textContent = 'Use the original preview or design download.';
    $('model-fallback').hidden = false;
    console.warn('Model viewer:', error);
  }
}

function applyVisibility() {
  for (const part of parts) part.object.visible = !part.manualHidden &&
    (!part.allocation || $('show-allocations').checked) && (!part.cover || $('show-covers').checked);
  if (selectionBox && selected) { const part = parts.find((entry) => entry.id === selected); selectionBox.visible = !!part?.object.visible; }
  render();
}

function listParts() {
  const query = $('part-search').value.toLocaleLowerCase().trim();
  const matches = parts.filter((part) => `${part.label} ${part.id} ${part.group}`.toLocaleLowerCase().includes(query));
  $('part-summary').textContent = `${matches.length} of ${parts.length} objects · check to show`;
  $('part-list').replaceChildren(...matches.map((part) => {
    const row = node('div', null, { class: 'part-row' + (part.id === selected ? ' selected' : '') });
    const checkbox = node('input', null, { type: 'checkbox', 'aria-label': `Show ${part.label}` });
    checkbox.checked = part.object.visible;
    checkbox.addEventListener('change', () => {
      part.manualHidden = !checkbox.checked;
      if (checkbox.checked && part.allocation) $('show-allocations').checked = true;
      if (checkbox.checked && part.cover) $('show-covers').checked = true;
      applyVisibility(); listParts();
    });
    const button = node('button', part.label, { 'aria-pressed': String(part.id === selected) });
    button.append(node('small', part.allocation ? 'Nonphysical allocation' : part.group));
    button.addEventListener('click', () => selectPart(part.id));
    row.append(checkbox, button); return row;
  }));
}

function selectPart(id) {
  const part = parts.find((entry) => entry.id === id); if (!part) return;
  selected = id;
  if (selectionBox) { scene.remove(selectionBox); dispose(selectionBox); }
  selectionBox = new three.BoxHelper(part.object, 0x008b90); selectionBox.visible = part.object.visible; scene.add(selectionBox);
  const detail = $('part-detail'); detail.replaceChildren(node('strong', part.label), node('p', part.allocation ? 'Internal space allocation · not a physical component' : part.group));
  detail.append(node('p', 'Source identity: ' + part.id));
  if (part.source || design().source) detail.append(node('a', 'Inspect source ↗', { href: sourceURL(part.source || design().source), target: '_blank', rel: 'noopener' }));
  const actions = node('div'); const focus = node('button', 'Focus part'), isolate = node('button', 'Isolate');
  focus.addEventListener('click', () => fitModel(part.object));
  isolate.addEventListener('click', () => {
    for (const other of parts) other.manualHidden = other.id !== id;
    if (part.allocation) $('show-allocations').checked = true;
    if (part.cover) $('show-covers').checked = true;
    applyVisibility(); listParts(); fitModel(part.object);
  });
  actions.append(focus, isolate); detail.append(actions); listParts(); render();
  if (board() && part.reference) {
    const circuit = node('button', 'Find circuit');
    circuit.addEventListener('click', () => {
      $('sheet-search').value = part.reference;
      $('sheet-scope').value = 'selected';
      const expression = new RegExp('\\b' + part.reference + '\\b');
      const match = catalog.sheets.find((sheet) => sheet.board === target && expression.test(sheet.search));
      setView('schematic');
      if (match) selectSheet(match);
      showSheets();
    });
    actions.append(circuit);
  }
}

function fitModel(object = modelRoot) {
  if (!object || !three) return;
  const bounds = new three.Box3().setFromObject(object), center = bounds.getCenter(new three.Vector3());
  const size = bounds.getSize(new three.Vector3()), radius = Math.max(size.x, size.y, size.z, .001);
  const aspect = $('model-canvas').clientWidth / Math.max($('model-canvas').clientHeight, 1);
  const distance = radius * (aspect < 1 ? 2.5 / Math.max(aspect, .4) : 2.3);
  camera.near = Math.max(radius / 2000, .000001); camera.far = distance * 50; camera.updateProjectionMatrix();
  camera.position.copy(center).add(new three.Vector3(1.1, .85, 1.3).normalize().multiplyScalar(distance));
  controls.target.copy(center); controls.minDistance = radius * .02; controls.maxDistance = distance * 20;
  controls.update(); resize3D();
}

function explodeModel() {
  const amount = Number($('explode').value) / 100; $('explode-value').textContent = `${Math.round(amount * 100)}%`;
  const bounds = new three.Box3().setFromObject(modelRoot), center = bounds.getCenter(new three.Vector3());
  for (const part of parts) {
    const direction = part.explode ? new three.Vector3(...part.explode) :
      new three.Box3().setFromObject(part.object).getCenter(new three.Vector3()).sub(center).multiplyScalar(.7);
    part.object.position.copy(part.base).addScaledVector(direction, amount);
  }
  if (selectionBox && selected) selectionBox.update(); render();
}

function showPCB() {
  const selectedBoard = board();
  $('pcb-select-prompt').hidden = !!selectedBoard; $('pcb-frame').hidden = !selectedBoard;
  $('pcb-standalone').hidden = !selectedBoard;
  if (!selectedBoard) { $('pcb-frame').removeAttribute('src'); return; }
  $('pcb-heading').textContent = selectedBoard.title;
  const url = new URL(selectedBoard.ibom, location.href).href;
  if ($('pcb-frame').src !== url) $('pcb-frame').src = url;
  $('pcb-standalone').href = selectedBoard.ibom;
}

function showCopper() {
  const selectedBoard = board();
  for (const id of ['copper-controls', 'copper-stage', 'copper-original']) $(id).hidden = !selectedBoard;
  $('copper-select-prompt').hidden = !!selectedBoard;
  if (!selectedBoard) return;
  const layer = selectedBoard.layers.find((entry) => entry.name === $('copper-layer').value) || selectedBoard.layers[0];
  $('copper-image').src = layer.file; $('copper-image').alt = `${selectedBoard.title}: ${layer.name} copper exported from KiCad`;
  $('copper-original').href = layer.file; drawings.copper.reset();
}

function showSheets() {
  const query = $('sheet-search').value.toLocaleLowerCase().trim();
  let sheets = catalog.sheets;
  if ($('sheet-scope').value === 'selected' && board()) sheets = sheets.filter((sheet) => sheet.board === target);
  const matches = sheets.filter((sheet) => `${sheet.page} ${sheet.title} ${sheet.search || ''}`.toLocaleLowerCase().includes(query));
  if (!activeSheet || !sheets.some((sheet) => sheet.id === activeSheet.id)) {
    const requested = new URL(location.href).searchParams.get('sheet');
    selectSheet(sheets.find((sheet) => sheet.id === requested) || matches[0] || sheets[0]);
  }
  $('sheet-count').textContent = `${matches.length} matching sheets · ${catalog.sheets.length} in complete hierarchy`;
  $('sheet-list').replaceChildren(...matches.map((sheet) => {
    const button = node('button', `${String(sheet.page).padStart(2, '0')} · ${sheet.title}`, { 'aria-current': String(activeSheet?.id === sheet.id) });
    button.append(node('small', sheet.boardTitle || sheet.board || 'System hierarchy'));
    button.addEventListener('click', () => { selectSheet(sheet); showSheets(); }); return button;
  }));
}

function selectSheet(sheet) {
  if (!sheet) return;
  activeSheet = sheet; $('schematic-image').src = sheet.file;
  $('schematic-image').alt = `Integrated schematic sheet ${sheet.page}: ${sheet.title}`;
  $('sheet-heading').textContent = `${sheet.page} / ${catalog.sheets.length} · ${sheet.title}`;
  $('schematic-original').href = sheet.file;
  const line = $('sheet-source'); line.replaceChildren(node('span', 'Current source: '), node('a', sheet.source, { href: sourceURL(sheet.source), target: '_blank', rel: 'noopener' }));
  const hierarchy = $('sheet-hierarchy'); hierarchy.replaceChildren(node('span', sheet.path || '/'));
  const destinations = [];
  if (sheet.parent) destinations.push([sheet.parent, '↑ Parent']);
  for (const id of sheet.children || []) destinations.push([id, '↓']);
  for (const [id, prefix] of destinations) {
    const destination = catalog.sheets.find((item) => item.id === id); if (!destination) continue;
    const button = node('button', `${prefix} ${destination.name || destination.title}`);
    button.addEventListener('click', () => { $('sheet-scope').value = 'all'; $('sheet-search').value = ''; selectSheet(destination); showSheets(); });
    hierarchy.append(button);
  }
  drawings.schematic.reset(); updateURL();
}

function showDownloads() {
  const downloads = catalog.downloads.filter((item) => !item.designs?.length || item.designs.includes(target));
  $('download-cards').replaceChildren(...downloads.map((item) => {
    const card = node('article', null, { class: 'download-card' });
    card.append(node('span', item.format, { class: 'format' }), node('h3', item.title), node('p', item.description),
      node('a', `Download ${item.format} ↓`, { class: 'primary', href: item.file, download: '' }),
      node('small', `${bytes(item.bytes)} · SHA-256 ${item.sha256.slice(0, 12)}…`));
    return card;
  }));
  $('download-checks').replaceChildren(node('a', 'Full download checksums', { href: 'downloads/SHA256SUMS.txt' }), document.createTextNode(' · '),
    node('a', 'Complete paper and released engineering', { href: 'https://github.com/pratham-cloud-ctrl/Project-SCCI-RH/releases/tag/v2.1.0' }));
}

function initDrawing(name) {
  const stage = $(name + '-stage'), image = $(name + '-image');
  let scale = 1, x = 0, y = 0, drag;
  const draw = () => { image.style.transform = `translate(${x}px,${y}px) scale(${scale})`; };
  const zoom = (factor) => { scale = Math.max(.5, Math.min(24, scale * factor)); draw(); };
  const reset = () => { scale = 1; x = y = 0; draw(); };
  stage.addEventListener('wheel', (event) => { event.preventDefault(); zoom(Math.exp(-event.deltaY * .0015)); }, { passive: false });
  stage.addEventListener('pointerdown', (event) => { drag = [event.clientX, event.clientY, x, y]; stage.setPointerCapture(event.pointerId); });
  stage.addEventListener('pointermove', (event) => { if (drag) { x = drag[2] + event.clientX - drag[0]; y = drag[3] + event.clientY - drag[1]; draw(); } });
  stage.addEventListener('pointerup', () => { drag = null; }); stage.addEventListener('pointercancel', () => { drag = null; });
  stage.addEventListener('keydown', (event) => {
    if (event.key === '+' || event.key === '=') zoom(1.3);
    else if (event.key === '-') zoom(1 / 1.3);
    else if (event.key === '0') reset();
    else if (event.key === 'ArrowLeft') x += 40;
    else if (event.key === 'ArrowRight') x -= 40;
    else if (event.key === 'ArrowUp') y += 40;
    else if (event.key === 'ArrowDown') y -= 40;
    else return;
    event.preventDefault(); draw();
  });
  image.addEventListener('error', () => { $('app-error').hidden = false; $('app-error').textContent = 'A drawing could not load. The static inspection index and design downloads remain available.'; });
  drawings[name] = { zoom, reset };
}

async function main() {
  initDrawing('copper'); initDrawing('schematic');
  catalog = await getJSON('assets/catalog.json');
  $('board-options').replaceChildren(...catalog.boards.map((item) => node('option', item.title, { value: item.id })));
  $('target').addEventListener('change', () => setTarget($('target').value));
  document.querySelectorAll('[role=tab]').forEach((button) => button.addEventListener('click', () => setView(button.dataset.tab)));
  document.querySelector('.tabs').addEventListener('keydown', (event) => {
    const tabs = [...document.querySelectorAll('[role=tab]')], index = tabs.indexOf(document.activeElement);
    if (index < 0) return;
    if (event.key === 'ArrowRight' || event.key === 'ArrowLeft') { event.preventDefault(); const next = (index + (event.key === 'ArrowRight' ? 1 : tabs.length - 1)) % tabs.length; setView(tabs[next].dataset.tab, true); }
    if (event.key === 'Home') { event.preventDefault(); setView('model', true); }
    if (event.key === 'End') { event.preventDefault(); setView('downloads', true); }
  });
  $('header-download').addEventListener('click', (event) => { event.preventDefault(); setView('downloads'); $('tab-downloads').scrollIntoView({ block: 'center' }); });
  $('part-search').addEventListener('input', listParts);
  $('reset-model').addEventListener('click', () => fitModel());
  $('explode').addEventListener('input', () => { if (modelRoot) explodeModel(); });
  for (const id of ['show-covers', 'show-allocations']) $(id).addEventListener('change', () => { applyVisibility(); listParts(); });
  $('show-all-parts').addEventListener('click', () => { parts.forEach((part) => { part.manualHidden = false; }); $('show-covers').checked = true; applyVisibility(); listParts(); });
  $('full-model').addEventListener('click', async () => { if (document.fullscreenElement) await document.exitFullscreen(); else await $('canvas-wrap').requestFullscreen?.(); });
  $('copper-layer').addEventListener('change', showCopper);
  $('sheet-search').addEventListener('input', showSheets); $('sheet-scope').addEventListener('change', showSheets);
  document.querySelectorAll('[data-zoom]').forEach((button) => button.addEventListener('click', () => { const [name, command] = button.dataset.zoom.split(':'); if (command === 'reset') drawings[name].reset(); else drawings[name].zoom(command === '+' ? 1.4 : 1 / 1.4); }));
  document.querySelectorAll('[data-choose-board]').forEach((button) => button.addEventListener('click', () => setTarget('recording-front-end')));
  const query = new URL(location.href).searchParams;
  view = query.get('view') || 'model'; setTarget(query.get('design') || 'future');
  document.documentElement.dataset.inspectorReady = 'true';
}

main().catch((error) => {
  $('app-error').hidden = false;
  $('app-error').replaceChildren(node('strong', 'The interactive index could not load. '), node('a', 'Open the static inspection index', { href: 'fallback.html' }));
  $('model-status').textContent = 'Use the static index below.';
  console.error(error);
});
